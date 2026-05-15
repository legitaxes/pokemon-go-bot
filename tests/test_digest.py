from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pogo_scout.db import repo
from pogo_scout.events import MonsterEvent
from pogo_scout.notifier.digest import DigestScheduler


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
HOME = (1.3521, 103.8198)


def _cfg(**ov):
    base = dict(
        home_lat=HOME[0], home_lng=HOME[1], radius_m=2000,
        digest_interval_min=15,
        allowed_chat_ids=[123],
        follow_enabled=False, follow_stale_min=10,
        live_lat=None, live_lng=None, live_location_updated_at=None,
    )
    base.update(ov)
    return SimpleNamespace(**base)


def _seed(db, **ov):
    base = dict(
        event_id="m1", pokemon_id=246, form_id=None, species_name="Larvitar",
        lat=1.3521, lng=103.8198, iv_percent=98.0, cp=612, level=25.0,
        pvp_great_rank=None, pvp_ultra_rank=None, shiny=False,
        despawn_at=NOW + timedelta(minutes=20), encounter_id="e1",
        received_at=NOW,
    )
    base.update(ov)
    repo.insert_active(db, MonsterEvent(**base))


@pytest.mark.asyncio
async def test_digest_skipped_when_interval_zero(db):
    cfg = _cfg(digest_interval_min=0)
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    sched = DigestScheduler(conn=db, config=cfg, notifier=notifier, clock=lambda: NOW)
    await sched.tick(NOW)
    notifier.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_digest_posts_summary(db):
    _seed(db)
    cfg = _cfg()
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock(return_value=[7])
    sched = DigestScheduler(conn=db, config=cfg, notifier=notifier, clock=lambda: NOW)
    await sched.tick(NOW)
    notifier.broadcast.assert_awaited_once()
    args, kwargs = notifier.broadcast.call_args
    assert "Larvitar" in kwargs["text"]


@pytest.mark.asyncio
async def test_digest_skips_when_no_new_events(db):
    cfg = _cfg()
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock()
    sched = DigestScheduler(conn=db, config=cfg, notifier=notifier, clock=lambda: NOW)
    await sched.tick(NOW)
    notifier.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_digest_filters_out_events_older_than_last_run(db):
    # digest_interval_min=15, so since = NOW - 15min.
    # Event A was inserted 30 min ago (before last run) -> should be excluded.
    # Event B was inserted NOW -> should be included.
    _seed(db, event_id="old",
          species_name="Bulbasaur", pokemon_id=1,
          received_at=NOW - timedelta(minutes=30),
          despawn_at=NOW + timedelta(minutes=5))
    _seed(db, event_id="fresh",
          species_name="Larvitar", pokemon_id=246,
          received_at=NOW,
          despawn_at=NOW + timedelta(minutes=20))
    cfg = _cfg()
    notifier = AsyncMock()
    notifier.broadcast = AsyncMock(return_value=[7])
    sched = DigestScheduler(conn=db, config=cfg, notifier=notifier, clock=lambda: NOW)
    await sched.tick(NOW)
    notifier.broadcast.assert_awaited_once()
    text = notifier.broadcast.call_args.kwargs["text"]
    assert "Larvitar" in text
    assert "Bulbasaur" not in text
