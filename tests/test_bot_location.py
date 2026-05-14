from datetime import datetime, timezone

import pytest

from pogo_scout.bot.location import handle_location_update
from pogo_scout.db import repo


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def test_stores_live_location_from_allowed_chat(db):
    handle_location_update(
        chat_id=123, lat=1.35, lng=103.82, now=NOW,
        allowed_chat_ids=[123], conn=db,
    )
    assert repo.get_kv(db, "live_lat", default=0.0) == pytest.approx(1.35)
    assert repo.get_kv(db, "live_lng", default=0.0) == pytest.approx(103.82)


def test_ignores_non_allowed_chat(db):
    handle_location_update(
        chat_id=999, lat=2.0, lng=2.0, now=NOW,
        allowed_chat_ids=[123], conn=db,
    )
    assert repo.get_kv(db, "live_lat", default=-1.0) == -1.0


def test_updates_timestamp(db):
    handle_location_update(
        chat_id=123, lat=1.35, lng=103.82, now=NOW,
        allowed_chat_ids=[123], conn=db,
    )
    stored = repo.get_kv(db, "live_location_updated_at", default="")
    assert stored.startswith("2026-05-14T12:00")


def test_resets_fallback_notified_flag(db):
    repo.set_kv(db, "live_location_fallback_notified", True)
    handle_location_update(
        chat_id=123, lat=1.35, lng=103.82, now=NOW,
        allowed_chat_ids=[123], conn=db,
    )
    assert repo.get_kv(db, "live_location_fallback_notified", default=False) is False
