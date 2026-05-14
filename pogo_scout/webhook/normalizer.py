from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pogo_scout.events import Event, MonsterEvent, RaidEvent
from pogo_scout.filters.raid import map_raw_tier_to_level
from pogo_scout.pokedex import name_for, PokedexLookupError


class NormalizerError(ValueError):
    pass


def _form_or_none(form: int | None) -> int | None:
    if form in (0, None):
        return None
    return int(form)


def _ts(unix: int | float) -> datetime:
    return datetime.fromtimestamp(int(unix), tz=timezone.utc)


def _best_pvp_rank(rankings: list[dict] | None) -> int | None:
    if not rankings:
        return None
    ranks = [r.get("rank") for r in rankings if isinstance(r.get("rank"), int)]
    return min(ranks) if ranks else None


def parse_poracle(payload: dict, *, received_at: datetime) -> Event:
    kind = payload.get("type")
    msg = payload.get("message")
    if not isinstance(msg, dict):
        raise NormalizerError("missing or invalid 'message'")

    if kind == "monster":
        return _parse_poracle_monster(msg, received_at=received_at)
    if kind == "raid":
        return _parse_poracle_raid(msg, received_at=received_at)
    raise NormalizerError(f"unsupported poracle type: {kind!r}")


def _parse_poracle_monster(msg: dict, *, received_at: datetime) -> MonsterEvent:
    try:
        pokemon_id = int(msg["pokemon_id"])
        lat = float(msg["latitude"])
        lng = float(msg["longitude"])
        disappear = int(msg["disappear_time"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NormalizerError(f"poracle monster missing fields: {exc}") from exc

    form_id = _form_or_none(msg.get("form"))
    try:
        species_name = name_for(pokemon_id, form_id)
    except PokedexLookupError:
        species_name = f"#{pokemon_id}"

    iv_pct: float | None = None
    if "iv" in msg and msg["iv"] is not None:
        iv_pct = float(msg["iv"])
    elif all(k in msg for k in ("individual_attack", "individual_defense", "individual_stamina")):
        atk = int(msg["individual_attack"])
        df = int(msg["individual_defense"])
        sta = int(msg["individual_stamina"])
        iv_pct = (atk + df + sta) / 45.0 * 100.0

    encounter_id = str(msg.get("encounter_id")) if msg.get("encounter_id") is not None else None
    event_id = f"enc:{encounter_id}" if encounter_id else f"spawn:{msg.get('spawnpoint_id')}:{disappear}"

    return MonsterEvent(
        event_id=event_id,
        pokemon_id=pokemon_id,
        form_id=form_id,
        species_name=species_name,
        lat=lat,
        lng=lng,
        iv_percent=iv_pct,
        cp=int(msg["cp"]) if msg.get("cp") is not None else None,
        level=float(msg["pokemon_level"]) if msg.get("pokemon_level") is not None else None,
        pvp_great_rank=_best_pvp_rank(msg.get("pvp_rankings_great_league")),
        pvp_ultra_rank=_best_pvp_rank(msg.get("pvp_rankings_ultra_league")),
        shiny=bool(msg.get("shiny", False)),
        despawn_at=_ts(disappear),
        encounter_id=encounter_id,
        received_at=received_at,
    )


def _parse_poracle_raid(msg: dict, *, received_at: datetime) -> RaidEvent:
    try:
        gym_id = str(msg["gym_id"])
        lat = float(msg["latitude"])
        lng = float(msg["longitude"])
        start = int(msg["start"])
        end = int(msg["end"])
        raw_level = msg["level"]
    except (KeyError, TypeError, ValueError) as exc:
        raise NormalizerError(f"poracle raid missing fields: {exc}") from exc

    raid_level = map_raw_tier_to_level(raw_level)
    boss_raw = msg.get("pokemon_id")
    is_egg = boss_raw in (0, None)
    boss_id = None if is_egg else int(boss_raw)
    boss_form = _form_or_none(msg.get("form")) if not is_egg else None
    boss_name: str | None = None
    if boss_id is not None:
        try:
            boss_name = name_for(boss_id, boss_form)
        except PokedexLookupError:
            boss_name = f"#{boss_id}"

    return RaidEvent(
        event_id=f"raid:{gym_id}:{start}",
        gym_id=gym_id,
        gym_name=str(msg.get("gym_name", "")),
        lat=lat,
        lng=lng,
        raid_level=raid_level,
        boss_pokemon_id=boss_id,
        boss_form_id=boss_form,
        boss_name=boss_name,
        start_at=_ts(start),
        end_at=_ts(end),
        is_shadow=bool(msg.get("shadow", False)),
        is_egg=is_egg,
        received_at=received_at,
    )
