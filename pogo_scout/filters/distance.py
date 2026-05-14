from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Protocol, Tuple

_EARTH_RADIUS_M = 6_371_000.0


class _CenterConfig(Protocol):
    home_lat: float
    home_lng: float
    follow_enabled: bool
    follow_stale_min: int
    live_lat: float | None
    live_lng: float | None
    live_location_updated_at: datetime | None


def haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lng1 = a
    lat2, lng2 = b
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    h = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * asin(sqrt(h))


def within_radius(
    a: Tuple[float, float], b: Tuple[float, float], radius_m: int
) -> bool:
    return haversine_m(a, b) <= radius_m


def proximity_center(config: _CenterConfig, now: datetime) -> Tuple[float, float]:
    if (
        config.follow_enabled
        and config.live_lat is not None
        and config.live_lng is not None
        and config.live_location_updated_at is not None
    ):
        age_s = (now - config.live_location_updated_at).total_seconds()
        if age_s <= config.follow_stale_min * 60:
            return (config.live_lat, config.live_lng)
    return (config.home_lat, config.home_lng)
