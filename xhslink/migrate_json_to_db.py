import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "redirect-config.json"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "xhslink.db"
SCHEMA_PATH = BASE_DIR / "db_schema.sql"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_schema(conn: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)


def to_json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def to_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def maybe_reset_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM middle_visit_agg_daily")
    conn.execute("DELETE FROM middle_visit_event")
    conn.execute("DELETE FROM short_link_generation_log")
    conn.execute("DELETE FROM link_mapping")
    conn.execute("DELETE FROM app_config")


def import_app_config(conn: sqlite3.Connection, config: dict, now_ms: int) -> None:
    app_config_payload = {
        "middleBaseUrl": (config.get("middleBaseUrl") or "").strip(),
        "delaySeconds": to_int(config.get("delaySeconds"), 1),
        "defaultTarget": (config.get("defaultTarget") or "").strip(),
        "nextId": to_int(config.get("nextId"), 1),
        "totalGenerated": to_int(config.get("totalGenerated"), 0),
        "targetPool": config.get("targetPool") if isinstance(config.get("targetPool"), list) else [],
    }

    for key, value in app_config_payload.items():
        conn.execute(
            """
            INSERT INTO app_config(config_key, config_value, updated_at_ms)
            VALUES(?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
              config_value=excluded.config_value,
              updated_at_ms=excluded.updated_at_ms
            """,
            (key, to_json_text(value), now_ms),
        )


def build_latest_history_by_key(history: list[dict]) -> dict:
    latest = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        key = (item.get("key") or "").strip()
        if not key:
            continue
        ts = to_int(item.get("created_at_ms"), 0)
        old = latest.get(key)
        if old is None or ts >= old["ts"]:
            latest[key] = {"item": item, "ts": ts}
    return latest


def build_reuse_count_by_key(history: list[dict]) -> dict:
    reuse_counts = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        key = (item.get("key") or "").strip()
        if not key:
            continue
        if bool(item.get("reused")):
            reuse_counts[key] = reuse_counts.get(key, 0) + 1
    return reuse_counts


def import_link_mapping(conn: sqlite3.Connection, config: dict, now_ms: int) -> None:
    key_map = config.get("keyMap") if isinstance(config.get("keyMap"), dict) else {}
    short_url_map = config.get("shortUrlMap") if isinstance(config.get("shortUrlMap"), dict) else {}
    history = config.get("history") if isinstance(config.get("history"), list) else []

    latest_history = build_latest_history_by_key(history)
    reuse_counts = build_reuse_count_by_key(history)

    for key, target_url in key_map.items():
        link_key = (key or "").strip()
        target = (target_url or "").strip()
        if not link_key or not target:
            continue

        latest = latest_history.get(link_key, {})
        latest_item = latest.get("item") if latest else {}
        created_at_ms = to_int((latest_item or {}).get("created_at_ms"), now_ms)
        middle_url = ((latest_item or {}).get("middle_url") or "").strip() or None
        short_url = (short_url_map.get(link_key) or (latest_item or {}).get("short_url") or "").strip() or None

        conn.execute(
            """
            INSERT INTO link_mapping(
              link_key, target_url, middle_url, short_url, status, reuse_count, created_at_ms, updated_at_ms
            )
            VALUES(?, ?, ?, ?, 'active', ?, ?, ?)
            ON CONFLICT(link_key) DO UPDATE SET
              target_url=excluded.target_url,
              middle_url=excluded.middle_url,
              short_url=excluded.short_url,
              reuse_count=excluded.reuse_count,
              updated_at_ms=excluded.updated_at_ms
            """,
            (
                link_key,
                target,
                middle_url,
                short_url,
                reuse_counts.get(link_key, 0),
                created_at_ms,
                now_ms,
            ),
        )


