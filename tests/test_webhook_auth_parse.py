import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pogo_scout.webhook.server import build_app


class FakePipeline:
    """Captures parsed events without doing dispatch."""
    def __init__(self):
        self.events = []
        self.received_at: datetime | None = None

    async def handle(self, payload, *, received_at):
        from pogo_scout.webhook.normalizer import detect_and_parse
        event = detect_and_parse(payload, received_at=received_at)
        self.events.append(event)
        self.received_at = received_at


@pytest.fixture
def pipeline():
    return FakePipeline()


@pytest.fixture
def client(pipeline):
    app = build_app(secret="shh", pipeline=pipeline, health_snapshot=lambda: {"status": "ok"})
    return TestClient(app)


def test_post_webhook_rejects_missing_secret(client, fixtures_dir):
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    r = client.post("/webhook", json=payload)
    assert r.status_code == 401


def test_post_webhook_rejects_wrong_secret(client, fixtures_dir):
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    r = client.post("/webhook", json=payload, headers={"X-Webhook-Secret": "nope"})
    assert r.status_code == 401


def test_post_webhook_accepts_poracle(client, pipeline, fixtures_dir):
    payload = json.loads((fixtures_dir / "poracle_monster_iv_full.json").read_text())
    r = client.post("/webhook", json=payload, headers={"X-Webhook-Secret": "shh"})
    assert r.status_code == 200
    assert len(pipeline.events) == 1
    assert pipeline.events[0].pokemon_id == 246


def test_post_webhook_unknown_schema_returns_200(client, pipeline):
    # Spec §8.1: unknown schema is 200 (no upstream retry storm). The event isn't processed.
    r = client.post("/webhook", json={"random": "garbage"}, headers={"X-Webhook-Secret": "shh"})
    assert r.status_code == 200
    assert pipeline.events == []


def test_post_webhook_invalid_json_returns_400(client):
    r = client.post(
        "/webhook",
        content=b"not-json{",
        headers={"X-Webhook-Secret": "shh", "Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_get_healthz_returns_snapshot(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
