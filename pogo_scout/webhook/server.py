from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Protocol

from fastapi import FastAPI, Header, HTTPException, Request

from pogo_scout.webhook.normalizer import NormalizerError

log = logging.getLogger(__name__)


class Pipeline(Protocol):
    async def handle(self, payload: dict, *, received_at: datetime) -> None: ...


def build_app(
    *,
    secret: str,
    pipeline: Pipeline,
    health_snapshot: Callable[[], dict],
) -> FastAPI:
    app = FastAPI()

    @app.post("/webhook")
    async def receive(
        request: Request,
        x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    ):
        if x_webhook_secret != secret:
            raise HTTPException(status_code=401, detail="bad secret")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid json: {exc}") from exc
        try:
            await pipeline.handle(payload, received_at=datetime.now(timezone.utc))
        except NormalizerError as exc:
            # Spec §8.1: unknown schema returns 200 so upstream doesn't retry-storm.
            log.info("webhook unknown_schema: %s", exc)
        except Exception:
            log.exception("pipeline error — returning 200 to upstream")
        return {"ok": True}

    @app.get("/healthz")
    async def healthz():
        return health_snapshot()

    return app
