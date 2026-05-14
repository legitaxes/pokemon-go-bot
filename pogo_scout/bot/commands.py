from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Sequence

from pogo_scout.db import repo
from pogo_scout.events import WantedSpecies
from pogo_scout.pokedex import PokedexLookupError, parse_species_input


def _parse_duration_minutes(text: str) -> int | None:
    m = re.fullmatch(r"(\d+)\s*([hm]?)", text.strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    if m.group(2) == "h":
        return n * 60
    return n


def cmd_radius(args: Sequence[str], *, conn) -> str:
    if len(args) != 1 or not args[0].isdigit():
        return "usage: /radius <meters>"
    repo.set_kv(conn, "radius_m", int(args[0]))
    return f"radius set to {args[0]}m"


def cmd_iv(args: Sequence[str], *, conn) -> str:
    if len(args) != 1:
        return "usage: /iv <percent>"
    try:
        v = float(args[0])
    except ValueError:
        return "usage: /iv <percent>"
    repo.set_kv(conn, "iv_floor", v)
    return f"IV floor set to {v:g}%"


def cmd_raidtier(args: Sequence[str], *, conn) -> str:
    if len(args) != 1 or not args[0].isdigit():
        return "usage: /raidtier <1-7>"
    n = int(args[0])
    if not 1 <= n <= 7:
        return "raid tier must be between 1 and 7"
    repo.set_kv(conn, "raid_tier_floor", n)
    return f"raid tier floor set to {n}"


def cmd_pvprank(args: Sequence[str], *, conn) -> str:
    if len(args) != 2 or args[0].lower() not in ("great", "ultra") or not args[1].isdigit():
        return "usage: /pvprank great|ultra <N>"
    league = args[0].lower()
    rank = int(args[1])
    key = "gl_rank_floor" if league == "great" else "ul_rank_floor"
    repo.set_kv(conn, key, rank)
    return f"{league} league rank floor set to {rank}"


def _toggle(args: Sequence[str], key: str, *, conn, label: str) -> str:
    if len(args) != 1 or args[0].lower() not in ("on", "off"):
        return f"usage: /{label} on|off"
    value = args[0].lower() == "on"
    repo.set_kv(conn, key, value)
    return f"{label} {'enabled' if value else 'disabled'}"


def cmd_shinyalert(args, *, conn):
    return _toggle(args, "shiny_alert", conn=conn, label="shinyalert")


def cmd_mapimage(args, *, conn):
    return _toggle(args, "map_image_enabled", conn=conn, label="mapimage")


def cmd_silencealert(args, *, conn):
    return _toggle(args, "silence_alert_enabled", conn=conn, label="silencealert")


def cmd_silencethreshold(args: Sequence[str], *, conn) -> str:
    if len(args) != 1:
        return "usage: /silencethreshold <duration> (e.g. 30m, 1h)"
    mins = _parse_duration_minutes(args[0])
    if mins is None:
        return "usage: /silencethreshold <duration>"
    repo.set_kv(conn, "silence_threshold_min", mins)
    return f"silence threshold set to {mins} minutes"


def cmd_wanted(args: Sequence[str], *, conn) -> str:
    if not args:
        return "usage: /wanted add|remove|list <species>"
    sub = args[0].lower()
    rest = " ".join(args[1:]).strip()

    if sub == "list":
        rows = repo.wanted_list(conn)
        if not rows:
            return "wanted list is empty"
        from pogo_scout.pokedex import name_for
        lines = []
        for w in rows:
            try:
                nm = name_for(w.pokemon_id, w.form_id)
            except PokedexLookupError:
                nm = f"#{w.pokemon_id}"
            suffix = " *" if w.is_wildcard else ""
            lines.append(f"- {nm}{suffix}")
        return "Wanted:\n" + "\n".join(lines)

    if sub not in ("add", "remove") or not rest:
        return "usage: /wanted add|remove <species>"

    try:
        pid, fid, wild = parse_species_input(rest)
    except PokedexLookupError:
        return f"unknown species: {rest}"

    w = WantedSpecies(pokemon_id=pid, form_id=fid, is_wildcard=wild)
    if sub == "add":
        repo.wanted_add(conn, w)
        return f"added: {rest}"
    repo.wanted_remove(conn, w)
    return f"removed: {rest}"


def parse_mute_duration(text: str, *, now: datetime) -> datetime | None:
    s = text.strip().lower()
    if s.startswith("until "):
        hhmm = s[len("until "):].replace(":", "")
        if len(hhmm) == 4 and hhmm.isdigit():
            h, mn = int(hhmm[:2]), int(hhmm[2:])
            if not (0 <= h <= 23 and 0 <= mn <= 59):
                return None
            target = now.astimezone(timezone.utc).replace(
                hour=h, minute=mn, second=0, microsecond=0
            )
            if target <= now:
                target += timedelta(days=1)
            return target
        return None
    m = re.fullmatch(r"(\d+)\s*([hm])", s)
    if not m:
        return None
    n = int(m.group(1))
    if m.group(2) == "h":
        return now + timedelta(hours=n)
    return now + timedelta(minutes=n)


def cmd_mute(args, *, conn, now: datetime) -> str:
    if not args:
        return "usage: /mute <30m|8h|until HHMM>"
    until = parse_mute_duration(" ".join(args), now=now)
    if until is None:
        return "usage: /mute <30m|8h|until HHMM>"
    repo.set_kv(conn, "mute_until", until.astimezone(timezone.utc).isoformat())
    return f"muted until {until.isoformat()}"


def cmd_unmute(args, *, conn) -> str:
    repo.set_kv(conn, "mute_until", "")
    return "unmuted"


def cmd_raidboss(args, *, conn) -> str:
    from pogo_scout.pokedex import name_for, PokedexLookupError, parse_species_input

    if not args:
        return "usage: /raidboss add|remove|list|clear <species>"
    sub = args[0].lower()
    if sub == "list":
        ids = repo.raid_boss_list(conn)
        if not ids:
            return "raid boss allowlist is empty (all bosses match)"
        names = []
        for pid in sorted(ids):
            try:
                names.append(name_for(pid, None))
            except PokedexLookupError:
                names.append(f"#{pid}")
        return "Allowed raid bosses:\n" + "\n".join(f"- {n}" for n in names)
    if sub == "clear":
        repo.raid_boss_clear(conn)
        return "raid boss allowlist cleared"
    if sub not in ("add", "remove") or len(args) < 2:
        return "usage: /raidboss add|remove|list|clear <species>"
    raw = " ".join(args[1:])
    try:
        pid, _fid, _wild = parse_species_input(raw)
    except PokedexLookupError:
        return f"unknown species: {raw}"
    if sub == "add":
        repo.raid_boss_add(conn, pid)
        return f"raid boss added: {raw}"
    repo.raid_boss_remove(conn, pid)
    return f"raid boss removed: {raw}"
