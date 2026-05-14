from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Iterable

from telegram.error import NetworkError, RetryAfter, TelegramError

log = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(
        self,
        bot,
        *,
        max_attempts: int = 3,
        backoff_sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        self._bot = bot
        self._max_attempts = max_attempts
        self._sleep = backoff_sleep or asyncio.sleep

    @property
    def healthy(self) -> bool:
        return getattr(self, "_unhealthy", False) is False

    async def send(
        self,
        *,
        chat_id: int,
        text: str,
        photo_bytes: bytes | None = None,
    ) -> int | None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                if photo_bytes is not None:
                    msg = await self._bot.send_photo(
                        chat_id=chat_id, photo=photo_bytes, caption=text[:1024]
                    )
                else:
                    msg = await self._bot.send_message(chat_id=chat_id, text=text)
                return msg.message_id
            except RetryAfter as exc:
                wait = float(exc.retry_after)
                log.warning("telegram 429, sleeping %.1fs", wait)
                await self._sleep(wait)
            except NetworkError:
                wait = 2 ** (attempt - 1)
                log.warning("telegram network error attempt=%d sleeping=%ds", attempt, wait)
                await self._sleep(wait)
            except TelegramError as exc:
                code = getattr(exc, "code", None)
                if code == 401:
                    log.critical("telegram 401 — bot token invalid")
                    self._unhealthy = True
                    return None
                log.error("telegram error: %s", exc)
                return None
        log.error("telegram dispatch failed after %d attempts", self._max_attempts)
        return None

    async def broadcast(
        self,
        *,
        chat_ids: Iterable[int],
        text: str,
        photo_bytes: bytes | None = None,
    ) -> list[int | None]:
        return [
            await self.send(chat_id=cid, text=text, photo_bytes=photo_bytes)
            for cid in chat_ids
        ]
