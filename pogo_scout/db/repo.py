from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from importlib.resources import files


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    current = schema_version(conn) if _has_schema_version(conn) else 0
    migrations_dir = files("pogo_scout.db.migrations")
    available = sorted(p.name for p in migrations_dir.iterdir() if p.name.endswith(".sql"))
    for fname in available:
        version = int(fname.split("_", 1)[0])
        if version <= current:
            continue
        sql = migrations_dir.joinpath(fname).read_text()
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
            (version, _now_iso()),
        )
    conn.commit()


def _has_schema_version(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    return row is not None


def schema_version(conn: sqlite3.Connection) -> int:
    if not _has_schema_version(conn):
        return 0
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] or 0
