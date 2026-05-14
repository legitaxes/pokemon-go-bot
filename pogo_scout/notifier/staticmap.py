from __future__ import annotations

import io
import logging
from typing import Tuple

from staticmap import CircleMarker, StaticMap

from pogo_scout.events import Event, MonsterEvent, RaidEvent

log = logging.getLogger(__name__)

_USER_AGENT = "pogo-scout/0.1 (+https://github.com/local/pogo-scout)"
_OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def render_event_map(
    event: Event,
    *,
    proximity_center: Tuple[float, float],
    zoom: int = 16,
    size_px: Tuple[int, int] = (600, 400),
    enabled: bool = True,
) -> bytes | None:
    """Render a PNG with a marker at the event location + a secondary marker at the
    proximity center. Returns None when disabled or on any failure (caller falls back to text)."""
    if not enabled:
        return None

    try:
        m = StaticMap(size_px[0], size_px[1], url_template=_OSM_URL, headers={"User-Agent": _USER_AGENT})
        event_color = "#e63946" if isinstance(event, MonsterEvent) else "#1d3557"
        m.add_marker(CircleMarker((event.lng, event.lat), event_color, 14))
        m.add_marker(CircleMarker((proximity_center[1], proximity_center[0]), "#2a9d8f", 8))
        img = m.render(zoom=zoom)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        log.warning("static map render failed", exc_info=True)
        return None
