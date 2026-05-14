from datetime import datetime, timedelta, timezone

from pogo_scout.bot.commands import cmd_status, cmd_audit, cmd_stats, cmd_digest
from pogo_scout.db import repo


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def test_status_returns_health_summary(db):
    repo.touch_last_webhook(db, now=NOW - timedelta(minutes=2))
    repo.set_kv(db, "radius_m", 1000)
    snapshot = {
        "uptime_s": 120,
        "telegram_healthy": True,
        "events_active_count": 5,
    }
    out = cmd_status([], conn=db, snapshot=snapshot, now=NOW)
    assert "uptime" in out.lower()
    assert "120" in out
    assert "1000" in out
    assert "ok" in out.lower() or "healthy" in out.lower()


def test_audit_returns_recent_rows(db):
    for i in range(3):
        repo.record_audit(
            db, event_id=f"e{i}", kind="monster", status="DISPATCHED",
            matched_by=f"iv:{90+i}.0%", telegram_message_id=i, error=None, now=NOW,
        )
    out = cmd_audit([], conn=db)
    assert "e0" in out and "e2" in out
    assert "DISPATCHED" in out


def test_audit_respects_limit(db):
    for i in range(10):
        repo.record_audit(
            db, event_id=f"e{i}", kind="monster", status="NO_MATCH",
            matched_by=None, telegram_message_id=None, error=None, now=NOW,
        )
    out = cmd_audit(["3"], conn=db)
    found = sum(1 for i in range(10) if f"e{i}" in out)
    assert found == 3


def test_stats_today(db):
    for status in ["DISPATCHED", "DISPATCHED", "NO_MATCH", "FAILED"]:
        repo.record_audit(
            db, event_id="x", kind="monster", status=status,
            matched_by=None, telegram_message_id=None, error=None, now=NOW,
        )
    out = cmd_stats(["today"], conn=db, now=NOW)
    assert "DISPATCHED" in out and "2" in out
    assert "FAILED" in out


def test_digest_set_interval(db):
    out = cmd_digest(["15m"], conn=db)
    assert "15" in out
    assert repo.get_kv(db, "digest_interval_min", default=0) == 15


def test_digest_off(db):
    repo.set_kv(db, "digest_interval_min", 15)
    cmd_digest(["off"], conn=db)
    assert repo.get_kv(db, "digest_interval_min", default=0) == 0
