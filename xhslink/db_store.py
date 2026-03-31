import json
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "xhslink.db"
SCHEMA_PATH = BASE_DIR / "db_schema.sql"

_SCHEMA_READY = set()


def _normalize_db_path(db_path: str) -> Path:
    raw = (db_path or "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _ensure_schema(db_path: Path) -> None:
    key = str(db_path)
    if key in _SCHEMA_READY:
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()

    _SCHEMA_READY.add(key)


def _dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _base36_encode(number: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number <= 0:
        return "0"
    result = []
    n = int(number)
    while n > 0:
        n, r = divmod(n, 36)
        result.append(chars[r])
    return "".join(reversed(result))


def _load_json_text(raw: str, default):
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _get_app_config_value(conn: sqlite3.Connection, config_key: str, default_value):
    row = conn.execute(
        "SELECT config_value FROM app_config WHERE config_key = ? LIMIT 1",
        (config_key,),
    ).fetchone()
    if not row:
        return default_value
    return _load_json_text(row[0], default_value)


def _set_app_config_value(conn: sqlite3.Connection, config_key: str, value) -> None:
    now_ms = int(time.time() * 1000)
    conn.execute(
        """
        INSERT INTO app_config(config_key, config_value, updated_at_ms)
        VALUES(?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
          config_value=excluded.config_value,
          updated_at_ms=excluded.updated_at_ms
        """,
        (config_key, _dump_json(value), now_ms),
    )


def upsert_app_config(config: dict, db_path: str = "") -> None:
    now_ms = int(time.time() * 1000)
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    payload = {
        "middleBaseUrl": (config.get("middleBaseUrl") or "").strip(),
        "delaySeconds": int(config.get("delaySeconds") or 1),
        "defaultTarget": (config.get("defaultTarget") or "").strip(),
        "nextId": int(config.get("nextId") or 1),
        "totalGenerated": int(config.get("totalGenerated") or 0),
        "targetPool": config.get("targetPool") if isinstance(config.get("targetPool"), list) else [],
    }

    with sqlite3.connect(path) as conn:
        for config_key, value in payload.items():
            conn.execute(
                """
                INSERT INTO app_config(config_key, config_value, updated_at_ms)
                VALUES(?, ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET
                  config_value=excluded.config_value,
                  updated_at_ms=excluded.updated_at_ms
                """,
                (config_key, _dump_json(value), now_ms),
            )
        conn.commit()


def upsert_link_mapping(mapping: dict, db_path: str = "") -> None:
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
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
                (mapping.get("link_key") or "").strip(),
                (mapping.get("target_url") or "").strip(),
                (mapping.get("middle_url") or "").strip() or None,
                (mapping.get("short_url") or "").strip() or None,
                int(mapping.get("reuse_count") or 0),
                int(mapping.get("created_at_ms") or int(time.time() * 1000)),
                int(mapping.get("updated_at_ms") or int(time.time() * 1000)),
            ),
        )
        conn.commit()


def insert_generation_log(log_item: dict, db_path: str = "") -> None:
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO short_link_generation_log(
              link_key, target_url, middle_url, short_url, reused, created_at_ms,
              request_payload, response_payload, error_message, raw_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (log_item.get("key") or "").strip() or None,
                (log_item.get("target_url") or "").strip() or None,
                (log_item.get("middle_url") or "").strip() or None,
                (log_item.get("short_url") or "").strip() or None,
                1 if bool(log_item.get("reused")) else 0,
                int(log_item.get("created_at_ms") or int(time.time() * 1000)),
                _dump_json(log_item.get("request_payload") or {}),
                _dump_json(log_item.get("response_payload") or {}),
                (log_item.get("error_message") or "").strip() or None,
                _dump_json(log_item),
            ),
        )
        conn.commit()


