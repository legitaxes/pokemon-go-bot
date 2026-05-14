from __future__ import annotations


def pvp_passes(
    *,
    great: int | None,
    ultra: int | None,
    gl_floor: int,
    ul_floor: int,
) -> bool:
    if great is not None and great <= gl_floor:
        return True
    if ultra is not None and ultra <= ul_floor:
        return True
    return False
