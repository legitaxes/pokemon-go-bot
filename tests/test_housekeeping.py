import shutil
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pogo_scout.db import repo
from pogo_scout.events import MonsterEvent
from pogo_scout.ops.housekeeping import Housekeeping


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _cfg(**ov):
    base = dict(
        allowed_chat_ids=[123],
        follow_enabled=False,
        follow_stale_min=10,
    )
    base.update(ov)
    return SimpleNamespace(**base)


def _seed_old(db):
    repo.insert_active(
        db,
        MonsterEvent(
            event_id="old", pokemon_id=1, form_id=None, species_name="Bulbasaur",
            lat=1.35, lng=103.82, iv_percent=10.0, cp=10, level=1.0,
            pvp_great_rank=None, pvp_ultra_rank=None, shiny=False,
            despawn_at=NOW - timedelta(hours=2),
            encounter_id="x", received_at=NOW - timedelta(hours=2),
        ),
    )


@pytest.mark.asyncio
async def test_vacuum_removes_expired_rows(db):
    _seed_old(db)
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    hk = Housekeeping(conn=db, config=_cfg(), notifier=notifier, db_path=None)
    await hk.tick(NOW)
    rows = db.execute("SELECT COUNT(*) FROM events_active").fetchone()[0]
    assert rows == 0


@pytest.mark.asyncio
async def test_disk_low_sends_critical_alert(db, tmp_path, monkeypatch):
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    hk = Housekeeping(conn=db, config=_cfg(), notifier=notifier, db_path=tmp_path / "x.db")
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda p: SimpleNamespace(total=1_000_000_000, used=950_000_000, free=50_000_000),
    )
    await hk.tick(NOW)
    notifier.broadcast.assert_awaited_once()
    args, kwargs = notifier.broadcast.call_args
    assert "disk" in kwargs["text"].lower()


@pytest.mark.asyncio
async def test_disk_low_alert_one_shot(db, tmp_path, monkeypatch):
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    hk = Housekeeping(conn=db, config=_cfg(), notifier=notifier, db_path=tmp_path / "x.db")
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda p: SimpleNamespace(total=1_000_000_000, used=950_000_000, free=50_000_000),
    )
    await hk.tick(NOW)
    await hk.tick(NOW + timedelta(hours=1))
    assert notifier.broadcast.await_count == 1


@pytest.mark.asyncio
async def test_stale_location_sends_one_shot_fallback_notice(db):
    repo.set_kv(db, "live_lat", 1.4)
    repo.set_kv(db, "live_lng", 103.9)
    repo.set_kv(db, "live_location_updated_at", (NOW - timedelta(minutes=30)).isoformat())
    repo.set_kv(db, "live_location_fallback_notified", False)
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    hk = Housekeeping(
        conn=db, config=_cfg(follow_enabled=True, follow_stale_min=10),
        notifier=notifier, db_path=None,
    )
    await hk.tick(NOW)
    notifier.broadcast.assert_awaited_once()
    assert repo.get_kv(db, "live_location_fallback_notified", default=False) is True
    await hk.tick(NOW + timedelta(minutes=5))
    assert notifier.broadcast.await_count == 1


@pytest.mark.asyncio
async def test_stale_location_skipped_when_follow_disabled(db):
    repo.set_kv(db, "live_lat", 1.4)
    repo.set_kv(db, "live_lng", 103.9)
    repo.set_kv(db, "live_location_updated_at", (NOW - timedelta(minutes=30)).isoformat())
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    hk = Housekeeping(
        conn=db, config=_cfg(follow_enabled=False), notifier=notifier, db_path=None,
    )
    await hk.tick(NOW)
    notifier.broadcast.assert_not_called()
