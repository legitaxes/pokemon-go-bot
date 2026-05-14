from __future__ import annotations

from typing import Iterable

from pogo_scout.events import WantedSpecies


def species_matches_wanted(
    *,
    pokemon_id: int,
    form_id: int | None,
    wanted: Iterable[WantedSpecies],
) -> bool:
    for w in wanted:
        if w.pokemon_id != pokemon_id:
            continue
        if w.is_wildcard:
            return True
        if w.form_id == form_id:
            return True
    return False
