from datetime import datetime, timedelta, timezone

from pogo_scout.bot.commands import cmd_follow
from pogo_scout.db import repo


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def test_follow_on_sets_kv(db):
    reply = cmd_follow(["on"], conn=db, now=NOW)
    assert "on" in reply.lower() or "enabled" in reply.lower()
    assert repo.get_kv(db, "follow_enabled", default=False) is True


def test_follow_off_sets_kv(db):
    repo.set_kv(db, "follow_enabled", True)
    cmd_follow(["off"], conn=db, now=NOW)
    assert repo.get_kv(db, "follow_enabled", default=False) is False


def test_follow_status_no_location(db):
    out = cmd_follow(["status"], conn=db, now=NOW)
    assert "disabled" in out.lower() or "off" in out.lower() or "no location" in out.lower()


def test_follow_status_with_fresh_location(db):
    repo.set_kv(db, "follow_enabled", True)
    repo.set_kv(db, "live_lat", 1.3)
    repo.set_kv(db, "live_lng", 103.9)
    repo.set_kv(db, "live_location_updated_at", (NOW - timedelta(minutes=2)).isoformat())
    out = cmd_follow(["status"], conn=db, now=NOW)
    assert "2" in out
    assert "fresh" in out.lower() or "live" in out.lower()
