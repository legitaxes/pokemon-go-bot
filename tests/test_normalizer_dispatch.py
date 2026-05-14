import json
from datetime import datetime, timezone

import pytest

from pogo_scout.events import MonsterEvent, RaidEvent
from pogo_scout.webhook.normalizer import detect_and_parse, NormalizerError


RECEIVED_AT = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _load(fixtures_dir, name):
    return json.loads((fixtures_dir / name).read_text())


def test_dispatches_poracle_monster(fixtures_dir):
    payload = _load(fixtures_dir, "poracle_monster_iv_full.json")
    event = detect_and_parse(payload, received_at=RECEIVED_AT)
    assert isinstance(event, MonsterEvent)
    assert event.pokemon_id == 246


def test_dispatches_pa_monster_computes_iv_from_components(fixtures_dir):
    payload = _load(fixtures_dir, "pa_monster_iv_full.json")
    event = detect_and_parse(payload, received_at=RECEIVED_AT)
    assert isinstance(event, MonsterEvent)
    assert event.iv_percent == pytest.approx((14 + 15 + 15) / 45 * 100)
    assert event.pvp_great_rank == 3


def test_dispatches_pa_raid(fixtures_dir):
    payload = _load(fixtures_dir, "pa_raid_t5.json")
    event = detect_and_parse(payload, received_at=RECEIVED_AT)
    assert isinstance(event, RaidEvent)
    assert event.raid_level == 5


def test_malformed_raises(fixtures_dir):
    payload = _load(fixtures_dir, "malformed_missing_lat.json")
    with pytest.raises(NormalizerError):
        detect_and_parse(payload, received_at=RECEIVED_AT)


def test_unknown_schema_raises():
    with pytest.raises(NormalizerError):
        detect_and_parse({"random": "shape"}, received_at=RECEIVED_AT)
