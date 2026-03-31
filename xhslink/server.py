import json
import logging
import time
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template

from app_config import DEFAULT_MIDDLE_TARGET
from db_store import (
    fetch_dashboard_data,
    fetch_link_mapping_by_key,
    fetch_target_url_by_key,
    get_or_create_link_key,
    get_total_generated,
    insert_generation_log,
    insert_middle_visit_event,
    touch_generation_log_for_reuse,
    update_link_mapping_urls,
)
from redirect_store import (
    is_allowed_target,
    load_redirect_config,
)
from sign_service import gen_sign
from short_url_task import run_short_url_task

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def _db_path(config: dict) -> str:
    return (config.get('dbPath') or 'data/xhslink.db').strip()


def _try_db_write(config: dict, write_action, action_name: str) -> None:
    try:
        write_action()
    except Exception as exc:
        logger.warning('DB_WRITE_FAILED action=%s err=%s', action_name, exc)


def _resolve_middle_base_url(config: dict) -> str:
    configured = (config.get('middleBaseUrl') or '').strip().rstrip('/')
    if configured:
        return configured
    return request.host_url.rstrip('/')


def _lookup_target_by_key(config: dict, key: str) -> tuple[str, str]:
    try:
        target = fetch_target_url_by_key(key, _db_path(config))
        if target:
            return target, 'db'
    except Exception as exc:
        logger.warning('MIDDLE_LOOKUP_DB_FAILED key=%s err=%s', key, exc)
    return '', 'none'


def _get_client_ip() -> str:
    x_forwarded_for = (request.headers.get('X-Forwarded-For') or '').strip()
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return (request.remote_addr or '').strip()


def _track_middle_visit(config: dict, key: str, target: str, status: str, error: str) -> None:
    event_item = {
        'timestamp_ms': int(time.time() * 1000),
        'key': key,
        'target': target,
        'status': status,
        'error': error,
        'ip': _get_client_ip(),
        'referer': (request.headers.get('Referer') or '').strip(),
        'user_agent': (request.headers.get('User-Agent') or '').strip(),
    }

    logger.info(
        'MIDDLE_TRACK status=%s key=%s target=%s ip=%s referer=%s error=%s',
        status,
        key,
        target,
        _get_client_ip(),
        (request.headers.get('Referer') or '').strip(),
        error,
    )

    _try_db_write(
        config,
        lambda: insert_middle_visit_event(event_item, _db_path(config)),
        'insert_middle_visit_event',
    )


@app.route('/short-url-page', methods=['GET'])
def short_url_page():
    return render_template('short_url.html')


@app.route('/middle', methods=['GET'])
def middle_page():
    config = load_redirect_config()
    key = (request.args.get('k') or request.args.get('key') or '').strip()
    delay = max(0, int(config.get('delaySeconds', 1)))
    missing_key = False

    if key:
        target, source = _lookup_target_by_key(config, key)
        logger.info('MIDDLE_LOOKUP key=%s source=%s hit=%s', key, source, bool(target))
        if not target:
            _track_middle_visit(config, key, '', 'invalidKey', '无效的跳转 key')
            return render_template('middle_redirect.html', target='', delay=0, error='无效的跳转 key')
    else:
        target = (config.get('defaultTarget') or '').strip() or DEFAULT_MIDDLE_TARGET
        missing_key = True

    if not target:
        _track_middle_visit(config, key, '', 'invalidTarget', '未配置跳转目标')
        return render_template('middle_redirect.html', target='', delay=0, error='未配置跳转目标')
    if not is_allowed_target(target):
        _track_middle_visit(config, key, target, 'invalidTarget', '目标链接协议不被允许')
        return render_template('middle_redirect.html', target='', delay=0, error='目标链接协议不被允许')

    if missing_key:
        _track_middle_visit(config, '', target, 'missingKey', '')
    else:
        _track_middle_visit(config, key, target, 'success', '')

    return render_template('middle_redirect.html', target=target, delay=delay, error='')


@app.route('/api/middle-url', methods=['POST'])
def build_middle_url():
    req_data = request.get_json(silent=True) or {}
    target = (req_data.get('target') or '').strip()
    if not target:
        return jsonify({"code": 400, "msg": "Missing 'target'", "data": None}), 400
    if not is_allowed_target(target):
        return jsonify({"code": 400, "msg": "Unsupported target scheme", "data": None}), 400

    config = load_redirect_config()
    key, _ = get_or_create_link_key(target, _db_path(config))

    middle_base_url = _resolve_middle_base_url(config)
    middle_url = f"{middle_base_url}/middle?k={quote(key, safe='')}"
    _try_db_write(
        config,
        lambda: update_link_mapping_urls(key, middle_url=middle_url, db_path=_db_path(config)),
        'update_link_mapping_urls_from_middle_url',
    )

    logger.info('BUILD_MIDDLE_URL key=%s middle_url=%s source_base=%s', key, middle_url, middle_base_url)
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "middle_url": middle_url,
            "key": key,
            "target": target,
        }
    })


