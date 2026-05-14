from datetime import datetime, timedelta, timezone

from pogo_scout.bot.commands import cmd_nearby
from pogo_scout.db import repo
from pogo_scout.events import MonsterEvent, RaidEvent


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
HOME = (1.3521, 103.8198)


def _seed_monster(db, **ov):
    base = dict(
        event_id="m1", pokemon_id=246, form_id=None, species_name="Larvitar",
        lat=1.3521, lng=103.8198, iv_percent=98.0, cp=612, level=25.0,
        pvp_great_rank=None, pvp_ultra_rank=None, shiny=False,
        despawn_at=NOW + timedelta(minutes=20), encounter_id="e1",
        received_at=NOW,
    )
    base.update(ov)
    repo.insert_active(db, MonsterEvent(**base))


def _seed_raid(db, **ov):
    base = dict(
        event_id="r1", gym_id="g1", gym_name="Gym", lat=1.3521, lng=103.8198,
        raid_level=5, boss_pokemon_id=384, boss_form_id=None, boss_name="Rayquaza",
        start_at=NOW, end_at=NOW + timedelta(minutes=45),
        is_shadow=False, is_egg=False, received_at=NOW,
    )
    base.update(ov)
    repo.insert_active(db, RaidEvent(**base))


def _cfg(**ov):
    from types import SimpleNamespace
    base = dict(
        home_lat=HOME[0], home_lng=HOME[1], radius_m=1000,
        follow_enabled=False, follow_stale_min=10,
        live_lat=None, live_lng=None, live_location_updated_at=None,
    )
    base.update(ov)
    return SimpleNamespace(**base)


def test_nearby_empty(db):
    reply = cmd_nearby([], conn=db, config=_cfg(), now=NOW)
    assert "nothing" in reply.lower() or "no active" in reply.lower()


def test_nearby_lists_monsters_and_raids(db):
    _seed_monster(db)
    _seed_raid(db)
    reply = cmd_nearby([], conn=db, config=_cfg(), now=NOW)
    assert "Larvitar" in reply
    assert "Rayquaza" in reply


def test_nearby_filters_by_kind(db):
    _seed_monster(db)
    _seed_raid(db)
    reply = cmd_nearby(["raids"], conn=db, config=_cfg(), now=NOW)
    assert "Rayquaza" in reply
    assert "Larvitar" not in reply


def test_nearby_radius_override(db):
    _seed_monster(db, event_id="far", lat=1.36, lng=103.83)  # ~1.5km away
    reply_default = cmd_nearby([], conn=db, config=_cfg(radius_m=500), now=NOW)
    assert "Larvitar" not in reply_default
    reply_override = cmd_nearby(["2000"], conn=db, config=_cfg(radius_m=500), now=NOW)
    assert "Larvitar" in reply_override
