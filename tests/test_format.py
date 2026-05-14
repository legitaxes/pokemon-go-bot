from datetime import datetime, timedelta, timezone

from pogo_scout.events import MonsterEvent, RaidEvent
from pogo_scout.notifier.format import format_alert, format_nearby_list


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
HOME = (1.3521, 103.8198)


def _monster(**ov):
    base = dict(
        event_id="m1", pokemon_id=246, form_id=None, species_name="Larvitar",
        lat=1.3521 + 0.001, lng=103.8198, iv_percent=98.0, cp=612, level=25.0,
        pvp_great_rank=3, pvp_ultra_rank=None, shiny=False,
        despawn_at=NOW + timedelta(minutes=20), encounter_id="e1",
        received_at=NOW,
    )
    base.update(ov)
    return MonsterEvent(**base)


def _raid(**ov):
    base = dict(
        event_id="r1", gym_id="g1", gym_name="Bishan Park Gym",
        lat=1.3521, lng=103.8198, raid_level=5,
        boss_pokemon_id=384, boss_form_id=None, boss_name="Rayquaza",
        start_at=NOW, end_at=NOW + timedelta(minutes=45),
        is_shadow=False, is_egg=False, received_at=NOW,
    )
    base.update(ov)
    return RaidEvent(**base)


def test_format_alert_monster_contains_key_facts():
    out = format_alert(_monster(), match_reason="iv:98.0%", proximity_center=HOME, now=NOW)
    assert "Larvitar" in out
    assert "98" in out
    assert "612" in out
    assert "GL #3" in out
    assert "google.com/maps" in out


def test_format_alert_shiny_marker():
    out = format_alert(_monster(shiny=True), match_reason="shiny", proximity_center=HOME, now=NOW)
    assert "shiny" in out.lower() or "✨" in out


def test_format_alert_unencountered_no_iv_field():
    out = format_alert(
        _monster(iv_percent=None, cp=None, pvp_great_rank=None),
        match_reason="wanted:Larvitar", proximity_center=HOME, now=NOW,
    )
    assert "Larvitar" in out
    assert "IV" not in out


def test_format_alert_raid():
    out = format_alert(_raid(), match_reason="raid:T5 Rayquaza", proximity_center=HOME, now=NOW)
    assert "Rayquaza" in out
    assert "T5" in out
    assert "Bishan Park Gym" in out


def test_format_alert_distance_present():
    out = format_alert(_monster(), match_reason="iv:98.0%", proximity_center=HOME, now=NOW)
    assert "m" in out and ("11" in out or "12" in out)


def test_format_nearby_list_groups_by_kind():
    events = [_monster(species_name="Larvitar"), _raid(boss_name="Rayquaza")]
    out = format_nearby_list(events, proximity_center=HOME, now=NOW)
    assert "Monsters" in out
    assert "Raids" in out
    assert "Larvitar" in out
    assert "Rayquaza" in out


def test_format_nearby_list_empty_message():
    out = format_nearby_list([], proximity_center=HOME, now=NOW)
    assert "nothing" in out.lower() or "no active" in out.lower()
