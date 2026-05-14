from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Tuple


class PokedexLookupError(LookupError):
    pass


@lru_cache(maxsize=1)
def _load() -> dict:
    data = files("pogo_scout.data").joinpath("pokedex.json").read_text()
    return json.loads(data)


def name_for(pokemon_id: int, form_id: int | None) -> str:
    data = _load()
    species = data["species"].get(str(pokemon_id))
    if species is None:
        raise PokedexLookupError(f"Unknown pokemon_id={pokemon_id}")
    base = species["name"]
    if form_id is None:
        return base
    form_name = data["forms"].get(str(pokemon_id), {}).get(str(form_id))
    if form_name is None:
        return base
    return f"{form_name} {base}"


@lru_cache(maxsize=1)
def _name_to_id_index() -> dict[str, tuple[int, int | None]]:
    """Lower-cased display name → (pokemon_id, form_id_or_None)."""
    data = _load()
    idx: dict[str, tuple[int, int | None]] = {}
    for pid_str, entry in data["species"].items():
        pid = int(pid_str)
        idx[entry["name"].lower()] = (pid, None)
        for fid_str, form_name in data["forms"].get(pid_str, {}).items():
            display = f"{form_name} {entry['name']}".lower()
            idx[display] = (pid, int(fid_str))
    return idx


def parse_species_input(raw: str) -> Tuple[int, int | None, bool]:
    """Return (pokemon_id, form_id_or_None, is_wildcard).

    Accepts: "246", "Larvitar", "Alolan Vulpix", "Vulpix *".
    """
    text = raw.strip()
    wildcard = text.endswith("*")
    if wildcard:
        text = text[:-1].strip()

    if text.isdigit():
        pid = int(text)
        try:
            name_for(pid, None)
        except PokedexLookupError:
            raise
        return pid, None, wildcard

    key = text.lower()
    idx = _name_to_id_index()
    if key not in idx:
        raise PokedexLookupError(f"Unknown species: {raw!r}")
    pid, fid = idx[key]
    if wildcard:
        return pid, None, True
    return pid, fid, False
