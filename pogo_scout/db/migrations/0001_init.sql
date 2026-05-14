CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted_species (
    pokemon_id INTEGER NOT NULL,
    form_id INTEGER,
    is_wildcard INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    PRIMARY KEY (pokemon_id, form_id, is_wildcard)
);

CREATE TABLE IF NOT EXISTS raid_boss_allowlist (
    pokemon_id INTEGER PRIMARY KEY,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events_active (
    event_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    pokemon_or_boss_id INTEGER,
    form_id INTEGER,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    iv_percent REAL,
    cp INTEGER,
    level REAL,
    pvp_great_rank INTEGER,
    pvp_ultra_rank INTEGER,
    raid_level INTEGER,
    gym_name TEXT,
    shiny INTEGER NOT NULL DEFAULT 0,
    is_egg INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_active_expires ON events_active(expires_at);
CREATE INDEX IF NOT EXISTS idx_events_active_bbox ON events_active(lat, lng);

CREATE TABLE IF NOT EXISTS alerted_events (
    event_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    alerted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerted_at ON alerted_events(alerted_at);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    matched_by TEXT,
    telegram_message_id INTEGER,
    error TEXT,
    ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
