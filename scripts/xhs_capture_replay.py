import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from playwright.sync_api import Request, sync_playwright


BASE_DIR = Path(__file__).resolve().parent
CONFIG = {
    "user_data_dir": str(BASE_DIR / ".pw-user-data"),
    "start_url": "https://creator.xiaohongshu.com/publish/publish?from=tab_switch&target=image",
    "capture_duration_ms": 30000,
    "capture_url_keywords": ["/api/", "creator.xiaohongshu.com"],
    # 精确接口匹配：只要 URL 中包含该片段才抓取/重放。留空字符串表示不过滤。
    "target_endpoint_contains": "/api/media/v1/upload/creator/permit",
    "output_file": str(BASE_DIR.parent / "xhslink" / "output" / "captured_requests_py.json"),
    "storage_state_file": str(BASE_DIR / ".pw-storage-state.json"),
    "replay_times": 1,
    # 重放时可统一覆盖 query/header/body 字段
    "query_overrides": {
        "from_replay": "1",
    },
    "header_overrides": {
        "x-replay-source": "playwright-python",
    },
    # 支持点路径写法，例如 "data.title": "new title"
    "body_overrides": {
        "replay_tag": "debug",
    },
}


def is_target_endpoint(url: str) -> bool:
    needle = (CONFIG.get("target_endpoint_contains") or "").strip()
    if not needle:
        return True
    return needle in url


def should_capture(req: Request) -> bool:
    if req.resource_type not in {"xhr", "fetch"}:
        return False
    url = req.url
    if not any(keyword in url for keyword in CONFIG["capture_url_keywords"]):
        return False
    return is_target_endpoint(url)


def sanitize_headers(headers: dict) -> dict:
    blocked = {
        "content-length",
        "host",
        "connection",
        "accept-encoding",
        ":authority",
        ":method",
        ":path",
        ":scheme",
    }
    clean = {}
    for key, value in (headers or {}).items():
        if key.lower() not in blocked:
            clean[key] = value
    return clean


def parse_json_safe(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def set_nested_value(payload: dict, dotted_key: str, value):
    cursor = payload
    parts = [item for item in dotted_key.split(".") if item]
    if not parts:
        return
    for key in parts[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[parts[-1]] = value


def modify_captured_request(record: dict) -> dict:
    next_record = deepcopy(record)

    parsed = urlparse(next_record["url"])
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(CONFIG.get("query_overrides", {}))
    new_query = urlencode(query)
    next_record["url"] = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )

    next_record["headers"].update(CONFIG.get("header_overrides", {}))

    if isinstance(next_record.get("body_json"), dict):
        for dotted_key, value in CONFIG.get("body_overrides", {}).items():
            set_nested_value(next_record["body_json"], dotted_key, value)

    return next_record


def capture_requests(page):
    records = []

    def on_request_finished(req: Request):
        if not should_capture(req):
            return

        resp = req.response()
        headers = sanitize_headers(req.headers)
        body_text = req.post_data or ""

        record = {
            "ts": page.evaluate("() => new Date().toISOString()"),
            "method": req.method,
            "url": req.url,
            "headers": headers,
            "body_text": body_text,
            "body_json": parse_json_safe(body_text),
            "response_status": resp.status if resp else None,
        }
        records.append(record)
        print(f"[CAPTURE] {req.method} {req.url}")

    page.on("requestfinished", on_request_finished)
    return records


def replay_requests(playwright, records: list):
    if not records:
        print("[REPLAY] no requests to replay")
        return

    api = playwright.request.new_context(storage_state=CONFIG["storage_state_file"])

    try:
        write_methods = {"POST", "PUT", "PATCH", "DELETE"}
        for record in records:
            if not is_target_endpoint(record.get("url", "")):
                continue
            for _ in range(CONFIG["replay_times"]):
                req = modify_captured_request(record)
                options = {
                    "method": req["method"],
                    "headers": sanitize_headers(req.get("headers", {})),
                }

                if req["method"] in write_methods:
                    if isinstance(req.get("body_json"), dict):
                        options["data"] = req["body_json"]
                    elif req.get("body_text"):
                        options["data"] = req["body_text"]

                resp = api.fetch(req["url"], **options)
                text = resp.text()
                preview = " ".join(text.split())[:200]
                print(f"[REPLAY] {req['method']} {req['url']} -> {resp.status} | {preview}")
    finally:
        api.dispose()


def main():
    with sync_playwright() as p:
        context = None
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=CONFIG["user_data_dir"],
                headless=False,
            )

            page = context.new_page()
            records = capture_requests(page)

            page.goto(CONFIG["start_url"])
            print(f"capture started, keep window for {CONFIG['capture_duration_ms'] / 1000:.0f}s")
            print("perform actions in page now (upload, click, submit, etc.)")

            page.wait_for_timeout(CONFIG["capture_duration_ms"])

            output_path = Path(CONFIG["output_file"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[SAVE] captured {len(records)} requests -> {output_path}")

            context.storage_state(path=CONFIG["storage_state_file"])
            replay_requests(p, records)

            print("done, keep browser open 8s for inspection")
            page.wait_for_timeout(8000)
        except Exception as exc:
            print(f"script failed: {exc}")
            raise
        finally:
            if context:
                context.close()


if __name__ == "__main__":
    main()
