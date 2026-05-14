from datetime import datetime, timedelta, timezone

from pogo_scout.bot.commands import cmd_mute, cmd_unmute, parse_mute_duration
from pogo_scout.db import repo


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def test_parse_duration_minutes():
    assert parse_mute_duration("30m", now=NOW) == NOW + timedelta(minutes=30)


def test_parse_duration_hours():
    assert parse_mute_duration("8h", now=NOW) == NOW + timedelta(hours=8)


def test_parse_duration_until_hhmm():
    out = parse_mute_duration("until 07:00", now=NOW)
    assert out is not None
    assert out.hour == 7
    assert out > NOW


def test_parse_duration_invalid():
    assert parse_mute_duration("forever", now=NOW) is None


def test_cmd_mute_sets_until(db):
    reply = cmd_mute(["30m"], conn=db, now=NOW)
    assert "30" in reply
    stored = repo.get_kv(db, "mute_until", default="")
    assert stored.startswith("2026-05-14T12:30")


def test_cmd_mute_invalid(db):
    reply = cmd_mute(["forever"], conn=db, now=NOW)
    assert "usage" in reply.lower()


def test_cmd_unmute_clears(db):
    repo.set_kv(db, "mute_until", "2026-05-14T13:00:00+00:00")
    reply = cmd_unmute([], conn=db)
    assert "unmuted" in reply.lower()
    assert repo.get_kv(db, "mute_until", default="") == ""
