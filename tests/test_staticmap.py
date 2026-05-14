from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pogo_scout.events import MonsterEvent
from pogo_scout.notifier import staticmap


NOW = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def _monster():
    return MonsterEvent(
        event_id="m1", pokemon_id=246, form_id=None, species_name="Larvitar",
        lat=1.3521, lng=103.8198, iv_percent=98.0, cp=612, level=25.0,
        pvp_great_rank=None, pvp_ultra_rank=None, shiny=False,
        despawn_at=NOW + timedelta(minutes=20), encounter_id="e1",
        received_at=NOW,
    )


def test_render_returns_bytes(monkeypatch):
    fake_buf_bytes = b"\x89PNG fake"

    def fake_render(self, zoom=None, center=None):
        img = MagicMock()
        def save(buf, fmt):
            buf.write(fake_buf_bytes)
        img.save = save
        return img

    monkeypatch.setattr(staticmap.StaticMap, "render", fake_render)
    out = staticmap.render_event_map(
        _monster(), proximity_center=(1.35, 103.82), zoom=16, size_px=(600, 400),
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"\x89PNG")


def test_render_returns_none_on_failure(monkeypatch):
    def boom(self):
        raise RuntimeError("tile fetch failed")
    monkeypatch.setattr(staticmap.StaticMap, "render", boom)
    out = staticmap.render_event_map(
        _monster(), proximity_center=(1.35, 103.82), zoom=16, size_px=(600, 400),
    )
    assert out is None


def test_disabled_returns_none(monkeypatch):
    out = staticmap.render_event_map(
        _monster(), proximity_center=(1.35, 103.82), zoom=16, size_px=(600, 400),
        enabled=False,
    )
    assert out is None
