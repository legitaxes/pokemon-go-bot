from __future__ import annotations

from datetime import datetime
from typing import Sequence

from pogo_scout.db import repo


def handle_location_update(
    *,
    chat_id: int,
    lat: float,
    lng: float,
    now: datetime,
    allowed_chat_ids: Sequence[int],
    conn,
) -> None:
    if chat_id not in allowed_chat_ids:
        return
    repo.set_kv(conn, "live_lat", float(lat))
    repo.set_kv(conn, "live_lng", float(lng))
    repo.set_kv(conn, "live_location_updated_at", now.isoformat())
    repo.set_kv(conn, "live_location_fallback_notified", False)
