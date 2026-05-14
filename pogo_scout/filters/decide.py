from __future__ import annotations

from datetime import datetime
from typing import Tuple

from pogo_scout.events import Event, MonsterEvent, RaidEvent
from pogo_scout.filters.iv import iv_passes_floor
from pogo_scout.filters.pvp import pvp_passes
from pogo_scout.filters.raid import raid_passes
from pogo_scout.filters.species import species_matches_wanted


def _is_muted(config, now: datetime) -> bool:
    mu = getattr(config, "mute_until", None)
    return mu is not None and mu > now


def should_push_alert(event: Event, config, *, now: datetime) -> Tuple[bool, str]:
    if _is_muted(config, now):
        return False, "muted"

    if isinstance(event, MonsterEvent):
        if config.shiny_alert and event.shiny:
            return True, "shiny"
        if species_matches_wanted(
            pokemon_id=event.pokemon_id,
            form_id=event.form_id,
            wanted=config.wanted_species,
        ):
            return True, f"wanted:{event.species_name}"
        if iv_passes_floor(iv_percent=event.iv_percent, iv_floor=config.iv_floor):
            return True, f"iv:{event.iv_percent:.1f}%"
        if pvp_passes(
            great=event.pvp_great_rank,
            ultra=event.pvp_ultra_rank,
            gl_floor=config.gl_rank_floor,
            ul_floor=config.ul_rank_floor,
        ):
            return True, f"pvp:GL{event.pvp_great_rank}/UL{event.pvp_ultra_rank}"
        return False, "no-match"

    if isinstance(event, RaidEvent):
        if event.raid_level < config.raid_tier_floor:
            return False, "tier-too-low"
        if not raid_passes(
            raid_level=event.raid_level,
            boss_pokemon_id=event.boss_pokemon_id,
            raid_tier_floor=config.raid_tier_floor,
            allowlist=config.raid_boss_allowlist,
        ):
            return False, "boss-not-wanted"
        boss = event.boss_name or "egg"
        return True, f"raid:T{event.raid_level} {boss}"

    raise TypeError(f"unsupported event kind: {event!r}")
