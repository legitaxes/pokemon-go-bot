from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

from pogo_scout.db import repo
from pogo_scout.events import Event, MonsterEvent, RaidEvent
from pogo_scout.filters.decide import should_push_alert
from pogo_scout.filters.distance import proximity_center, within_radius
from pogo_scout.notifier.format import format_alert
from pogo_scout.webhook.normalizer import detect_and_parse

log = logging.getLogger(__name__)

_DEDUPE_TTL_MONSTER = 15 * 60
_DEDUPE_TTL_RAID = 60 * 60


@dataclass
class WebhookPipeline:
    conn: object
    config: object
    notifier: object
    render_map: Callable
    clock: Callable[[], datetime]

    async def handle(self, payload: dict, *, received_at: datetime) -> None:
        repo.touch_last_webhook(self.conn, now=received_at)
        event: Event = detect_and_parse(payload, received_at=received_at)
        now = self.clock()

        ttl = _DEDUPE_TTL_MONSTER if isinstance(event, MonsterEvent) else _DEDUPE_TTL_RAID
        if repo.seen_recently(self.conn, event.event_id, ttl_seconds=ttl, now=now):
            # Exception: re-process a MonsterEvent that now has IV (previously seen without IV).
            if not (isinstance(event, MonsterEvent) and event.iv_percent is not None and
                    repo.get_active_event_iv(self.conn, event.event_id) is None):
                return

        center = proximity_center(self.config, now)
        if not within_radius(center, (event.lat, event.lng), self.config.radius_m):
            return

        repo.insert_active(self.conn, event)
        repo.mark_seen(self.conn, event.event_id, kind=event.kind, now=now)

        match, reason = should_push_alert(event, self.config, now=now)

        status = "NO_MATCH"
        matched_by = None
        message_id: int | None = None
        error: str | None = None

        if not match:
            if reason == "muted":
                status = "MUTED"
        else:
            matched_by = reason
            text = format_alert(
                event, match_reason=reason, proximity_center=center, now=now,
            )
            photo = self.render_map(
                event,
                proximity_center=center,
                zoom=self.config.map_zoom,
                size_px=self.config.map_size_px,
                enabled=self.config.map_image_enabled,
            )
            try:
                ids = await self.notifier.broadcast(
                    chat_ids=self.config.allowed_chat_ids, text=text, photo_bytes=photo,
                )
                message_id = next((i for i in ids if i is not None), None)
                status = "DISPATCHED" if message_id is not None else "FAILED"
                if status == "FAILED":
                    error = "all telegram sends returned None"
            except Exception as exc:
                status = "FAILED"
                error = f"{type(exc).__name__}: {exc}"
                log.exception("dispatch failure")

        repo.record_audit(
            self.conn,
            event_id=event.event_id,
            kind=event.kind,
            status=status,
            matched_by=matched_by,
            telegram_message_id=message_id,
            error=error,
            now=now,
        )
