import sqlite3
from pathlib import Path

# 默认数据库路径
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "xhslink.db"

BUSINESS_TABLES = [
    "link_mapping",
    "short_link_generation_log",
    "middle_visit_event",
    "middle_visit_agg_daily",
]

def clear_business_tables(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        for table in BUSINESS_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    clear_business_tables()
    print("已清空所有业务表数据。")
