from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pogo_scout.db import repo
from pogo_scout.ops.silence import SilenceDetector


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _cfg(**ov):
    base = dict(
        silence_threshold_min=45,
        silence_alert_enabled=True,
        allowed_chat_ids=[123],
    )
    base.update(ov)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_no_alert_when_fresh(db):
    repo.touch_last_webhook(db, now=NOW - timedelta(minutes=10))
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    d = SilenceDetector(conn=db, config=_cfg(), notifier=notifier)
    await d.tick(NOW)
    notifier.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_alerts_when_silence_exceeds_threshold(db):
    repo.touch_last_webhook(db, now=NOW - timedelta(minutes=50))
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    d = SilenceDetector(conn=db, config=_cfg(), notifier=notifier)
    await d.tick(NOW)
    notifier.broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_only_one_alert_per_silence_episode(db):
    repo.touch_last_webhook(db, now=NOW - timedelta(minutes=50))
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    d = SilenceDetector(conn=db, config=_cfg(), notifier=notifier)
    await d.tick(NOW)
    await d.tick(NOW + timedelta(minutes=5))
    assert notifier.broadcast.await_count == 1


@pytest.mark.asyncio
async def test_resets_after_fresh_webhook(db):
    repo.touch_last_webhook(db, now=NOW - timedelta(minutes=50))
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    d = SilenceDetector(conn=db, config=_cfg(), notifier=notifier)
    await d.tick(NOW)
    repo.touch_last_webhook(db, now=NOW + timedelta(minutes=1))
    await d.tick(NOW + timedelta(minutes=2))
    await d.tick(NOW + timedelta(minutes=60))
    assert notifier.broadcast.await_count == 2


@pytest.mark.asyncio
async def test_disabled_skips_alert(db):
    repo.touch_last_webhook(db, now=NOW - timedelta(minutes=50))
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    d = SilenceDetector(conn=db, config=_cfg(silence_alert_enabled=False), notifier=notifier)
    await d.tick(NOW)
    notifier.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_no_alert_when_never_received(db):
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    d = SilenceDetector(conn=db, config=_cfg(), notifier=notifier)
    await d.tick(NOW)
    notifier.broadcast.assert_not_called()
