PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS app_config (
  config_key TEXT PRIMARY KEY,
  config_value TEXT NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS link_mapping (
  link_key TEXT PRIMARY KEY,
  target_url TEXT NOT NULL,
  middle_url TEXT,
  short_url TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  reuse_count INTEGER NOT NULL DEFAULT 0,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_link_mapping_target_url ON link_mapping(target_url);

CREATE TABLE IF NOT EXISTS short_link_generation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  link_key TEXT,
  target_url TEXT,
  middle_url TEXT,
  short_url TEXT,
  reused INTEGER NOT NULL DEFAULT 0,
  created_at_ms INTEGER NOT NULL,
  request_payload TEXT,
  response_payload TEXT,
  error_message TEXT,
  raw_json TEXT,
  FOREIGN KEY (link_key) REFERENCES link_mapping(link_key)
);

CREATE INDEX IF NOT EXISTS idx_generation_log_created_at ON short_link_generation_log(created_at_ms);
CREATE INDEX IF NOT EXISTS idx_generation_log_key ON short_link_generation_log(link_key);

CREATE TABLE IF NOT EXISTS middle_visit_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_time_ms INTEGER NOT NULL,
  link_key TEXT,
  target_url TEXT,
  status TEXT NOT NULL,
  error_message TEXT,
  ip TEXT,
  user_agent TEXT,
  referer TEXT,
  FOREIGN KEY (link_key) REFERENCES link_mapping(link_key)
);

CREATE INDEX IF NOT EXISTS idx_middle_event_time_key ON middle_visit_event(event_time_ms, link_key);
CREATE INDEX IF NOT EXISTS idx_middle_event_status_time ON middle_visit_event(status, event_time_ms);

CREATE TABLE IF NOT EXISTS middle_visit_agg_daily (
  stat_date TEXT NOT NULL,
  link_key TEXT NOT NULL,
  total INTEGER NOT NULL DEFAULT 0,
  success INTEGER NOT NULL DEFAULT 0,
  invalid_key INTEGER NOT NULL DEFAULT 0,
  missing_key INTEGER NOT NULL DEFAULT 0,
  invalid_target INTEGER NOT NULL DEFAULT 0,
  updated_at_ms INTEGER NOT NULL,
  PRIMARY KEY (stat_date, link_key)
);
