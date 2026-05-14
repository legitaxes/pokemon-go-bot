from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from pogo_scout.events import WantedSpecies


@dataclass
class Config:
    telegram_bot_token: str
    webhook_secret: str
    allowed_chat_ids: list[int]
    home_lat: float
    home_lng: float
    radius_m: int = 1000
    iv_floor: float = 90.0
    raid_tier_floor: int = 5
    gl_rank_floor: int = 5
    ul_rank_floor: int = 5
    silence_threshold_min: int = 45
    digest_interval_min: int = 0
    map_image_enabled: bool = True
    map_zoom: int = 16
    map_size_px: tuple[int, int] = (600, 400)
    follow_stale_min: int = 10
    shiny_alert: bool = True
    silence_alert_enabled: bool = True
    follow_enabled: bool = False
    mute_until: datetime | None = None
    live_lat: float | None = None
    live_lng: float | None = None
    live_location_updated_at: datetime | None = None
    live_location_fallback_notified: bool = False
    wanted_species: list[WantedSpecies] = field(default_factory=list)
    raid_boss_allowlist: set[int] = field(default_factory=set)

    @classmethod
    def load(cls, *, yaml_path: Path, env: dict[str, str]) -> "Config":
        data = yaml.safe_load(Path(yaml_path).read_text())
        try:
            chat_ids = [int(s.strip()) for s in env["ALLOWED_CHAT_IDS"].split(",") if s.strip()]
        except ValueError as exc:
            raise ValueError(f"ALLOWED_CHAT_IDS must be comma-separated ints: {exc}") from exc
        return cls(
            telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
            webhook_secret=env["WEBHOOK_SECRET"],
            allowed_chat_ids=chat_ids,
            home_lat=float(data["home_lat"]),
            home_lng=float(data["home_lng"]),
            radius_m=int(data.get("radius_m", 1000)),
            iv_floor=float(data.get("iv_floor", 90.0)),
            raid_tier_floor=int(data.get("raid_tier_floor", 5)),
            gl_rank_floor=int(data.get("gl_rank_floor", 5)),
            ul_rank_floor=int(data.get("ul_rank_floor", 5)),
            silence_threshold_min=int(data.get("silence_threshold_min", 45)),
            digest_interval_min=int(data.get("digest_interval_min", 0)),
            map_image_enabled=bool(data.get("map_image_enabled", True)),
            map_zoom=int(data.get("map_zoom", 16)),
            map_size_px=tuple(data.get("map_size_px", [600, 400])),
            follow_stale_min=int(data.get("follow_stale_min", 10)),
        )

    def reload_from_db(self, conn) -> None:
        from pogo_scout.db import repo

        kv = repo.dict_kv(conn)
        for key, attr, caster in [
            ("radius_m", "radius_m", int),
            ("iv_floor", "iv_floor", float),
            ("raid_tier_floor", "raid_tier_floor", int),
            ("gl_rank_floor", "gl_rank_floor", int),
            ("ul_rank_floor", "ul_rank_floor", int),
            ("silence_threshold_min", "silence_threshold_min", int),
            ("digest_interval_min", "digest_interval_min", int),
            ("map_zoom", "map_zoom", int),
            ("follow_stale_min", "follow_stale_min", int),
            ("live_lat", "live_lat", float),
            ("live_lng", "live_lng", float),
        ]:
            if key in kv:
                setattr(self, attr, caster(kv[key]))
        for key, attr in [
            ("shiny_alert", "shiny_alert"),
            ("silence_alert_enabled", "silence_alert_enabled"),
            ("follow_enabled", "follow_enabled"),
            ("map_image_enabled", "map_image_enabled"),
            ("live_location_fallback_notified", "live_location_fallback_notified"),
        ]:
            if key in kv:
                setattr(self, attr, kv[key] == "1")
        for key, attr in [
            ("mute_until", "mute_until"),
            ("live_location_updated_at", "live_location_updated_at"),
        ]:
            if key in kv and kv[key]:
                setattr(self, attr, datetime.fromisoformat(kv[key]))
            else:
                setattr(self, attr, None)
        self.wanted_species = repo.wanted_list(conn)
        self.raid_boss_allowlist = repo.raid_boss_list(conn)
