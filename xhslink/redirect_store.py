import copy
import json
from urllib.parse import urlsplit

from app_config import CONFIG_PATH, DEFAULT_REDIRECT_CONFIG


def is_allowed_target(target: str) -> bool:
    try:
        parsed = urlsplit(target)
    except Exception:
        return False
    return parsed.scheme in {"http", "https", "xhsdiscover"}


def load_redirect_config() -> dict:
    if not CONFIG_PATH.exists():
        return copy.deepcopy(DEFAULT_REDIRECT_CONFIG)

    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(DEFAULT_REDIRECT_CONFIG)

    config = copy.deepcopy(DEFAULT_REDIRECT_CONFIG)
    if isinstance(loaded, dict):
        config.update(loaded)

    config["middleBaseUrl"] = (config.get("middleBaseUrl") or "").strip().rstrip("/")
    config["dbPath"] = (config.get("dbPath") or "data/xhslink.db").strip()

    config["delaySeconds"] = int(config.get("delaySeconds") or 1)
    config["defaultTarget"] = (config.get("defaultTarget") or "").strip()
    return config


def save_redirect_config(config: dict) -> None:
    raise RuntimeError("redirect-config.json is read-only in DB-primary mode")
