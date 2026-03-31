import execjs

from app_config import ROOT_DIR


def load_js_context():
    js_path = ROOT_DIR / "static" / "xhs_creator_xs.js"
    source = js_path.read_text(encoding="utf-8")
    return execjs.compile(source)


JS_CONTEXT = load_js_context()


def gen_sign(api: str, a1: str, data=""):
    ret = JS_CONTEXT.call("get_request_headers_params", api, data, a1)
    return ret["xs"], ret["xt"]
