from __future__ import annotations

from typing import AbstractSet, Union

_NAMED = {
    "mega": 6,
    "elite": 6,
    "primal": 7,
}


def map_raw_tier_to_level(raw: Union[int, str]) -> int:
    """Normalize a raid-tier value from various scanner schemas to 1-7."""
    if isinstance(raw, int):
        if 1 <= raw <= 7:
            return raw
        raise ValueError(f"raid tier out of range: {raw}")
    text = raw.strip().lower()
    if text.startswith("t") and text[1:].isdigit():
        n = int(text[1:])
        if 1 <= n <= 5:
            return n
    if text.isdigit():
        return map_raw_tier_to_level(int(text))
    if text in _NAMED:
        return _NAMED[text]
    raise ValueError(f"unknown raid tier: {raw!r}")


def raid_passes(
    *,
    raid_level: int,
    boss_pokemon_id: int | None,
    raid_tier_floor: int,
    allowlist: AbstractSet[int],
) -> bool:
    if raid_level < raid_tier_floor:
        return False
    if allowlist:
        if boss_pokemon_id is None:
            return False
        return boss_pokemon_id in allowlist
    return True
