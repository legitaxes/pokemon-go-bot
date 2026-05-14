import sqlite3
from pathlib import Path

from pogo_scout.db.repo import init_db, schema_version


def test_init_creates_all_tables(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    init_db(conn)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert {
        "schema_version", "config_kv", "wanted_species", "raid_boss_allowlist",
        "events_active", "alerted_events", "audit_log",
    } <= names


def test_init_idempotent(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    init_db(conn)
    init_db(conn)  # second call must not raise
    assert schema_version(conn) == 1


def test_wal_mode_enabled(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
