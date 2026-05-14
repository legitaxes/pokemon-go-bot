from datetime import datetime, timedelta, timezone

from pogo_scout.events import MonsterEvent, RaidEvent, WantedSpecies
from pogo_scout.db import repo

NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _monster(**ov):
    base = dict(
        event_id="m1", pokemon_id=246, form_id=None, species_name="Larvitar",
        lat=1.35, lng=103.82, iv_percent=98.0, cp=400, level=20.0,
        pvp_great_rank=2, pvp_ultra_rank=None, shiny=False,
        despawn_at=NOW + timedelta(minutes=20), encounter_id="e1",
        received_at=NOW,
    )
    base.update(ov)
    return MonsterEvent(**base)


def test_dedupe_seen_recently(db):
    assert repo.seen_recently(db, "evt1", ttl_seconds=900, now=NOW) is False
    repo.mark_seen(db, "evt1", kind="monster", now=NOW)
    assert repo.seen_recently(db, "evt1", ttl_seconds=900, now=NOW) is True
    later = NOW + timedelta(seconds=901)
    assert repo.seen_recently(db, "evt1", ttl_seconds=900, now=later) is False


def test_insert_active_idempotent(db):
    repo.insert_active(db, _monster())
    repo.insert_active(db, _monster())
    rows = db.execute("SELECT COUNT(*) FROM events_active").fetchone()
    assert rows[0] == 1


def test_query_active_in_radius_bounding_box(db):
    repo.insert_active(db, _monster(event_id="near", lat=1.35, lng=103.82))
    repo.insert_active(db, _monster(event_id="far", lat=1.5, lng=104.0))
    near = repo.query_active(
        db, center=(1.35, 103.82), radius_m=1000, now=NOW, kind=None,
    )
    ids = {e["event_id"] for e in near}
    assert "near" in ids and "far" not in ids


def test_query_active_excludes_expired(db):
    repo.insert_active(db, _monster(event_id="gone", despawn_at=NOW - timedelta(minutes=1)))
    out = repo.query_active(db, center=(1.35, 103.82), radius_m=100000, now=NOW, kind=None)
    assert all(e["event_id"] != "gone" for e in out)


def test_vacuum_active_deletes_old_rows(db):
    repo.insert_active(db, _monster(event_id="old", despawn_at=NOW - timedelta(hours=2)))
    repo.insert_active(db, _monster(event_id="new", despawn_at=NOW + timedelta(minutes=20)))
    deleted = repo.vacuum_active(db, older_than=NOW - timedelta(minutes=10))
    assert deleted == 1
    remaining = [r[0] for r in db.execute("SELECT event_id FROM events_active")]
    assert remaining == ["new"]


def test_config_kv_roundtrip(db):
    assert repo.get_kv(db, "radius_m", default=1000) == 1000
    repo.set_kv(db, "radius_m", 800)
    assert repo.get_kv(db, "radius_m", default=1000) == 800
    repo.set_kv(db, "shiny_alert", False)
    assert repo.get_kv(db, "shiny_alert", default=True) is False


def test_wanted_species_add_list_remove(db):
    repo.wanted_add(db, WantedSpecies(246, None, False))
    repo.wanted_add(db, WantedSpecies(37, None, True))
    listed = repo.wanted_list(db)
    assert set(listed) == {
        WantedSpecies(246, None, False),
        WantedSpecies(37, None, True),
    }
    repo.wanted_remove(db, WantedSpecies(246, None, False))
    assert WantedSpecies(246, None, False) not in repo.wanted_list(db)


def test_raid_boss_allowlist_ops(db):
    repo.raid_boss_add(db, 445)
    repo.raid_boss_add(db, 149)
    assert repo.raid_boss_list(db) == {445, 149}
    repo.raid_boss_remove(db, 445)
    assert repo.raid_boss_list(db) == {149}
    repo.raid_boss_clear(db)
    assert repo.raid_boss_list(db) == set()


def test_audit_log_records(db):
    repo.record_audit(
        db,
        event_id="m1", kind="monster", status="DISPATCHED",
        matched_by="iv:98.0%", telegram_message_id=42, error=None,
        now=NOW,
    )
    rows = db.execute("SELECT event_id, status, matched_by FROM audit_log").fetchall()
    assert rows == [("m1", "DISPATCHED", "iv:98.0%")]


def test_last_webhook_received_at_default_none(db):
    assert repo.get_last_webhook_received_at(db) is None


def test_last_webhook_received_at_update(db):
    repo.touch_last_webhook(db, now=NOW)
    assert repo.get_last_webhook_received_at(db) == NOW
