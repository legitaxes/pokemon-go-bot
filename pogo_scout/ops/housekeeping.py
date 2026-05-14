from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from pogo_scout.db import repo

log = logging.getLogger(__name__)

_DISK_FLOOR_BYTES = 100 * 1024 * 1024  # 100 MB


@dataclass
class Housekeeping:
    conn: object
    config: object
    notifier: object
    db_path: Path | None
    _disk_alerted: bool = field(default=False, init=False)

    async def run_forever(self, clock: Callable[[], datetime]):
        while True:
            await asyncio.sleep(5 * 60)
            try:
                await self.tick(clock())
            except Exception:
                log.exception("housekeeping tick failed")

    async def tick(self, now: datetime) -> None:
        deleted = repo.vacuum_active(self.conn, older_than=now - timedelta(minutes=10))
        if deleted:
            log.info("vacuum removed %d expired rows", deleted)

        if self.db_path is not None:
            usage = shutil.disk_usage(self.db_path.parent if self.db_path else ".")
            if usage.free < _DISK_FLOOR_BYTES and not self._disk_alerted:
                await self.notifier.broadcast(
                    chat_ids=self.config.allowed_chat_ids,
                    text=f"⚠️ Pi disk space low: {usage.free // 1024 // 1024} MB free. Event persistence may stop.",
                    photo_bytes=None,
                )
                self._disk_alerted = True
            elif usage.free >= _DISK_FLOOR_BYTES * 2:
                self._disk_alerted = False

        if getattr(self.config, "follow_enabled", False):
            upd_iso = repo.get_kv(self.conn, "live_location_updated_at", default="")
            notified = repo.get_kv(self.conn, "live_location_fallback_notified", default=False)
            if upd_iso and not notified:
                upd = datetime.fromisoformat(upd_iso)
                age_min = (now - upd).total_seconds() / 60
                if age_min > self.config.follow_stale_min:
                    await self.notifier.broadcast(
                        chat_ids=self.config.allowed_chat_ids,
                        text="⚠️ Live location stale — falling back to home coords.",
                        photo_bytes=None,
                    )
                    repo.set_kv(self.conn, "live_location_fallback_notified", True)
