from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from pogo_scout.events import Event, MonsterEvent, RaidEvent
from pogo_scout.filters.distance import haversine_m


def _maps_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lng:.6f}"


def _apple_maps_link(lat: float, lng: float) -> str:
    return f"https://maps.apple.com/?q={lat:.6f},{lng:.6f}"


def _fmt_duration(seconds: float) -> str:
    sign = "" if seconds >= 0 else "-"
    s = int(abs(seconds))
    m, rem = divmod(s, 60)
    return f"{sign}{m}m{rem:02d}s"


def _compass_bearing(home: tuple[float, float], to: tuple[float, float]) -> str:
    from math import atan2, cos, degrees, radians, sin
    lat1, lon1 = (radians(c) for c in home)
    lat2, lon2 = (radians(c) for c in to)
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    bearing = (degrees(atan2(x, y)) + 360) % 360
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
    return dirs[int((bearing + 22.5) // 45)]


def format_alert(
    event: Event,
    *,
    match_reason: str,
    proximity_center: tuple[float, float],
    now: datetime,
) -> str:
    dist_m = haversine_m(proximity_center, (event.lat, event.lng))
    bearing = _compass_bearing(proximity_center, (event.lat, event.lng))

    if isinstance(event, MonsterEvent):
        head_bits = []
        if event.shiny:
            head_bits.append("✨ SHINY")
        if event.iv_percent is not None:
            head_bits.append(f"{event.iv_percent:.0f}%")
        head_bits.append(event.species_name)
        if event.level is not None:
            head_bits.append(f"L{event.level:g}")
        if event.cp is not None:
            head_bits.append(f"CP {event.cp}")
        header = "  ".join(head_bits)

        time_left = (event.despawn_at - now).total_seconds()
        loc = f"📍 {dist_m:.0f}m {bearing}"

        lines = [header, loc, f"⏳ despawns in {_fmt_duration(time_left)}"]

        pvp_parts = []
        if event.pvp_great_rank is not None:
            pvp_parts.append(f"GL #{event.pvp_great_rank}")
        if event.pvp_ultra_rank is not None:
            pvp_parts.append(f"UL #{event.pvp_ultra_rank}")
        if pvp_parts:
            lines.append("🥇 " + " / ".join(pvp_parts))

        lines.append(f"🗺 {_maps_link(event.lat, event.lng)}")
        lines.append(f"   {_apple_maps_link(event.lat, event.lng)}")
        lines.append(f"(matched: {match_reason})")
        return "\n".join(lines)

    if isinstance(event, RaidEvent):
        boss = event.boss_name or "Egg"
        header = f"🚨 T{event.raid_level} Raid — {boss}"
        gym = f"🏛 {event.gym_name}" if event.gym_name else ""
        loc = f"📍 {dist_m:.0f}m {bearing}"
        ends_in = (event.end_at - now).total_seconds()
        lines = [header]
        if gym:
            lines.append(gym)
        lines += [loc, f"⏳ ends in {_fmt_duration(ends_in)}"]
        lines.append(f"🗺 {_maps_link(event.lat, event.lng)}")
        lines.append(f"   {_apple_maps_link(event.lat, event.lng)}")
        lines.append(f"(matched: {match_reason})")
        return "\n".join(lines)

    raise TypeError(f"unknown event: {event!r}")


def format_nearby_list(
    events: Sequence[Event],
    *,
    proximity_center: tuple[float, float],
    now: datetime,
) -> str:
    if not events:
        return "🔭 nothing active in radius right now"

    monsters = [e for e in events if isinstance(e, MonsterEvent)]
    raids = [e for e in events if isinstance(e, RaidEvent)]

    def _mon_line(e: MonsterEvent) -> str:
        d = haversine_m(proximity_center, (e.lat, e.lng))
        b = _compass_bearing(proximity_center, (e.lat, e.lng))
        iv = f"{e.iv_percent:.0f}%" if e.iv_percent is not None else "??%"
        left = _fmt_duration((e.despawn_at - now).total_seconds())
        prefix = "✨ " if e.shiny else ""
        return f"{prefix}{iv} {e.species_name} · {d:.0f}m {b} · {left} left"

    def _raid_line(e: RaidEvent) -> str:
        d = haversine_m(proximity_center, (e.lat, e.lng))
        b = _compass_bearing(proximity_center, (e.lat, e.lng))
        boss = e.boss_name or "Egg"
        left = _fmt_duration((e.end_at - now).total_seconds())
        return f"T{e.raid_level} {boss} · {d:.0f}m {b} · ends {left}"

    parts: list[str] = []
    if monsters:
        monsters_sorted = sorted(monsters, key=lambda e: haversine_m(proximity_center, (e.lat, e.lng)))
        parts.append("🟢 Monsters")
        parts.extend(_mon_line(e) for e in monsters_sorted[:40])
    if raids:
        raids_sorted = sorted(raids, key=lambda e: haversine_m(proximity_center, (e.lat, e.lng)))
        parts.append("\n🚨 Raids")
        parts.extend(_raid_line(e) for e in raids_sorted[:40])
    return "\n".join(parts)
