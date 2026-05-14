import json
from datetime import datetime, timezone

from pogo_scout.events import MonsterEvent, RaidEvent
from pogo_scout.webhook.normalizer import parse_poracle


RECEIVED_AT = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _load(fixtures_dir, name):
    return json.loads((fixtures_dir / name).read_text())


def test_poracle_monster_full(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_monster_iv_full.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert isinstance(event, MonsterEvent)
    assert event.pokemon_id == 246
    assert event.form_id is None
    assert event.iv_percent == 98.0
    assert event.cp == 612
    assert event.pvp_great_rank == 3
    assert event.pvp_ultra_rank is None
    assert event.shiny is False
    assert event.species_name == "Larvitar"
    assert event.encounter_id == "12345"


def test_poracle_monster_unencountered(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_monster_unencountered.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert event.iv_percent is None
    assert event.cp is None
    assert event.pvp_great_rank is None


def test_poracle_monster_shiny(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_monster_shiny.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert event.shiny is True


def test_poracle_monster_alolan_form(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_monster_alolan_form.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert event.form_id == 65
    assert event.species_name == "Alolan Vulpix"


def test_poracle_raid_t5(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_raid_t5.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert isinstance(event, RaidEvent)
    assert event.raid_level == 5
    assert event.boss_pokemon_id == 384
    assert event.boss_name == "Rayquaza"
    assert event.is_egg is False


def test_poracle_raid_mega_maps_to_tier_6(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_raid_mega.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert event.raid_level == 6
    assert event.boss_pokemon_id == 445


def test_poracle_raid_egg(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_raid_egg.json")
    event = parse_poracle(payload, received_at=RECEIVED_AT)
    assert event.is_egg is True
    assert event.boss_pokemon_id is None
    assert event.boss_name is None