def touch_generation_log_for_reuse(
    link_key: str,
    short_url: str,
    touched_at_ms: int = 0,
    db_path: str = "",
) -> bool:
    key = (link_key or "").strip()
    s_url = (short_url or "").strip()
    if not key or not s_url:
        return False

    path = _normalize_db_path(db_path)
    _ensure_schema(path)
    ts = int(touched_at_ms or int(time.time() * 1000))

    with sqlite3.connect(path) as conn:
        row = conn.execute(
            """
            SELECT id
            FROM short_link_generation_log
            WHERE link_key = ? AND short_url = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (key, s_url),
        ).fetchone()
        if not row:
            return False

        conn.execute(
            "UPDATE short_link_generation_log SET created_at_ms = ? WHERE id = ?",
            (ts, int(row[0])),
        )
        conn.commit()
        return True


def insert_middle_visit_event(event_item: dict, db_path: str = "") -> None:
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO middle_visit_event(
              event_time_ms, link_key, target_url, status, error_message, ip, user_agent, referer
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(event_item.get("timestamp_ms") or int(time.time() * 1000)),
                (event_item.get("key") or "").strip() or None,
                (event_item.get("target") or "").strip() or None,
                (event_item.get("status") or "unknown").strip() or "unknown",
                (event_item.get("error") or "").strip() or None,
                (event_item.get("ip") or "").strip() or None,
                (event_item.get("user_agent") or "").strip() or None,
                (event_item.get("referer") or "").strip() or None,
            ),
        )
        conn.commit()


def fetch_dashboard_data(db_path: str = "", history_limit: int = 200, logs_limit: int = 50) -> dict:
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row

        config_rows = conn.execute("SELECT config_key, config_value FROM app_config").fetchall()
        config_map = {
            row["config_key"]: _load_json_text(row["config_value"], None) for row in config_rows
        }

        total_generated = int(config_map.get("totalGenerated") or 0)
        mapped_url_count = int(
            conn.execute("SELECT COUNT(1) FROM link_mapping WHERE status='active'").fetchone()[0]
        )

        history_rows = conn.execute(
            """
            SELECT link_key, target_url, middle_url, short_url, created_at_ms, reused
            FROM short_link_generation_log
            ORDER BY created_at_ms DESC, id DESC
            LIMIT ?
            """,
            (int(history_limit),),
        ).fetchall()
        history = [
            {
                "key": (row["link_key"] or "").strip(),
                "target_url": (row["target_url"] or "").strip(),
                "middle_url": (row["middle_url"] or "").strip(),
                "short_url": (row["short_url"] or "").strip(),
                "created_at_ms": int(row["created_at_ms"] or 0),
                "reused": bool(row["reused"]),
            }
            for row in history_rows
        ]

        visit_rows = conn.execute(
            """
            SELECT event_time_ms, link_key, target_url, status, error_message, ip, user_agent, referer
            FROM middle_visit_event
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(logs_limit),),
        ).fetchall()
        middle_visit_logs = [
            {
                "timestamp_ms": int(row["event_time_ms"] or 0),
                "key": (row["link_key"] or "").strip(),
                "target": (row["target_url"] or "").strip(),
                "status": (row["status"] or "").strip(),
                "error": (row["error_message"] or "").strip(),
                "ip": (row["ip"] or "").strip(),
                "user_agent": (row["user_agent"] or "").strip(),
                "referer": (row["referer"] or "").strip(),
            }
            for row in visit_rows
        ]

        stats_total = int(conn.execute("SELECT COUNT(1) FROM middle_visit_event").fetchone()[0])
        stats_success = int(
            conn.execute("SELECT COUNT(1) FROM middle_visit_event WHERE status='success'").fetchone()[0]
        )
        stats_invalid_key = int(
            conn.execute("SELECT COUNT(1) FROM middle_visit_event WHERE status='invalidKey'").fetchone()[0]
        )
        stats_missing_key = int(
            conn.execute("SELECT COUNT(1) FROM middle_visit_event WHERE status='missingKey'").fetchone()[0]
        )
        stats_invalid_target = int(
            conn.execute("SELECT COUNT(1) FROM middle_visit_event WHERE status='invalidTarget'").fetchone()[0]
        )

        by_key_rows = conn.execute(
            """
            SELECT link_key, COUNT(1) AS cnt
            FROM middle_visit_event
            WHERE link_key IS NOT NULL AND link_key != ''
            GROUP BY link_key
            """
        ).fetchall()
        by_key = {(row["link_key"] or "").strip(): int(row["cnt"] or 0) for row in by_key_rows}

    return {
        "total_generated": total_generated,
        "mapped_url_count": mapped_url_count,
        "history": history,
        "middle_stats": {
            "total": stats_total,
            "success": stats_success,
            "invalidKey": stats_invalid_key,
            "missingKey": stats_missing_key,
            "invalidTarget": stats_invalid_target,
            "byKey": by_key,
        },
        "middle_visit_logs": middle_visit_logs,
    }


