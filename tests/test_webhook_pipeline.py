import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pogo_scout.db import repo
from pogo_scout.events import WantedSpecies
from pogo_scout.webhook.pipeline import WebhookPipeline


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _make_config(db):
    cfg = SimpleNamespace(
        home_lat=1.3521, home_lng=103.8198,
        radius_m=2000,
        iv_floor=90.0, raid_tier_floor=5, gl_rank_floor=0, ul_rank_floor=0,
        shiny_alert=True, mute_until=None,
        wanted_species=[], raid_boss_allowlist=set(),
        allowed_chat_ids=[123],
        map_image_enabled=False,
        map_zoom=16, map_size_px=(600, 400),
        follow_enabled=False, follow_stale_min=10,
        live_lat=None, live_lng=None, live_location_updated_at=None,
        live_location_fallback_notified=False,
    )
    return cfg


@pytest.mark.asyncio
async def test_pipeline_iv_match_dispatches(db, fixtures_dir):
    cfg = _make_config(db)
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock(return_value=[42])
    pipeline = WebhookPipeline(
        conn=db, config=cfg, notifier=notifier, render_map=lambda *a, **k: None, clock=lambda: NOW,
    )
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    await pipeline.handle(payload, received_at=NOW)
    notifier.broadcast.assert_awaited_once()
    args, kwargs = notifier.broadcast.call_args
    assert "Larvitar" in kwargs["text"]


@pytest.mark.asyncio
async def test_pipeline_no_match_no_dispatch_but_persists(db, fixtures_dir):
    cfg = _make_config(db)
    cfg.iv_floor = 99.0
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    pipeline = WebhookPipeline(
        conn=db, config=cfg, notifier=notifier, render_map=lambda *a, **k: None, clock=lambda: NOW,
    )
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    await pipeline.handle(payload, received_at=NOW)
    notifier.broadcast.assert_not_called()
    active_count = db.execute("SELECT COUNT(*) FROM events_active").fetchone()[0]
    assert active_count == 1


@pytest.mark.asyncio
async def test_pipeline_out_of_radius_drops_event(db, fixtures_dir):
    cfg = _make_config(db)
    cfg.home_lat = 35.0
    cfg.home_lng = 139.0
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    pipeline = WebhookPipeline(
        conn=db, config=cfg, notifier=notifier, render_map=lambda *a, **k: None, clock=lambda: NOW,
    )
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    await pipeline.handle(payload, received_at=NOW)
    notifier.broadcast.assert_not_called()
    count = db.execute("SELECT COUNT(*) FROM events_active").fetchone()[0]
    assert count == 0


@pytest.mark.asyncio
async def test_pipeline_dedupe_skips_repeat(db, fixtures_dir):
    cfg = _make_config(db)
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock(return_value=[42])
    pipeline = WebhookPipeline(
        conn=db, config=cfg, notifier=notifier, render_map=lambda *a, **k: None, clock=lambda: NOW,
    )
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    await pipeline.handle(payload, received_at=NOW)
    await pipeline.handle(payload, received_at=NOW + timedelta(seconds=30))
    assert notifier.broadcast.await_count == 1


@pytest.mark.asyncio
async def test_pipeline_audit_records_no_match(db, fixtures_dir):
    cfg = _make_config(db)
    cfg.iv_floor = 99.0
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    pipeline = WebhookPipeline(
        conn=db, config=cfg, notifier=notifier, render_map=lambda *a, **k: None, clock=lambda: NOW,
    )
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    await pipeline.handle(payload, received_at=NOW)
    statuses = [r[0] for r in db.execute("SELECT status FROM audit_log")]
    assert statuses == ["NO_MATCH"]


@pytest.mark.asyncio
async def test_pipeline_updates_last_webhook_timestamp(db, fixtures_dir):
    cfg = _make_config(db)
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock(return_value=[42])
    pipeline = WebhookPipeline(
        conn=db, config=cfg, notifier=notifier, render_map=lambda *a, **k: None, clock=lambda: NOW,
    )
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    await pipeline.handle(payload, received_at=NOW)
    assert repo.get_last_webhook_received_at(db) == NOW
