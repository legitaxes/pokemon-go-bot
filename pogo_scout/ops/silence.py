from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from pogo_scout.db import repo

log = logging.getLogger(__name__)


@dataclass
class SilenceDetector:
    conn: object
    config: object
    notifier: object
    _alerted_at: datetime | None = field(default=None, init=False)
    _last_webhook_seen: datetime | None = field(default=None, init=False)

    async def run_forever(self, clock: Callable[[], datetime]):
        while True:
            await asyncio.sleep(10 * 60)
            try:
                await self.tick(clock())
            except Exception:
                log.exception("silence tick failed")

    async def tick(self, now: datetime) -> None:
        if not getattr(self.config, "silence_alert_enabled", True):
            return
        last = repo.get_last_webhook_received_at(self.conn)
        if last is None:
            return
        if self._last_webhook_seen != last:
            self._last_webhook_seen = last
            self._alerted_at = None
        age_min = (now - last).total_seconds() / 60
        threshold = self.config.silence_threshold_min
        if age_min < threshold:
            return
        if self._alerted_at is not None:
            return
        text = f"⚠️ No webhook received in {int(age_min)} minutes. Tunnel or upstream may be down."
        await self.notifier.broadcast(
            chat_ids=self.config.allowed_chat_ids, text=text, photo_bytes=None,
        )
        self._alerted_at = now
