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


from datetime import datetime, timezone
from typing import Iterable, Literal

from pogo_scout.events import MonsterEvent, RaidEvent, WantedSpecies, Event


_KV_TRUE = "1"
_KV_FALSE = "0"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(text: str | None) -> datetime | None:
    if text is None:
        return None
    return datetime.fromisoformat(text)


# ---------- dedupe ----------

def seen_recently(conn, event_id: str, *, ttl_seconds: int, now: datetime) -> bool:
    row = conn.execute(
        "SELECT alerted_at FROM alerted_events WHERE event_id = ?", (event_id,)
    ).fetchone()
    if row is None:
        return False
    alerted_at = _parse_iso(row[0])
    return (now - alerted_at).total_seconds() <= ttl_seconds


def mark_seen(conn, event_id: str, *, kind: str, now: datetime) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO alerted_events(event_id, kind, alerted_at) VALUES (?, ?, ?)",
        (event_id, kind, _iso(now)),
    )
    conn.commit()


# ---------- events_active ----------

def get_active_event_iv(conn, event_id: str) -> float | None:
    """Get the previously stored IV for an event_id, or None if not found."""
    row = conn.execute(
        "SELECT iv_percent FROM events_active WHERE event_id = ?", (event_id,)
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def insert_active(conn, event: Event) -> None:
    if isinstance(event, MonsterEvent):
        params = (
            event.event_id, "monster", event.pokemon_id, event.form_id,
            event.lat, event.lng, event.iv_percent, event.cp, event.level,
            event.pvp_great_rank, event.pvp_ultra_rank, None, None,
            int(event.shiny), 0, _iso(event.despawn_at), _iso(event.received_at),
        )
    elif isinstance(event, RaidEvent):
        params = (
            event.event_id, "raid", event.boss_pokemon_id, event.boss_form_id,
            event.lat, event.lng, None, None, None, None, None,
            event.raid_level, event.gym_name,
            0, int(event.is_egg), _iso(event.end_at), _iso(event.received_at),
        )
    else:
        raise TypeError(event)
    conn.execute(
        """
        INSERT OR IGNORE INTO events_active(
          event_id, kind, pokemon_or_boss_id, form_id, lat, lng,
          iv_percent, cp, level, pvp_great_rank, pvp_ultra_rank,
          raid_level, gym_name, shiny, is_egg, expires_at, inserted_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        params,
    )
    conn.commit()


def query_active(
    conn,
    *,
    center: tuple[float, float],
    radius_m: int,
    now: datetime,
    kind: Literal["monster", "raid"] | None,
) -> list[dict]:
    # Cheap bounding box: 1 degree ~ 111 km; over-estimate by 1.2× for safety.
    lat0, lng0 = center
    deg_lat = (radius_m / 111_320.0) * 1.2
    deg_lng = deg_lat
    sql = (
        "SELECT event_id, kind, pokemon_or_boss_id, form_id, lat, lng, "
        "iv_percent, cp, level, pvp_great_rank, pvp_ultra_rank, "
        "raid_level, gym_name, shiny, is_egg, expires_at, inserted_at "
        "FROM events_active WHERE expires_at > ? "
        "AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?"
    )
    args = [_iso(now), lat0 - deg_lat, lat0 + deg_lat, lng0 - deg_lng, lng0 + deg_lng]
    if kind is not None:
        sql += " AND kind = ?"
        args.append(kind)
    rows = conn.execute(sql, args).fetchall()
    cols = [
        "event_id", "kind", "pokemon_or_boss_id", "form_id", "lat", "lng",
        "iv_percent", "cp", "level", "pvp_great_rank", "pvp_ultra_rank",
        "raid_level", "gym_name", "shiny", "is_egg", "expires_at", "inserted_at",
    ]
    return [dict(zip(cols, r)) for r in rows]


def vacuum_active(conn, *, older_than: datetime) -> int:
    cur = conn.execute(
        "DELETE FROM events_active WHERE expires_at < ?", (_iso(older_than),)
    )
    conn.commit()
    return cur.rowcount


# ---------- config_kv ----------

def get_kv(conn, key: str, *, default):
    row = conn.execute("SELECT value FROM config_kv WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    raw = row[0]
    if isinstance(default, bool):
        return raw == _KV_TRUE
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


def set_kv(conn, key: str, value) -> None:
    if isinstance(value, bool):
        raw = _KV_TRUE if value else _KV_FALSE
    else:
        raw = str(value)
    conn.execute(
        "INSERT INTO config_kv(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, raw),
    )
    conn.commit()


def dict_kv(conn) -> dict[str, str]:
    return {k: v for k, v in conn.execute("SELECT key, value FROM config_kv")}


# ---------- wanted species ----------

def wanted_add(conn, w: WantedSpecies) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO wanted_species(pokemon_id, form_id, is_wildcard, added_at) "
        "VALUES (?, ?, ?, ?)",
        (w.pokemon_id, w.form_id, int(w.is_wildcard), _iso(datetime.now(timezone.utc))),
    )
    conn.commit()


def wanted_remove(conn, w: WantedSpecies) -> None:
    conn.execute(
        "DELETE FROM wanted_species WHERE pokemon_id = ? AND "
        "(form_id IS ? OR form_id = ?) AND is_wildcard = ?",
        (w.pokemon_id, w.form_id, w.form_id, int(w.is_wildcard)),
    )
    conn.commit()


def wanted_list(conn) -> list[WantedSpecies]:
    rows = conn.execute(
        "SELECT pokemon_id, form_id, is_wildcard FROM wanted_species"
    ).fetchall()
    return [WantedSpecies(p, f, bool(w)) for p, f, w in rows]


# ---------- raid boss allowlist ----------

def raid_boss_add(conn, pokemon_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO raid_boss_allowlist(pokemon_id, added_at) VALUES (?, ?)",
        (pokemon_id, _iso(datetime.now(timezone.utc))),
    )
    conn.commit()


def raid_boss_remove(conn, pokemon_id: int) -> None:
    conn.execute("DELETE FROM raid_boss_allowlist WHERE pokemon_id = ?", (pokemon_id,))
    conn.commit()


def raid_boss_clear(conn) -> None:
    conn.execute("DELETE FROM raid_boss_allowlist")
    conn.commit()


def raid_boss_list(conn) -> set[int]:
    rows = conn.execute("SELECT pokemon_id FROM raid_boss_allowlist").fetchall()
    return {r[0] for r in rows}


# ---------- audit log ----------

def record_audit(
    conn,
    *,
    event_id: str,
    kind: str,
    status: str,
    matched_by: str | None,
    telegram_message_id: int | None,
    error: str | None,
    now: datetime,
) -> None:
    conn.execute(
        "INSERT INTO audit_log(event_id, kind, status, matched_by, telegram_message_id, error, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_id, kind, status, matched_by, telegram_message_id, error, _iso(now)),
    )
    conn.commit()


def recent_audit(conn, limit: int) -> list[dict]:
    rows = conn.execute(
        "SELECT event_id, kind, status, matched_by, telegram_message_id, error, ts "
        "FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    cols = ["event_id", "kind", "status", "matched_by", "telegram_message_id", "error", "ts"]
    return [dict(zip(cols, r)) for r in rows]


# ---------- silence detection state ----------

_LAST_WEBHOOK_KEY = "_last_webhook_received_at"


def touch_last_webhook(conn, *, now: datetime) -> None:
    set_kv(conn, _LAST_WEBHOOK_KEY, _iso(now))


def get_last_webhook_received_at(conn) -> datetime | None:
    row = conn.execute(
        "SELECT value FROM config_kv WHERE key = ?", (_LAST_WEBHOOK_KEY,)
    ).fetchone()
    return _parse_iso(row[0]) if row else None
