from datetime import datetime, timezone

from pogo_scout.config import Config
from pogo_scout.db import repo
from pogo_scout.events import WantedSpecies


ENV = {
    "TELEGRAM_BOT_TOKEN": "test-token",
    "WEBHOOK_SECRET": "shh",
    "ALLOWED_CHAT_IDS": "123,456",
}


def test_load_from_yaml_and_env(fixtures_dir):
    cfg = Config.load(yaml_path=fixtures_dir / "test_config.yaml", env=ENV)
    assert cfg.home_lat == 1.3521
    assert cfg.telegram_bot_token == "test-token"
    assert cfg.allowed_chat_ids == [123, 456]
    assert cfg.iv_floor == 90.0
    assert cfg.shiny_alert is True
    assert cfg.mute_until is None


def test_reload_from_db_overrides_kv(fixtures_dir, db):
    cfg = Config.load(yaml_path=fixtures_dir / "test_config.yaml", env=ENV)
    repo.set_kv(db, "radius_m", 800)
    repo.set_kv(db, "iv_floor", 95.5)
    repo.set_kv(db, "shiny_alert", False)
    repo.set_kv(db, "mute_until", "2026-05-14T15:00:00+00:00")
    repo.wanted_add(db, WantedSpecies(246, None, False))
    repo.raid_boss_add(db, 445)
    cfg.reload_from_db(db)
    assert cfg.radius_m == 800
    assert cfg.iv_floor == 95.5
    assert cfg.shiny_alert is False
    assert cfg.mute_until == datetime(2026, 5, 14, 15, 0, tzinfo=timezone.utc)
    assert WantedSpecies(246, None, False) in cfg.wanted_species
    assert 445 in cfg.raid_boss_allowlist


def test_invalid_chat_ids_raises(fixtures_dir):
    bad_env = dict(ENV, ALLOWED_CHAT_IDS="abc,def")
    import pytest
    with pytest.raises(ValueError):
        Config.load(yaml_path=fixtures_dir / "test_config.yaml", env=bad_env)