def import_generation_log(conn: sqlite3.Connection, config: dict) -> None:
    history = config.get("history") if isinstance(config.get("history"), list) else []
    for item in history:
        if not isinstance(item, dict):
            continue

        link_key = (item.get("key") or "").strip() or None
        target_url = (item.get("target_url") or "").strip() or None
        middle_url = (item.get("middle_url") or "").strip() or None
        short_url = (item.get("short_url") or "").strip() or None
        reused = 1 if bool(item.get("reused")) else 0
        created_at_ms = to_int(item.get("created_at_ms"), int(time.time() * 1000))

        conn.execute(
            """
            INSERT INTO short_link_generation_log(
              link_key, target_url, middle_url, short_url, reused, created_at_ms,
              request_payload, response_payload, error_message, raw_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_key,
                target_url,
                middle_url,
                short_url,
                reused,
                created_at_ms,
                None,
                None,
                None,
                to_json_text(item),
            ),
        )


def import_visit_events(conn: sqlite3.Connection, config: dict, now_ms: int) -> None:
    logs = config.get("middleVisitLogs") if isinstance(config.get("middleVisitLogs"), list) else []

    for item in logs:
        if not isinstance(item, dict):
            continue
        event_time_ms = to_int(item.get("timestamp_ms"), now_ms)
        link_key = (item.get("key") or "").strip() or None
        target_url = (item.get("target") or "").strip() or None
        status = (item.get("status") or "unknown").strip() or "unknown"
        error_message = (item.get("error") or "").strip() or None
        ip = (item.get("ip") or "").strip() or None
        user_agent = (item.get("user_agent") or "").strip() or None
        referer = (item.get("referer") or "").strip() or None

        conn.execute(
            """
            INSERT INTO middle_visit_event(
              event_time_ms, link_key, target_url, status, error_message, ip, user_agent, referer
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time_ms, link_key, target_url, status, error_message, ip, user_agent, referer),
        )


def import_daily_agg(conn: sqlite3.Connection, config: dict, now_ms: int) -> None:
    stats = config.get("middleStats") if isinstance(config.get("middleStats"), dict) else {}
    today = datetime.utcfromtimestamp(now_ms / 1000).strftime("%Y-%m-%d")

    conn.execute(
        """
        INSERT INTO middle_visit_agg_daily(
          stat_date, link_key, total, success, invalid_key, missing_key, invalid_target, updated_at_ms
        )
        VALUES(?, '__ALL__', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stat_date, link_key) DO UPDATE SET
          total=excluded.total,
          success=excluded.success,
          invalid_key=excluded.invalid_key,
          missing_key=excluded.missing_key,
          invalid_target=excluded.invalid_target,
          updated_at_ms=excluded.updated_at_ms
        """,
        (
            today,
            to_int(stats.get("total"), 0),
            to_int(stats.get("success"), 0),
            to_int(stats.get("invalidKey"), 0),
            to_int(stats.get("missingKey"), 0),
            to_int(stats.get("invalidTarget"), 0),
            now_ms,
        ),
    )


def migrate(config_path: Path, db_path: Path, append: bool) -> None:
    config = load_json(config_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        apply_schema(conn)

        if not append:
            maybe_reset_tables(conn)

        now_ms = int(time.time() * 1000)
        import_app_config(conn, config, now_ms)
        import_link_mapping(conn, config, now_ms)
        import_generation_log(conn, config)
        import_visit_events(conn, config, now_ms)
        import_daily_agg(conn, config, now_ms)

        conn.commit()

        mapping_count = conn.execute("SELECT COUNT(1) FROM link_mapping").fetchone()[0]
        visit_count = conn.execute("SELECT COUNT(1) FROM middle_visit_event").fetchone()[0]
        log_count = conn.execute("SELECT COUNT(1) FROM short_link_generation_log").fetchone()[0]

    print(f"Migration complete. db={db_path}")
    print(f"link_mapping={mapping_count}, short_link_generation_log={log_count}, middle_visit_event={visit_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate redirect-config.json data into SQLite database.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to redirect-config.json")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to sqlite database file")
    parser.add_argument("--append", action="store_true", help="Append mode; do not clear existing tables")
    args = parser.parse_args()

    migrate(Path(args.config), Path(args.db), args.append)


if __name__ == "__main__":
    main()
