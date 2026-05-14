from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Union


@dataclass(frozen=True)
class MonsterEvent:
    event_id: str
    pokemon_id: int
    form_id: int | None
    species_name: str
    lat: float
    lng: float
    iv_percent: float | None
    cp: int | None
    level: float | None
    pvp_great_rank: int | None
    pvp_ultra_rank: int | None
    shiny: bool
    despawn_at: datetime
    encounter_id: str | None
    received_at: datetime
    kind: Literal["monster"] = "monster"


@dataclass(frozen=True)
class RaidEvent:
    event_id: str
    gym_id: str
    gym_name: str
    lat: float
    lng: float
    raid_level: int
    boss_pokemon_id: int | None
    boss_form_id: int | None
    boss_name: str | None
    start_at: datetime
    end_at: datetime
    is_shadow: bool
    is_egg: bool
    received_at: datetime
    kind: Literal["raid"] = "raid"


Event = Union[MonsterEvent, RaidEvent]


@dataclass(frozen=True)
class WantedSpecies:
    pokemon_id: int
    form_id: int | None
    is_wildcard: bool
