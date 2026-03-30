from pathlib import Path
from playwright.sync_api import sync_playwright


USER_DATA_DIR = Path(__file__).parent / ".pw-user-data"
TARGET_URL = "https://creator.xiaohongshu.com"


with sync_playwright() as p:
    # 使用持久化用户目录，cookies/localStorage 会保留到下次运行
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
    )

    page = context.new_page()
    page.goto(TARGET_URL)
    print(page.title())

    input("按回车关闭浏览器...\n")
    context.close()
