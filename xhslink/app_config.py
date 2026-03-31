from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
CONFIG_PATH = ROOT_DIR / "redirect-config.json"

DEFAULT_MIDDLE_TARGET = "https://wx.cdgoufang.com/v/f/oO3LcT7R"

DEFAULT_REDIRECT_CONFIG = {
    "middleBaseUrl": "",
    "dbPath": "data/xhslink.db",
    "delaySeconds": 1,
    "defaultTarget": DEFAULT_MIDDLE_TARGET,
}
