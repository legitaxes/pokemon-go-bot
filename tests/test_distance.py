from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from pogo_scout.filters.distance import (
    haversine_m,
    proximity_center,
    within_radius,
)


HOME = (1.3521, 103.8198)  # SG


def test_haversine_same_point_is_zero():
    assert haversine_m(HOME, HOME) == pytest.approx(0.0, abs=0.001)


def test_haversine_500m_north_is_about_500m():
    lat, lng = HOME
    north_500 = (lat + 500 / 111_320, lng)
    assert haversine_m(HOME, north_500) == pytest.approx(500.0, abs=2.0)


def test_within_radius_inclusive_boundary():
    assert within_radius(HOME, HOME, radius_m=0) is True


def test_within_radius_outside():
    far = (HOME[0] + 0.1, HOME[1])  # ~11 km
    assert within_radius(HOME, far, radius_m=1000) is False


def _cfg(**kwargs):
    base = dict(
        home_lat=HOME[0], home_lng=HOME[1],
        follow_enabled=False, follow_stale_min=10,
        live_lat=None, live_lng=None, live_location_updated_at=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_proximity_center_defaults_to_home():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    assert proximity_center(_cfg(), now) == HOME


def test_proximity_center_uses_live_when_fresh_and_enabled():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    cfg = _cfg(
        follow_enabled=True,
        live_lat=1.4, live_lng=103.9,
        live_location_updated_at=now - timedelta(minutes=2),
    )
    assert proximity_center(cfg, now) == (1.4, 103.9)


def test_proximity_center_falls_back_when_stale():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    cfg = _cfg(
        follow_enabled=True,
        live_lat=1.4, live_lng=103.9,
        live_location_updated_at=now - timedelta(minutes=11),
    )
    assert proximity_center(cfg, now) == HOME


def test_proximity_center_ignores_live_when_disabled():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    cfg = _cfg(
        follow_enabled=False,
        live_lat=1.4, live_lng=103.9,
        live_location_updated_at=now,
    )
    assert proximity_center(cfg, now) == HOME
