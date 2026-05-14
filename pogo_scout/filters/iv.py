from __future__ import annotations


def iv_passes_floor(*, iv_percent: float | None, iv_floor: float) -> bool:
    if iv_percent is None:
        return False
    return iv_percent >= iv_floor
