import os
from pathlib import Path
from unittest.mock import MagicMock

from pogo_scout import main


def test_build_application_returns_components(tmp_path, monkeypatch):
    yaml = tmp_path / "config.yaml"
    yaml.write_text(
        "home_lat: 1.3521\nhome_lng: 103.8198\nradius_m: 1000\n"
        "iv_floor: 90\nraid_tier_floor: 5\ngl_rank_floor: 5\nul_rank_floor: 5\n"
        "silence_threshold_min: 45\ndigest_interval_min: 0\n"
        "map_image_enabled: true\nmap_zoom: 16\nmap_size_px: [600, 400]\n"
        "follow_stale_min: 10\n"
    )
    env = {
        "TELEGRAM_BOT_TOKEN": "t", "WEBHOOK_SECRET": "s", "ALLOWED_CHAT_IDS": "1",
    }
    db_path = tmp_path / "scout.db"
    app, components = main.build_application(
        yaml_path=yaml, env=env, db_path=db_path, build_telegram_app=lambda *a, **k: None,
    )
    assert app is not None
    assert components.config.home_lat == 1.3521
    assert components.conn is not None
    assert db_path.exists()


def test_health_snapshot_returns_keys(tmp_path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text(
        "home_lat: 1.0\nhome_lng: 1.0\n"
    )
    env = {"TELEGRAM_BOT_TOKEN": "t", "WEBHOOK_SECRET": "s", "ALLOWED_CHAT_IDS": "1"}
    _, components = main.build_application(
        yaml_path=yaml, env=env, db_path=tmp_path / "x.db",
        build_telegram_app=lambda *a, **k: None,
    )
    snap = components.health_snapshot()
    assert "status" in snap
    assert "events_active_count" in snap
    assert "telegram_healthy" in snap


def _fake_tg_app() -> MagicMock:
    app = MagicMock()
    app.bot = MagicMock()
    app.add_handler = MagicMock()
    return app


def test_build_application_exposes_tg_app_for_polling(tmp_path):
    # Regression: tg_app must be on Components so _amain can start polling.
    yaml = tmp_path / "config.yaml"
    yaml.write_text("home_lat: 1.0\nhome_lng: 1.0\n")
    env = {"TELEGRAM_BOT_TOKEN": "t", "WEBHOOK_SECRET": "s", "ALLOWED_CHAT_IDS": "1"}
    fake = _fake_tg_app()
    _, components = main.build_application(
        yaml_path=yaml, env=env, db_path=tmp_path / "x.db",
        build_telegram_app=lambda _token: fake,
    )
    assert components.tg_app is fake
    # Handlers must actually be registered against the application.
    assert fake.add_handler.call_count > 0


def test_status_handler_uses_live_snapshot_not_stub():
    # Regression: /status previously used a hardcoded {"uptime_s": 0, ...} dict
    # in the handler, so every /status reply lied about uptime/health/event count.
    # Verify the wiring module no longer contains the stub.
    import inspect
    src = inspect.getsource(main)
    assert '"uptime_s": 0' not in src, (
        "/status appears to still embed a hardcoded snapshot stub instead of calling snapshot()"
    )
    assert "snapshot=snapshot()" in src, (
        "/status handler must pass the live snapshot() result, not a literal dict"
    )
