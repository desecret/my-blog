import os
import execjs
import json
from urllib.parse import quote, urlsplit
from flask import Flask, request, jsonify, render_template

from short_url_task import run_short_url_task

app = Flask(__name__)

# 中间页固定跳转目标（当 URL 不带 target 参数时使用）
DEFAULT_MIDDLE_TARGET = "https://wx.cdgoufang.com/v/f/oO3LcT7R"

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)

# 加载 JS 文件
def load_js():
    js_path = os.path.join(ROOT_DIR, 'static', 'xhs_creator_xs.js')
    with open(js_path, encoding='utf-8') as f:
        return execjs.compile(f.read())

# 全局复用编译好的 JS 上下文
js_context = load_js()

def gen_sign(api, a1, data=""):
    ret = js_context.call('get_request_headers_params', api, data, a1)
    return ret['xs'], ret['xt']


def is_allowed_target(target: str) -> bool:
    try:
        parsed = urlsplit(target)
    except Exception:
        return False
    return parsed.scheme in {"http", "https", "xhsdiscover"}


@app.route('/short-url-page', methods=['GET'])
def short_url_page():
    return render_template('short_url.html')


@app.route('/index.html', methods=['GET'])
@app.route('/middle', methods=['GET'])
def middle_page():
    target = (request.args.get('target') or '').strip() or DEFAULT_MIDDLE_TARGET
    if not target:
        return render_template('middle_redirect.html', target='', delay=0, error='未配置跳转目标')
    if not is_allowed_target(target):
        return render_template('middle_redirect.html', target='', delay=0, error='目标链接协议不被允许')
    return render_template('middle_redirect.html', target=target, delay=1, error='')


@app.route('/api/middle-url', methods=['POST'])
def build_middle_url():
    req_data = request.get_json(silent=True) or {}
    target = (req_data.get('target') or '').strip()
    if not target:
        return jsonify({"code": 400, "msg": "Missing 'target'", "data": None}), 400
    if not is_allowed_target(target):
        return jsonify({"code": 400, "msg": "Unsupported target scheme", "data": None}), 400

    middle_url = f"{request.host_url.rstrip('/')}/index.html?target={quote(target, safe='')}"
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "middle_url": middle_url,
            "target": target,
        }
    })


@app.route('/api/short-url', methods=['POST'])
def create_short_url():
    req_data = request.get_json(silent=True) or {}
    applink_value = (req_data.get('applink') or '').strip()
    if not applink_value:
        return jsonify({"code": 400, "msg": "Missing 'applink'", "data": None}), 400

    try:
        params_json = json.dumps({"applink": applink_value}, ensure_ascii=False, separators=(",", ":"))
        original_url = f"xhsdiscover://open_app?params={params_json}"
        task_result = run_short_url_task(original_url)
        short_url = task_result.get("response", {}).get("data")
        if not short_url:
            return jsonify({
                "code": 502,
                "msg": "Failed to generate short_url",
                "data": task_result.get("response", {}).get("raw_text"),
            }), 502

        return jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "short_url": short_url,
                "normalized_original_url": task_result.get("request", {}).get("payload", {}).get("original_url"),
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
