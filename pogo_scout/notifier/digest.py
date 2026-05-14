from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from pogo_scout.bot.commands import _row_to_event
from pogo_scout.db import repo
from pogo_scout.filters.distance import proximity_center, within_radius
from pogo_scout.notifier.format import format_nearby_list

log = logging.getLogger(__name__)


@dataclass
class DigestScheduler:
    conn: object
    config: object
    notifier: object
    clock: Callable[[], datetime]
    _last_run: datetime | None = field(default=None)
    _task: asyncio.Task | None = field(default=None, init=False)

    async def run_forever(self):
        while True:
            interval = max(1, getattr(self.config, "digest_interval_min", 0)) * 60
            await asyncio.sleep(interval)
            try:
                await self.tick(self.clock())
            except Exception:
                log.exception("digest tick failed")

    async def tick(self, now: datetime) -> None:
        interval = getattr(self.config, "digest_interval_min", 0)
        if interval <= 0:
            return
        since = self._last_run or (now - timedelta(minutes=interval))
        center = proximity_center(self.config, now)
        rows = repo.query_active(
            self.conn, center=center, radius_m=self.config.radius_m, now=now, kind=None,
        )
        new_rows = [r for r in rows if r["expires_at"] > since.isoformat()
                    and within_radius(center, (r["lat"], r["lng"]), self.config.radius_m)]
        if not new_rows:
            self._last_run = now
            return
        events = [_row_to_event(r) for r in new_rows]
        text = "📋 Digest:\n" + format_nearby_list(
            events, proximity_center=center, now=now,
        )
        await self.notifier.broadcast(
            chat_ids=self.config.allowed_chat_ids, text=text, photo_bytes=None,
        )
        self._last_run = now
