import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pogo_scout.notifier.telegram import TelegramNotifier


@pytest.mark.asyncio
async def test_send_text_calls_send_message():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
    n = TelegramNotifier(bot)
    msg_id = await n.send(chat_id=999, text="hello")
    assert msg_id == 42
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_with_photo_uses_send_photo():
    bot = MagicMock()
    bot.send_photo = AsyncMock(return_value=MagicMock(message_id=43))
    n = TelegramNotifier(bot)
    msg_id = await n.send(chat_id=999, text="caption", photo_bytes=b"\x89PNG...")
    assert msg_id == 43
    bot.send_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_retries_on_transient_error():
    from telegram.error import NetworkError
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[NetworkError("x"), NetworkError("x"), MagicMock(message_id=7)])
    n = TelegramNotifier(bot, backoff_sleep=AsyncMock())
    msg_id = await n.send(chat_id=1, text="x")
    assert msg_id == 7
    assert bot.send_message.await_count == 3


@pytest.mark.asyncio
async def test_send_returns_none_after_final_failure():
    from telegram.error import NetworkError
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=NetworkError("boom"))
    n = TelegramNotifier(bot, backoff_sleep=AsyncMock())
    out = await n.send(chat_id=1, text="x")
    assert out is None
    assert bot.send_message.await_count == 3


@pytest.mark.asyncio
async def test_429_respects_retry_after():
    from telegram.error import RetryAfter
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[RetryAfter(2.0), MagicMock(message_id=8)])
    sleep = AsyncMock()
    n = TelegramNotifier(bot, backoff_sleep=sleep)
    msg_id = await n.send(chat_id=1, text="x")
    assert msg_id == 8
    sleep.assert_any_await(2.0)
