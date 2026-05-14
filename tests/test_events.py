from datetime import datetime, timezone

from pogo_scout.events import MonsterEvent, RaidEvent, WantedSpecies


def test_monster_event_construction():
    e = MonsterEvent(
        event_id="enc:abc",
        pokemon_id=246,
        form_id=None,
        species_name="Larvitar",
        lat=1.3521,
        lng=103.8198,
        iv_percent=98.0,
        cp=512,
        level=25.0,
        pvp_great_rank=3,
        pvp_ultra_rank=None,
        shiny=False,
        despawn_at=datetime(2026, 5, 14, 13, 45, tzinfo=timezone.utc),
        encounter_id="abc",
        received_at=datetime(2026, 5, 14, 13, 20, tzinfo=timezone.utc),
    )
    assert e.kind == "monster"
    assert e.pokemon_id == 246
    assert e.iv_percent == 98.0


def test_raid_event_construction():
    e = RaidEvent(
        event_id="raid:gym1:1715690400",
        gym_id="gym1",
        gym_name="Bishan Park Gym",
        lat=1.3521,
        lng=103.8198,
        raid_level=5,
        boss_pokemon_id=384,
        boss_form_id=None,
        boss_name="Rayquaza",
        start_at=datetime(2026, 5, 14, 13, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 5, 14, 13, 45, tzinfo=timezone.utc),
        is_shadow=False,
        is_egg=False,
        received_at=datetime(2026, 5, 14, 12, 45, tzinfo=timezone.utc),
    )
    assert e.kind == "raid"
    assert e.boss_pokemon_id == 384


def test_wanted_species_equality():
    a = WantedSpecies(pokemon_id=37, form_id=None, is_wildcard=False)
    b = WantedSpecies(pokemon_id=37, form_id=None, is_wildcard=False)
    c = WantedSpecies(pokemon_id=37, form_id=None, is_wildcard=True)
    assert a == b
    assert a != c


def test_events_are_frozen():
    import dataclasses

    e = MonsterEvent(
        event_id="x", pokemon_id=1, form_id=None, species_name="Bulbasaur",
        lat=0.0, lng=0.0, iv_percent=None, cp=None, level=None,
        pvp_great_rank=None, pvp_ultra_rank=None, shiny=False,
        despawn_at=datetime.now(timezone.utc), encounter_id=None,
        received_at=datetime.now(timezone.utc),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.pokemon_id = 2  # type: ignore


import pytest  # noqa: E402
