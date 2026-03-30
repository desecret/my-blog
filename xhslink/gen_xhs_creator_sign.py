import execjs
import os
import subprocess
import json
from urllib.parse import urlparse


APP_UPLOAD_NOTE_MOBILE_HEADERS = {
    "user-agent": "discover/9.22.1 (iPhone; iOS 26.1; Scale/3.00) Resolution/1284*2778 Version/9.22.1 Build/9221801 Device/(Apple Inc.;iPhone13,4) NetType/WiFi",
    "xy-direction": "21",
    "x-xray-traceid": "ce9177fac590c0ba9124cea880806f95",
    "xy-scene": "point=1499&fs=0",
    "x-mini-mua": "eyJhIjoiRUNGQUFGMDIiLCJjIjo1MTksImkiOjIsImsiOiI5ODdjNDZiYTRiYjhjOTIyNDE5YmIxMDlhMWQ3ODVhMjYzOWM4OWFiMDdlNDE0OGIzM2Y5NjBjY2RlOTNhNTMwIiwibSI6IjE3NzQ0MDc2NDQ1NTYiLCJuIjoiMTg4N2EzMWUwM2QyOGUwYjI2ZWZiOGI5MzAxMGRiMDMiLCJvIjoiNkp2R0pQU3lzRHBmZW1GUktpYjgxdyIsInAiOiJpIiwicyI6IjZkODg1MDc3YWFjODhjNDRkMTczYzA0OGRjMDI4OTBjIiwidSI6IjAwMDAwMDAwN2Y5N2QwMWI5ZDg4NWJkZmVmMzZhMmNlNGI3YzllM2MiLCJ2IjoiMi4xLjk1In0.TH-G4FGfN82Kt83b8Q3pWOB1jc5bmKcwblKP2hV6GxrGeSgtVtpX9Curec33jHSjTm0u9KDgI6gBtUNbFjroH9g8iSV7kadxU1MxYkKpJ9yi_vn99f5LhMI9SSgA2AVzlD_QweNfEdZx5CiezBi2hh1-xs6rxsnMpnf1Q0WHd3yA0JC4EE7qWHO4DZv4BBI4C4PZJV13tYq4ScWdIzEej7pbhslXSZKGSwt90ZLvcDcjDOe8dUAPfqI99lFsDm1Qu2c0bDa-xgZvDvFRE9KcuN0nJoGyhSNNjvK9IJJEDhHuTyI-bK4Vw9g4A6TWFq0KvuPhEOy65ggFST4Ruah9Ff-XHppwLXHJvNZXEPzVfot_LMHE1hmunFFoMEqp47JsodRxuVhWE3sOokS3VMrGV6sbzrYxtKg9-bkf8dvGnkC0FfyKjQGEGQIpSEvDBEA_QfiYUu44N8-Skmqm7ydb_QbVt5LUqWST6iNRc7c3vWrsMUQSl8yKZKbSQyKg-6jq-dTRYwuEdGGQ9h8aBwES7kILoFrfZwiwJJKof4PC4PfPDSHnmZXZF0KUiDs7S-hp.",
    "x-b3-traceid": "3e4f8b49c5131bd7",
    "x-mini-sig": "b9bb535a1b1266d59b37d4837a7c9a2d9b9220f28cba085dc2d7af7b2512fd6f",
    "accept-language": "zh-Hans-JP;q=1",
    "x-mini-nsig": "05c14bad71d34132f2604ddd1371633b0310a302a25a430edb3d5a156c6bc8a3",
    "x-legacy-did": "B373FBE3-2081-4709-AE0D-22856E6440CE",
    "x-mini-gid": "7cbdceda17595494b23fcc303a9417b69cbe65c847359ff077727f97",
    "x-mini-s1": "ABgBAAAB3J2HQUZDIwS9fhz+AF/KRBaRFSI4suqJNgRbL+c5SkmIppieJyQ24ZexNnTLSSZs6JMIFxhF3wU=",
    "shield": "XYAAEAAgAAAAEAAABTAAAAUzUWEe4xG1IYD9/c+qCLOlKGmTtFa+lG438MfuBeRKwwxoOz6MQST536/+hez8Qt3MR+oNcyZAxME22NYs7y2C9g9ZEN1BzL20uiqSke0w0y6Xf0",
    "x-net-core": "crn",
    "xy-platform-info": "platform=iOS&version=9.22.1&build=9221801&deviceId=B373FBE3-2081-4709-AE0D-22856E6440CE&bundle=com.xingin.discover",
    "accept-encoding": "gzip;q=1.0,compress;q=0.5",
    "mode": "gslb",
    "xy-common-params": "SUE=1&app_id=ECFAAF02&auto_trans=0&build=9221801&channel=AppStore&data_ctry=CN&deviceId=B373FBE3-2081-4709-AE0D-22856E6440CE&device_level=1&device_model=phone&did=2a94fd59b0531a1e9e7a9dd00d41c6c8&dlang=zh&fid=&gid=7cbdceda17595494b23fcc303a9417b69cbe65c847359ff077727f97&holder_ctry=CN&id_token=VjEAABhtDDEa%2B5lpoDiCivV%2BMCJCTRzFy%2BBi9Ay493t3zq4gqU1FjQZcALiFVSmjkh0meCCx8OZMy6OmJMWKFN95qdJkqzJslwBE2cjUitA03D51q5I61PbzwYsaD6ZF/LKbRh8J&identifier_flag=0&is_mac=0&lang=zh-Hans&launch_id=796045244&mlanguage=zh_cn&nqe_score=62&overseas_channel=0&platform=iOS&project_id=ECFAAF&sid=session.1773308568730829565075&t=1774407644&teenager=0&tz=Asia/Shanghai&uis=light&version=9.22.1",
    "x-raw-ptr": "0",
    "accept": "*/*",
    "referer": "https://app.xhs.cn/",
    "x-legacy-fid": "",
}

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(BASE_DIR)
COOKIE_FILE = os.path.join(BASE_DIR, "input", "cookie.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "output", "biz_requests_result.json")

TARGET_HOST = "https://creator.xiaohongshu.com"

# 如果 ACTIVE_JOB_NAME 为空，则执行列表里的所有任务。
# 如果给定了某个名字（例如 "permit_post_example"），则只执行那一个。
ACTIVE_JOB_NAME = "app_upload_note"

# 每条请求可单独配置 method 与目标地址，支持以下三种写法：
# 1) url: 完整 URL
# 2) host + api: host 为域名，api 为签名路径（推荐）
# 3) path: 使用全局 TARGET_HOST + path
REQUEST_JOBS = [
    {
        "name": "permit_spectrum_get",
        "method": "GET",
        "host": "https://creator.xiaohongshu.com",
        "api": "/api/media/v1/upload/creator/permit?biz_name=&scene=image&file_count=1&version=1&source=web",
    },
    {
        "name": "permit_post_example",
        "method": "POST",
        "host": "https://pro.xiaohongshu.com",
        "api": "/ads/api/clue/common/query/upload/permit",
        "data": {
            "bizName": "professional",
	        "scene": "aurora_image",
	        "fileCount": 1
        },
    },
    {
        "name": "app_upload_note",
        "method": "GET",
        "host": "https://edith.xiaohongshu.com",
        "api": "/api/media/v1/upload/capa/permit?bid=0&biz_name=&file_count=14&scene=notes_pre_post&version=1",
        "use_mobile_headers": True,
    }
]

# 加载 JS 文件
def load_js():
    js_path = os.path.join(ROOT_DIR, 'static', 'xhs_creator_xs.js')
    with open(js_path, encoding='utf-8') as f:
        return execjs.compile(f.read())

# 生成 x-s 和 x-t
def gen_sign(api, a1, data=""):
    js = load_js()
    ret = js.call('get_request_headers_params', api, data, a1)
    return ret['xs'], ret['xt']


def to_json_str(payload):
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def resolve_request_target(job):
    raw_url = job.get("url")
    if raw_url:
        parsed = urlparse(raw_url)
        api = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        return raw_url, api

    host = job.get("host", TARGET_HOST)
    api = job.get("api")
    if api:
        return f"{host}{api}", api

    path = job.get("path", "")
    if not path:
        raise ValueError("job 必须包含 url 或 host+api 或 path")
    full_url = f"{TARGET_HOST}{path}"
    return full_url, path

if __name__ == "__main__":
    # 从文件中读取 cookie
    cookie_str = ""
    cookie_file = COOKIE_FILE
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookie_str = f.read().strip()
    else:
        print(f"[ERROR] 找不到 {cookie_file} 文件！")
        exit(1)

    # 提取 a1 的值
    a1 = ""
    for item in cookie_str.split(';'):
        item = item.strip()
        if item.startswith('a1='):
            a1 = item[3:]
            break
            
    if not a1:
        print("[ERROR] Cookie 中没有提取到 a1 字段！")
        exit(1)

    results = []

    # 过滤指定的任务
    jobs_to_run = REQUEST_JOBS
    if ACTIVE_JOB_NAME:
        jobs_to_run = [job for job in REQUEST_JOBS if job.get("name") == ACTIVE_JOB_NAME]
        if not jobs_to_run:
            print(f"[WARN] 找不到名为 '{ACTIVE_JOB_NAME}' 的任务。")
            exit(0)

    for idx, job in enumerate(jobs_to_run):
        method = str(job.get("method", "GET")).upper()
        full_url, api = resolve_request_target(job)
        data_payload = to_json_str(job.get("data")) if method == "POST" else ""
        use_mobile_headers = bool(job.get("use_mobile_headers", False))

        xs, xt = "", ""
        if not use_mobile_headers:
            xs, xt = gen_sign(api, a1, data_payload)

        curl_parts = [
            f"curl -s -w \"\\n%{{http_code}}\\n\" '{full_url}'",
            f"-X {method}",
            "--compressed",
            f"-b '{cookie_str}'",
        ]

        if use_mobile_headers:
            for hk, hv in APP_UPLOAD_NOTE_MOBILE_HEADERS.items():
                esc_hv = str(hv).replace("'", "'\"'\"'")
                curl_parts.append(f"-H '{hk}: {esc_hv}'")
        else:
            curl_parts.extend([
                "-H 'accept: application/json, text/plain, */*'",
                "-H 'accept-language: zh-CN,zh;q=0.9'",
                "-H 'authorization;'",
                "-H 'cache-control: no-cache'",
                f"-H 'x-s: {xs}'",
                f"-H 'x-t: {xt}'",
                "-H 'pragma: no-cache'",
            ])

        if method == "POST" and data_payload:
            escaped_payload = data_payload.replace("'", "'\"'\"'")
            curl_parts.append("-H 'content-type: application/json;charset=UTF-8'")
            curl_parts.append(f"--data-raw '{escaped_payload}'")

        curl_cmd = " \\\n  ".join(curl_parts)

        print(f"\n[INFO] [{idx+1}/{len(jobs_to_run)}] 正在执行 {job.get('name', 'unnamed')} ({method})...")
        
        result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        http_code = lines[-1] if lines else "Unknown"
        body = '\n'.join(lines[:-1])
        
        parsed_body = body
        try:
            parsed_json = json.loads(body)
            parsed_body = parsed_json
        except json.JSONDecodeError:
            pass

        results.append({
            "name": job.get("name", f"job_{idx+1}"),
            "method": method,
            "url": full_url,
            "api": api,
            "request_data": job.get("data", ""),
            "http_code": http_code,
            "response": parsed_body
        })
        
        print(f"       状态码: {http_code}")

    # 将结果保存到文件
    output_file = OUTPUT_FILE
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
        
    print(f"\n[SUCCESS] 所有请求执行完毕！结果已保存在 {output_file} 中。")
