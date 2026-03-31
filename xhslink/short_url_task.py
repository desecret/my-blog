import execjs
import json
import random
import socket
import time
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
COOKIE_FILE = BASE_DIR / "input" / "cookie.txt"
OUTPUT_FILE = BASE_DIR / "output" / "short_url_result.json"

API_PATH = "/api/sns/web/short_url"
TARGET_URL = "https://edith.xiaohongshu.com/api/sns/web/short_url"


def get_local_ip() -> str:
    """Get the primary local IPv4 address used for outbound traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect does not send packets, it only resolves the local route.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()

# 中间页地址（页面内部自行决定跳转目标，不通过 URL 参数传递目标链接）
MIDDLE_PAGE_URL = f"http://{get_local_ip()}:9999/middle"
print(f"Middle page URL: {MIDDLE_PAGE_URL}")  # Debug log for middle page URL


# xhs 协议中的 applink 使用“中间页链接”
ORIGINAL_URL = f'xhsdiscover://open_app?params={{"applink":"{MIDDLE_PAGE_URL}"}}'
# ORIGINAL_URL = 'xhsdiscover://extweb?link=https://xiaohongshu.baidu.com'

# Same alphabet as b64Encode implementation in static/xhs_xs_xsc_56.js
CUSTOM_B64_ALPHABET = "ZmserbBoHQtNP+wOcza/LpngG8yJq42KWYj0DSfdikx3VT16IlUAFM97hECvuRX5"
STD_B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

FFF = (
    "I38rHdgsjopgIvesdVwgIC+oIELmBZ5e3VwXLgFTIxS3bqwErFeexd0ekncAzMFYnqthIhJeSnMDKutRI3KsYorWHPtGrbV0P9WfIi/eWc6eYqtyQApPI37ekmR6QL+5Ii6sdneeSfqYHqwl2qt5B0DBIx++GDi/sVtkIxdsxuwr4qtiIhuaIE3e3LV0I3VTIC7e0utl2ADmsLveDSKsSPw5IEvsiVtJOqw8BuwfPpdeTFWOIx4TIiu6ZPwbPut5IvlaLbgs3qtxIxes1VwHIkumIkIyejgsY/WTge7eSqte/D7sDcpipedeYrDtIC6eDVw2IENsSqtlnlSuNjVtIvoekqt3cZ7sVo4gIESyIhE4NnquIxhnqz8gIkIfoqwkICZW8g3sdlOeVPw3IvAe0fged0YyIi5s3Mc52utAIiKsidvekZNeTPt4nAOeWPwEIvSzaAdeSVwXpnesDqwmI3TrIxE5Luwwaqw+rekhZANe1MNe0Pw9ICNsVLoeSbIFIkosSr7sVnFiIkgsVVtMIiudqqw+tqtWI30e3PwIIhoe3ut1IiOsjut3wutnsPwXICclI3Ir27lk2I5e1utCIES/IEJs0PtnpYIAO0JeYfD1IErPOPtKoqw3I3OexqtWQL5eiz0sVSEyIEJekd/skPtsnPwqICJeSPwiIh5eVAuLIv5eYo/e0PtSICKsVqwV4omqI3RIIkge0e0sYZ0si/7eiuwSIvTeIhqmGuwCIkrPIx0edUzbzbveTPw5IxI0yVwImZeedM0eWVwmeqt2IiM9IhhQLqwJPqtbIxZ="
)


def load_cookie() -> str:
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"Cookie file not found: {COOKIE_FILE}")
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def extract_a1(cookie_str: str) -> str:
    for item in cookie_str.split(";"):
        item = item.strip()
        if item.startswith("a1="):
            return item[3:]
    raise ValueError("a1 not found in cookie")


def load_sign_js_context():
    js_path = ROOT_DIR / "static" / "xhs_creator_xs.js"
    source = js_path.read_text(encoding="utf-8")
    return execjs.compile(source)


def gen_xs_xt(api: str, payload: dict, a1: str) -> tuple[str, int]:
    ctx = load_sign_js_context()
    ret = ctx.call("get_request_headers_params", api, payload, a1)
    return ret["xs"], int(ret["xt"])


def make_crc32_variant_table() -> list[int]:
    poly = 0xEDB88320
    table = [0] * 256
    for d in range(256):
        r = d
        for _ in range(8):
            if r & 1:
                r = (r >> 1) ^ poly
            else:
                r = r >> 1
        table[d] = r & 0xFFFFFFFF
    return table


CRC_TABLE = make_crc32_variant_table()


def gens9(value: str) -> int:
    poly = 0xEDB88320
    c = -1
    for ch in value:
        c = CRC_TABLE[(c & 0xFF) ^ ord(ch)] ^ ((c >> 8) & 0xFFFFFFFF)
    out = ((-1 ^ c ^ poly) & 0xFFFFFFFF)
    if out >= 2**31:
        out -= 2**32
    return out


def b64_custom_encode(raw: bytes) -> str:
    import base64

    std = base64.b64encode(raw).decode("ascii")
    mapped = []
    for ch in std:
        idx = STD_B64_ALPHABET.find(ch)
        mapped.append(CUSTOM_B64_ALPHABET[idx] if idx != -1 else ch)
    return "".join(mapped)


def gen_xs_common(a1: str, xs: str, xt: int) -> str:
    data = {
        "s0": 5,
        "s1": "",
        "x0": "1",
        "x1": "4.2.6",
        "x2": "Windows",
        "x3": "xhs-pc-web",
        "x4": "4.84.1",
        "x5": a1,
        "x6": xt,
        "x7": xs,
        "x8": FFF,
        "x9": gens9(str(xt) + xs + FFF),
        "x10": 0,
        "x11": "normal",
    }
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b64_custom_encode(body)


def gen_trace_ids() -> tuple[str, str]:
    trace32 = "".join(random.choice("0123456789abcdef") for _ in range(32))
    trace16 = "".join(random.choice("0123456789abcdef") for _ in range(16))
    return trace32, trace16


def build_headers(cookie_str: str, xs: str, xt: int, xs_common: str) -> dict:
    xray_traceid, b3_traceid = gen_trace_ids()
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://www.xiaohongshu.com",
        "referer": "https://www.xiaohongshu.com/",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
        "x-xray-traceid": xray_traceid,
        "x-b3-traceid": b3_traceid,
        "x-s": xs,
        "x-t": str(xt),
        "x-s-common": xs_common,
        "xsecappid": "xhs-pc-web",
        "cookie": cookie_str,
    }


def normalize_original_url(original_url: str) -> str:
    """UTF-8 encode params.applink value in ORIGINAL_URL when available."""
    parts = urlsplit(original_url)
    query_map = parse_qs(parts.query, keep_blank_values=True)
    params_values = query_map.get("params")
    if not params_values:
        return original_url

    raw_params = params_values[0]
    decoded_params = unquote(raw_params)

    params_obj = None
    for candidate in (decoded_params, raw_params):
        try:
            params_obj = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if not isinstance(params_obj, dict):
        return original_url

    applink = params_obj.get("applink")
    if not isinstance(applink, str) or not applink:
        return original_url

    params_obj["applink"] = quote(applink, safe="")
    params_json = json.dumps(params_obj, ensure_ascii=False, separators=(",", ":"))
    # Keep existing %xx in applink to avoid double-encoding when params is encoded.
    encoded_params = quote(params_json, safe="%")

    query_map["params"] = [encoded_params]
    new_query_parts = []
    for key, values in query_map.items():
        for value in values:
            new_query_parts.append(f"{quote(key, safe='')}={value}")
    new_query = "&".join(new_query_parts)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def run_short_url_task(original_url: str) -> dict:
    cookie_str = load_cookie()
    a1 = extract_a1(cookie_str)

    normalized_original_url = normalize_original_url(original_url)
    print(f"Normalized original URL: {normalized_original_url}")  # Debug log for normalized URL
    payload = {"original_url": normalized_original_url}
    xs, xt = gen_xs_xt(API_PATH, payload, a1)
    xs_common = gen_xs_common(a1, xs, xt)

    headers = build_headers(cookie_str, xs, xt, xs_common)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib_request.Request(TARGET_URL, data=body, headers=headers, method="POST")

    status_code = 0
    response_text = ""
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            status_code = int(resp.status)
            response_text = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        status_code = int(exc.code)
        response_text = exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        status_code = -1
        response_text = str(exc)

    parsed_response = None
    try:
        parsed_response = json.loads(response_text)
    except json.JSONDecodeError:
        parsed_response = None
        
    short_url = "https://" + parsed_response["data"]["short_url"] if parsed_response and "data" in parsed_response and "short_url" in parsed_response["data"] else None

    result = {
        "request": {
            "url": TARGET_URL,
            "api": API_PATH,
            "payload": payload,
            "headers": {
                "x-s": xs,
                "x-t": str(xt),
                "x-s-common": xs_common,
            },
        },
        "response": {
            "status_code": status_code,
            "data": short_url,
            "raw_text": response_text,
        },
        "timestamp_ms": int(time.time() * 1000),
    }

    out_path = OUTPUT_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def main():
    result = run_short_url_task(ORIGINAL_URL)

    
    print(f"status_code={result['response']['status_code']}")
    # print(f"output={out_path}")
    print(f"short_url={result['response']['data']}")


if __name__ == "__main__":
    main()