def fetch_target_url_by_key(link_key: str, db_path: str = "") -> str:
    key = (link_key or "").strip()
    if not key:
        return ""

    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        row = conn.execute(
            """
            SELECT target_url
            FROM link_mapping
            WHERE link_key = ? AND status = 'active'
            LIMIT 1
            """,
            (key,),
        ).fetchone()
        if row and row[0]:
            return str(row[0]).strip()

        lower_key = key.lower()
        if lower_key != key:
            row2 = conn.execute(
                """
                SELECT target_url
                FROM link_mapping
                WHERE link_key = ? AND status = 'active'
                LIMIT 1
                """,
                (lower_key,),
            ).fetchone()
            if row2 and row2[0]:
                return str(row2[0]).strip()

    return ""


def fetch_link_mapping_by_key(link_key: str, db_path: str = "") -> dict:
    key = (link_key or "").strip()
    if not key:
        return {}

    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT link_key, target_url, middle_url, short_url, reuse_count, created_at_ms, updated_at_ms
            FROM link_mapping
            WHERE link_key = ? AND status = 'active'
            LIMIT 1
            """,
            (key,),
        ).fetchone()
        if not row:
            return {}
        return {
            "link_key": (row["link_key"] or "").strip(),
            "target_url": (row["target_url"] or "").strip(),
            "middle_url": (row["middle_url"] or "").strip(),
            "short_url": (row["short_url"] or "").strip(),
            "reuse_count": int(row["reuse_count"] or 0),
            "created_at_ms": int(row["created_at_ms"] or 0),
            "updated_at_ms": int(row["updated_at_ms"] or 0),
        }


def get_or_create_link_key(target_url: str, db_path: str = "") -> tuple[str, bool]:
    target = (target_url or "").strip()
    if not target:
        return "", False

    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT link_key
            FROM link_mapping
            WHERE target_url = ? AND status = 'active'
            ORDER BY created_at_ms ASC
            LIMIT 1
            """,
            (target,),
        ).fetchone()
        if row and row[0]:
            conn.commit()
            return str(row[0]).strip(), False

        next_id = int(_get_app_config_value(conn, "nextId", 1) or 1)
        next_id = max(1, next_id)
        while True:
            candidate = _base36_encode(next_id)
            exists = conn.execute(
                "SELECT 1 FROM link_mapping WHERE link_key = ? LIMIT 1",
                (candidate,),
            ).fetchone()
            next_id += 1
            if not exists:
                break

        now_ms = int(time.time() * 1000)
        conn.execute(
            """
            INSERT INTO link_mapping(
              link_key, target_url, middle_url, short_url, status, reuse_count, created_at_ms, updated_at_ms
            )
            VALUES(?, ?, '', '', 'active', 0, ?, ?)
            """,
            (candidate, target, now_ms, now_ms),
        )
        _set_app_config_value(conn, "nextId", next_id)
        conn.commit()
        return candidate, True


def update_link_mapping_urls(
    link_key: str,
    middle_url: str = "",
    short_url: str = "",
    db_path: str = "",
) -> None:
    key = (link_key or "").strip()
    if not key:
        return

    path = _normalize_db_path(db_path)
    _ensure_schema(path)
    now_ms = int(time.time() * 1000)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            UPDATE link_mapping
            SET middle_url = CASE WHEN ? != '' THEN ? ELSE middle_url END,
                short_url = CASE WHEN ? != '' THEN ? ELSE short_url END,
                updated_at_ms = ?
            WHERE link_key = ?
            """,
            (
                (middle_url or "").strip(),
                (middle_url or "").strip(),
                (short_url or "").strip(),
                (short_url or "").strip(),
                now_ms,
                key,
            ),
        )
        conn.commit()


def increment_total_generated(db_path: str = "") -> int:
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = int(_get_app_config_value(conn, "totalGenerated", 0) or 0)
        current += 1
        _set_app_config_value(conn, "totalGenerated", current)
        conn.commit()
        return current


def get_total_generated(db_path: str = "") -> int:
    path = _normalize_db_path(db_path)
    _ensure_schema(path)

    with sqlite3.connect(path) as conn:
        return int(_get_app_config_value(conn, "totalGenerated", 0) or 0)
