import pytest

from pogo_scout.filters.raid import (
    map_raw_tier_to_level,
    raid_passes,
)


def test_tier_t5_maps_to_5():
    assert map_raw_tier_to_level("T5") == 5
    assert map_raw_tier_to_level(5) == 5


def test_tier_mega_and_elite_map_to_6():
    assert map_raw_tier_to_level("mega") == 6
    assert map_raw_tier_to_level("Elite") == 6


def test_tier_primal_maps_to_7():
    assert map_raw_tier_to_level("primal") == 7


def test_tier_unknown_raises():
    with pytest.raises(ValueError):
        map_raw_tier_to_level("foo")


def test_raid_passes_meets_floor_no_allowlist():
    assert raid_passes(raid_level=5, boss_pokemon_id=384, raid_tier_floor=5, allowlist=set()) is True


def test_raid_below_floor_fails():
    assert raid_passes(raid_level=4, boss_pokemon_id=384, raid_tier_floor=5, allowlist=set()) is False


def test_raid_at_floor_with_boss_in_allowlist():
    assert raid_passes(raid_level=6, boss_pokemon_id=445, raid_tier_floor=5, allowlist={445}) is True


def test_raid_at_floor_with_boss_not_in_allowlist():
    assert raid_passes(raid_level=6, boss_pokemon_id=149, raid_tier_floor=5, allowlist={445}) is False


def test_raid_egg_without_boss_id_fails_when_allowlist_set():
    assert raid_passes(raid_level=5, boss_pokemon_id=None, raid_tier_floor=5, allowlist={445}) is False


def test_raid_egg_passes_when_allowlist_empty():
    assert raid_passes(raid_level=5, boss_pokemon_id=None, raid_tier_floor=5, allowlist=set()) is True
