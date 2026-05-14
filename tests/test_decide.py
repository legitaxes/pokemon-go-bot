from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from pogo_scout.events import MonsterEvent, RaidEvent, WantedSpecies
from pogo_scout.filters.decide import should_push_alert


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _cfg(**kwargs) -> SimpleNamespace:
    base = dict(
        iv_floor=90.0,
        raid_tier_floor=5,
        gl_rank_floor=5,
        ul_rank_floor=5,
        shiny_alert=True,
        mute_until=None,
        wanted_species=[],
        raid_boss_allowlist=set(),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _monster(**overrides) -> MonsterEvent:
    base = dict(
        event_id="m1", pokemon_id=246, form_id=None, species_name="Larvitar",
        lat=1.35, lng=103.82, iv_percent=80.0, cp=400, level=20.0,
        pvp_great_rank=None, pvp_ultra_rank=None, shiny=False,
        despawn_at=NOW + timedelta(minutes=20), encounter_id="e1",
        received_at=NOW,
    )
    base.update(overrides)
    return MonsterEvent(**base)


def _raid(**overrides) -> RaidEvent:
    base = dict(
        event_id="r1", gym_id="g1", gym_name="Gym", lat=1.35, lng=103.82,
        raid_level=5, boss_pokemon_id=384, boss_form_id=None, boss_name="Rayquaza",
        start_at=NOW, end_at=NOW + timedelta(minutes=45),
        is_shadow=False, is_egg=False, received_at=NOW,
    )
    base.update(overrides)
    return RaidEvent(**base)


def test_mute_short_circuits_all_filters():
    match, reason = should_push_alert(
        _monster(iv_percent=100.0),
        _cfg(mute_until=NOW + timedelta(hours=1)),
        now=NOW,
    )
    assert match is False
    assert reason == "muted"


def test_shiny_overrides_low_iv():
    match, reason = should_push_alert(
        _monster(iv_percent=10.0, shiny=True), _cfg(), now=NOW
    )
    assert match is True
    assert reason == "shiny"


def test_wanted_species_matches_unencountered():
    cfg = _cfg(wanted_species=[WantedSpecies(246, None, False)])
    match, reason = should_push_alert(
        _monster(iv_percent=None), cfg, now=NOW
    )
    assert match is True
    assert reason.startswith("wanted:")


def test_iv_floor_passes():
    match, reason = should_push_alert(_monster(iv_percent=98.0), _cfg(), now=NOW)
    assert match is True
    assert "iv:" in reason


def test_pvp_great_passes():
    match, reason = should_push_alert(
        _monster(iv_percent=50.0, pvp_great_rank=2), _cfg(), now=NOW
    )
    assert match is True
    assert "pvp:" in reason


def test_no_monster_match_returns_no_match():
    match, reason = should_push_alert(_monster(iv_percent=50.0), _cfg(), now=NOW)
    assert match is False
    assert reason == "no-match"


def test_raid_below_floor_rejected():
    match, reason = should_push_alert(_raid(raid_level=3), _cfg(), now=NOW)
    assert match is False
    assert reason == "tier-too-low"


def test_raid_boss_allowlist_rejects_other_bosses():
    cfg = _cfg(raid_boss_allowlist={445})
    match, reason = should_push_alert(_raid(boss_pokemon_id=149), cfg, now=NOW)
    assert match is False
    assert reason == "boss-not-wanted"


def test_raid_match_returns_descriptive_reason():
    match, reason = should_push_alert(_raid(raid_level=6, boss_pokemon_id=445, boss_name="Garchomp"), _cfg(), now=NOW)
    assert match is True
    assert "Garchomp" in reason
