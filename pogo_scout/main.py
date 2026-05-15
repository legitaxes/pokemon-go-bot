from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
)

from pogo_scout import __version__
from pogo_scout.bot import commands as bcmd
from pogo_scout.bot.location import handle_location_update
from pogo_scout.config import Config
from pogo_scout.db import repo
from pogo_scout.notifier.digest import DigestScheduler
from pogo_scout.notifier.staticmap import render_event_map
from pogo_scout.notifier.telegram import TelegramNotifier
from pogo_scout.ops.housekeeping import Housekeeping
from pogo_scout.ops.silence import SilenceDetector
from pogo_scout.webhook.pipeline import WebhookPipeline
from pogo_scout.webhook.server import build_app

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _NoopNotifier:
    healthy = True

    async def broadcast(self, *, chat_ids, text, photo_bytes=None):
        log.info("noop notifier swallowed: %s", text[:60])
        return [None]


@dataclass
class Components:
    config: Config
    conn: sqlite3.Connection
    notifier: object  # TelegramNotifier or _NoopNotifier
    pipeline: WebhookPipeline
    digest: DigestScheduler
    silence: SilenceDetector
    housekeeping: Housekeeping
    started_at: float
    health_snapshot: Callable[[], dict]
    tg_app: "Application | None"


def build_application(
    *,
    yaml_path: Path,
    env: dict[str, str],
    db_path: Path,
    build_telegram_app: Callable[[str], "Application | None"] | None,
):
    config = Config.load(yaml_path=yaml_path, env=env)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    repo.init_db(conn)
    config.reload_from_db(conn)

    tg_app = None
    notifier: object = _NoopNotifier()
    if build_telegram_app is not None:
        tg_app = build_telegram_app(config.telegram_bot_token)
        if tg_app is not None:
            notifier = TelegramNotifier(tg_app.bot)

    started_at = time.monotonic()

    def snapshot() -> dict:
        last = repo.get_last_webhook_received_at(conn)
        return {
            "status": "ok",
            "version": __version__,
            "uptime_s": int(time.monotonic() - started_at),
            "last_webhook_received_at": last.isoformat() if last else None,
            "last_webhook_age_s": int((_utcnow() - last).total_seconds()) if last else None,
            "telegram_healthy": getattr(notifier, "healthy", True),
            "events_active_count": conn.execute("SELECT COUNT(*) FROM events_active").fetchone()[0],
            "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        }

    if tg_app is not None:
        _register_telegram_handlers(tg_app, conn=conn, config=config, snapshot=snapshot)

    pipeline = WebhookPipeline(
        conn=conn, config=config,
        notifier=notifier,
        render_map=render_event_map,
        clock=_utcnow,
    )
    digest = DigestScheduler(
        conn=conn, config=config, notifier=notifier, clock=_utcnow,
    )
    silence = SilenceDetector(
        conn=conn, config=config, notifier=notifier,
    )
    housekeeping = Housekeeping(
        conn=conn, config=config, notifier=notifier, db_path=db_path,
    )

    app = build_app(secret=config.webhook_secret, pipeline=pipeline, health_snapshot=snapshot)
    components = Components(
        config=config, conn=conn, notifier=notifier, pipeline=pipeline,
        digest=digest, silence=silence, housekeeping=housekeeping,
        started_at=started_at, health_snapshot=snapshot, tg_app=tg_app,
    )
    return app, components


def _register_telegram_handlers(
    tg_app: "Application", *, conn, config: Config, snapshot: Callable[[], dict],
) -> None:
    def _gate(handler):
        async def wrapper(update: Update, ctx):
            if update.effective_chat.id not in config.allowed_chat_ids:
                return
            await handler(update, ctx)
        return wrapper

    async def _reply(update: Update, text: str) -> None:
        await update.effective_message.reply_text(text)

    @_gate
    async def on_wanted(update, ctx):
        await _reply(update, bcmd.cmd_wanted(ctx.args, conn=conn))
        config.reload_from_db(conn)

    @_gate
    async def on_radius(update, ctx):
        await _reply(update, bcmd.cmd_radius(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_iv(update, ctx):
        await _reply(update, bcmd.cmd_iv(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_raidtier(update, ctx):
        await _reply(update, bcmd.cmd_raidtier(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_pvprank(update, ctx):
        await _reply(update, bcmd.cmd_pvprank(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_shinyalert(update, ctx):
        await _reply(update, bcmd.cmd_shinyalert(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_mapimage(update, ctx):
        await _reply(update, bcmd.cmd_mapimage(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_silencethreshold(update, ctx):
        await _reply(update, bcmd.cmd_silencethreshold(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_silencealert(update, ctx):
        await _reply(update, bcmd.cmd_silencealert(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_raidboss(update, ctx):
        await _reply(update, bcmd.cmd_raidboss(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_mute(update, ctx):
        await _reply(update, bcmd.cmd_mute(ctx.args, conn=conn, now=_utcnow())); config.reload_from_db(conn)

    @_gate
    async def on_unmute(update, ctx):
        await _reply(update, bcmd.cmd_unmute(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_nearby(update, ctx):
        await _reply(update, bcmd.cmd_nearby(ctx.args, conn=conn, config=config, now=_utcnow()))

    @_gate
    async def on_digest(update, ctx):
        await _reply(update, bcmd.cmd_digest(ctx.args, conn=conn)); config.reload_from_db(conn)

    @_gate
    async def on_status(update, ctx):
        await _reply(update, bcmd.cmd_status(
            ctx.args, conn=conn, snapshot=snapshot(), now=_utcnow(),
        ))

    @_gate
    async def on_audit(update, ctx):
        await _reply(update, bcmd.cmd_audit(ctx.args, conn=conn))

    @_gate
    async def on_stats(update, ctx):
        await _reply(update, bcmd.cmd_stats(ctx.args, conn=conn, now=_utcnow()))

    @_gate
    async def on_follow(update, ctx):
        await _reply(update, bcmd.cmd_follow(ctx.args, conn=conn, now=_utcnow())); config.reload_from_db(conn)

    @_gate
    async def on_location(update, ctx):
        loc = update.effective_message.location if update.effective_message else None
        if loc is None:
            return
        handle_location_update(
            chat_id=update.effective_chat.id,
            lat=loc.latitude, lng=loc.longitude, now=_utcnow(),
            allowed_chat_ids=config.allowed_chat_ids, conn=conn,
        )
        config.reload_from_db(conn)

    for name, fn in [
        ("wanted", on_wanted), ("radius", on_radius), ("iv", on_iv),
        ("raidtier", on_raidtier), ("pvprank", on_pvprank),
        ("shinyalert", on_shinyalert), ("mapimage", on_mapimage),
        ("silencethreshold", on_silencethreshold), ("silencealert", on_silencealert),
        ("raidboss", on_raidboss), ("mute", on_mute), ("unmute", on_unmute),
        ("nearby", on_nearby), ("digest", on_digest), ("status", on_status),
        ("audit", on_audit), ("stats", on_stats), ("follow", on_follow),
    ]:
        tg_app.add_handler(CommandHandler(name, fn))
    tg_app.add_handler(MessageHandler(filters.LOCATION, on_location))


async def _amain():
    import uvicorn

    yaml_path = Path(os.environ.get("POGO_CONFIG_YAML", "config.yaml"))
    db_path = Path(os.environ.get("POGO_DB_PATH", "pogo_scout.db"))

    def _build_tg(token: str) -> "Application":
        return Application.builder().token(token).build()

    app, components = build_application(
        yaml_path=yaml_path, env=dict(os.environ), db_path=db_path,
        build_telegram_app=_build_tg,
    )

    digest_task = asyncio.create_task(components.digest.run_forever())
    silence_task = asyncio.create_task(components.silence.run_forever(_utcnow))
    hk_task = asyncio.create_task(components.housekeeping.run_forever(_utcnow))

    tg_app = components.tg_app
    if tg_app is not None:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        if tg_app is not None:
            await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        for t in (digest_task, silence_task, hk_task):
            t.cancel()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