@app.route('/api/short-url-dashboard', methods=['GET'])
def short_url_dashboard():
    config = load_redirect_config()
    data = fetch_dashboard_data(_db_path(config), history_limit=200, logs_limit=50)

    logger.info(
        'DASHBOARD_QUERY source=db total_generated=%s mapped_url_count=%s middle_total=%s middle_logs=%s',
        int(data.get('total_generated', 0)),
        int(data.get('mapped_url_count', 0)),
        int((data.get('middle_stats') or {}).get('total', 0)),
        len(data.get('middle_visit_logs') or []),
    )

    return jsonify({
        "code": 0,
        "msg": "success",
        "data": data,
    })


@app.route('/api/short-url', methods=['POST'])
def create_short_url():
    req_data = request.get_json(silent=True) or {}
    target_url = (req_data.get('target_url') or req_data.get('url') or '').strip()
    applink_value = (req_data.get('applink') or '').strip()

    config = load_redirect_config()

    key = ''
    middle_url = ''
    reused = False
    short_url = ''
    normalized_original_url = ''
    if target_url:
        if not is_allowed_target(target_url):
            return jsonify({"code": 400, "msg": "Unsupported target_url scheme", "data": None}), 400
        key, _ = get_or_create_link_key(target_url, _db_path(config))
        middle_base_url = _resolve_middle_base_url(config)
        middle_url = f"{middle_base_url}/middle?k={quote(key, safe='')}"
        applink_value = middle_url
        mapping = fetch_link_mapping_by_key(key, _db_path(config))
        short_url = (mapping.get("short_url") or "").strip()
        reused = bool(short_url)

        if reused:
            last_middle_url = (mapping.get("middle_url") or "").strip()
            if last_middle_url and last_middle_url != middle_url:
                logger.info(
                    'SHORT_URL_REUSE_BYPASS key=%s reason=middle_url_changed old=%s new=%s',
                    key,
                    last_middle_url,
                    middle_url,
                )
                reused = False

        logger.info('CREATE_SHORT_URL key=%s target_url=%s middle_url=%s reused=%s', key, target_url, middle_url, reused)

    if not applink_value:
        return jsonify({"code": 400, "msg": "Missing 'target_url' or 'applink'", "data": None}), 400

    try:
        if not reused:
            params_json = json.dumps({"applink": applink_value}, ensure_ascii=False, separators=(",", ":"))
            original_url = f"xhsdiscover://open_app?params={params_json}"
            task_result = run_short_url_task(original_url)
            short_url = task_result.get("response", {}).get("data")
            normalized_original_url = task_result.get("request", {}).get("payload", {}).get("original_url")
            if not short_url:
                return jsonify({
                    "code": 502,
                    "msg": "Failed to generate short_url",
                    "data": task_result.get("response", {}).get("raw_text"),
                }), 502

        created_at_ms = int(time.time() * 1000)
        history_item = {
            "key": key,
            "target_url": target_url,
            "middle_url": middle_url,
            "short_url": short_url,
            "created_at_ms": created_at_ms,
            "reused": reused,
        }
        if key:
            _try_db_write(
                config,
                lambda: update_link_mapping_urls(
                    key,
                    middle_url=middle_url,
                    short_url=short_url,
                    db_path=_db_path(config),
                ),
                'update_link_mapping_urls_after_short',
            )
            if reused:
                _try_db_write(
                    config,
                    lambda: touch_generation_log_for_reuse(
                        key,
                        short_url,
                        touched_at_ms=int(history_item.get('created_at_ms') or int(time.time() * 1000)),
                        db_path=_db_path(config),
                    ),
                    'touch_generation_log_for_reuse',
                )
            else:
                _try_db_write(
                    config,
                    lambda: insert_generation_log({
                        'key': key,
                        'target_url': target_url,
                        'middle_url': middle_url,
                        'short_url': short_url,
                        'reused': reused,
                        'created_at_ms': int(history_item.get('created_at_ms') or int(time.time() * 1000)),
                        'request_payload': {
                            'target_url': target_url,
                            'applink': applink_value,
                        },
                        'response_payload': {
                            'short_url': short_url,
                            'reused': reused,
                        },
                    }, _db_path(config)),
                    'insert_generation_log',
                )
        total_generated = get_total_generated(_db_path(config))

        return jsonify({
            "code": 0,
            "msg": "reused" if reused else "success",
            "data": {
                "short_url": short_url,
                "normalized_original_url": normalized_original_url,
                "target_url": target_url,
                "middle_url": middle_url,
                "key": key,
                "total_generated": int(total_generated),
                "reused": reused,
                "reuse_tip": "检测到相同投放 URL，已复用历史短链" if reused else "已生成新的短链",
                "history_item": history_item,
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500

@app.route('/sign', methods=['POST', 'GET'])
def get_signature():
    if request.method == 'GET':
        api = request.args.get('api', '')
        a1 = request.args.get('a1', '')
        data = request.args.get('data', '')
    else:
        req_data = request.get_json(silent=True) or {}
        api = req_data.get('api', '')
        a1 = req_data.get('a1', '')
        data = req_data.get('data', '')

    if not api or not a1:
        return jsonify({"code": 400, "msg": "Missing 'api' or 'a1' parameter", "data": None}), 400

    try:
        xs, xt = gen_sign(api, a1, data)
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "x-s": xs,
                "x-t": xt
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
