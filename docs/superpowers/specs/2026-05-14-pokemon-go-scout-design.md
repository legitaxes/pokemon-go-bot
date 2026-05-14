# Pokémon Go Scout — Design Spec

**Date:** 2026-05-14
**Status:** Draft for user review
**Target deployment:** Raspberry Pi / home server, Singapore

---

## 1. Goal

Build a personal Pokémon Go scout bot that:

- Receives spawn and raid events for the Singapore region via webhook (Poracle / PokéAlarm protocol) from a community scanner.
- Filters events down to those the user cares about (within a fixed home radius, matching wanted species / IV floor / raid tier / PvP rank).
- Pushes matching alerts to the user via a Telegram bot.
- Also supports a "scout mode": on-demand `/nearby` queries and a periodic digest that show **all** in-radius activity, ignoring the push-alert filters.
- Allows live config edits (wanted list, radius, mute, etc.) from Telegram without restarting.
- Runs unattended 24/7 on a Pi with graceful failure handling and silence detection.

## 2. Constraints and assumptions

- **Region:** Singapore. Coverage from local scanner communities exists and uses the standard Poracle / PokéAlarm JSON shapes.
- **Data source:** A community willing to push webhook events to our endpoint. **This is a social dependency, not a code dependency** — see §11. Without it, the bot has nothing to filter.
- **Host:** Raspberry Pi (or similar SBC / home server) on the user's home LAN, 24/7.
- **Inbound network:** No port forwarding. Public webhook ingress via Cloudflare Tunnel.
- **Notification target:** A single user (the operator) on Telegram. `ALLOWED_CHAT_IDS` is a short whitelist. No multi-user features in v1.
- **Volume:** Peak Singapore at ~1 km radius ≈ 50–200 events/hr. Trivial load.
- **TOS:** This bot does **not** scrape Pokémon Go directly, does **not** automate gameplay, and does **not** require any Pokémon Go account. It is a passive consumer of community-provided webhook data plus a Telegram bot, which carries no Niantic-account risk.

## 3. Architecture

Single Python 3.11+ process running on the Pi under `systemd`. Three external integrations:

1. **Inbound (webhooks):** Community scanner POSTs JSON to `https://<tunnel-hostname>/webhook` with a shared-secret header. Cloudflare Tunnel (`cloudflared`) routes that traffic through an outbound connection initiated from the Pi — no inbound router ports are opened, no home IP is exposed, and only the one HTTP endpoint we map is reachable. `cloudflared` runs as a separate systemd unit.
2. **Processing:** FastAPI app receives → authenticates → normalizes → dedupes → applies filter chain → formats → dispatches.
3. **Outbound + interactive:** `python-telegram-bot` in the same process sends formatted alerts and handles inbound commands (`/wanted`, `/mute`, `/radius`, `/nearby`, `/status`, etc.).

Persistent state lives in a local SQLite file (WAL mode). One process, one DB file, one tunnel — the entire system is meant to be small enough to reason about in one sitting.

### Why this shape

The minimum viable architecture that still degrades gracefully. No message broker, no separate worker, no container orchestration, no ORM, no DI framework. The expected codebase is ~600 LOC of Python plus tests. Adding more layers would create more failure modes than they prevent at this scale.

## 4. Component layout

```
pokemon-go-bot/
├── pogo_scout/
│   ├── __init__.py
│   ├── main.py              # Entrypoint: starts uvicorn + telegram bot + schedulers
│   ├── config.py            # Pydantic settings: env + yaml + sqlite kv merge
│   ├── events.py            # Internal Event dataclasses (MonsterEvent, RaidEvent)
│   ├── webhook/
│   │   ├── server.py        # FastAPI app, POST /webhook, GET /healthz (LAN-only)
│   │   └── normalizer.py    # Poracle / PokéAlarm JSON → internal Event
│   ├── filters/
│   │   ├── distance.py
│   │   ├── species.py
│   │   ├── iv.py
│   │   ├── raid.py
│   │   ├── pvp.py
│   │   └── decide.py        # should_push_alert(event, config) -> (bool, reason)
│   ├── notifier/
│   │   ├── telegram.py      # Send w/ retry, respect 429 retry_after
│   │   ├── format.py        # Event → Telegram message string (pure)
│   │   └── digest.py        # Periodic digest scheduler
│   ├── bot/
│   │   └── commands.py      # /wanted /mute /radius /iv /raidtier /raidboss /pvprank
│   │                        # /nearby /digest /silencethreshold /silencealert
│   │                        # /status /audit /stats /shinyalert
│   ├── ops/
│   │   ├── silence.py       # Silence-detection background task
│   │   └── housekeeping.py  # Vacuum events_active, daily backup trigger, disk checks
│   └── db/
│       ├── schema.sql
│       ├── migrations/      # 0001_*.sql, 0002_*.sql, ...
│       └── repo.py          # Thin functions over sqlite3 (stdlib)
├── tests/
│   ├── fixtures/            # Poracle + PA payloads, shiny, alolan, mega, egg, …
│   ├── snapshots/           # Rendered Telegram messages
│   ├── test_normalizer.py
│   ├── test_filters_distance.py
│   ├── test_filters_species.py
│   ├── test_filters_iv.py
│   ├── test_filters_raid.py
│   ├── test_filters_pvp.py
│   ├── test_decide.py
│   ├── test_format.py
│   ├── test_commands.py
│   ├── test_silence.py
│   └── test_webhook_e2e.py
├── deploy/
│   ├── pogo-scout.service
│   ├── cloudflared.service.example
│   ├── cloudflared-config.yml.example
│   └── README.md            # Pi setup walkthrough end-to-end
├── pyproject.toml
├── .env.example
└── config.yaml.example
```

### Boundary rule

Only `webhook/normalizer.py` knows about Poracle / PokéAlarm JSON. Everything else operates on internal `MonsterEvent` / `RaidEvent` dataclasses. Swapping data sources is a normalizer change, nothing more.

### Why no ORM / no async DB / no DI

Stdlib `sqlite3` with parameterized queries is enough at this scale. SQLAlchemy or DI containers would add more code than they remove and make Pi-side debugging harder.

## 5. Data flow

### 5.1 Webhook event lifecycle

```
[SG community scanner]
        │  POST https://<tunnel-host>/webhook
        │  Header: X-Webhook-Secret: <shared-secret>
        │  Body: Poracle / PA JSON
        ▼
1. FastAPI: validate secret header (401 if missing/wrong)
        │
        ▼
2. normalizer.detect_and_parse(payload) → MonsterEvent | RaidEvent
   - Detect schema (Poracle vs PA) by shape
   - 400 on truly malformed; 200 + log on unknown schema (no upstream retry-storm)
        │
        ▼
3. Dedupe: db.seen_recently(event.dedupe_key, ttl)
   - Monsters: ttl=15min, key=encounter_id
   - Raids: ttl=60min, key=(gym_id, boss_id, start_ts)
   - If seen: 200 and stop
   - Exception: previously-seen monster with iv_percent=None, new event has IV → re-process
        │
        ▼
4. Distance filter (cheap reject)
   - Drop if haversine(home, event) > radius
        │
        ▼
5. Persist: INSERT events_active(event_id, …, expires_at)
   - Always insert (so /nearby and digest see it), regardless of push-filter outcome
        │
        ▼
6. Push-filter chain: decide.should_push_alert(event, config)
   - Mute check (mute_until > now → drop alert, but row already persisted)
   - Monster: shiny override → species in wanted → iv_percent ≥ floor → pvp rank ≤ floor
   - Raid: tier ≥ floor → (boss in allowlist OR allowlist empty)
        │
        match=False ──► record audit_log row, status=NO_MATCH or MUTED; respond 200
        │
        match=True
        ▼
7. format.format_alert(event, match_reason) → Telegram message string
        │
        ▼
8. notifier.telegram.send(message, chat_ids)
   - 429 → respect retry_after
   - 5xx / network → 3 retries with backoff 1s/2s/4s
   - 401 (bad token) → set telegram_healthy=False, audit FAILED, continue
        │
        ▼
9. db.record_alert(event, match_reason, status, telegram_message_id)
        │
        ▼
   Respond 200.
```

### 5.2 Scout mode (pull + digest)

- **`/nearby [kind] [radius_override]`** — query `events_active` for rows where `expires_at > now()` and event passes distance filter (with optional override). Group by kind, sort by distance, format compactly, send as one or two Telegram messages. Truncate at 40 lines per message.
- **Periodic digest** — background `asyncio` task. Reads `digest_interval_minutes` from config_kv every tick. On each tick: query `events_active` for rows inserted since last digest, still active, in radius. If empty, skip; otherwise post a single grouped summary message. Includes everything (already-pushed events are not excluded).
- **Housekeeping** — every 5 minutes: `DELETE FROM events_active WHERE expires_at < now() - 10 min`.

### 5.3 Bot commands (inbound)

| Command | Effect |
|---|---|
| `/wanted add <species>` | Add to wanted list (accepts EN name or pokemon_id; supports `"Alolan Vulpix"` and `"Vulpix *"` wildcard) |
| `/wanted remove <species>` | Remove |
| `/wanted list` | Show current wanted list |
| `/radius <meters>` | Update proximity radius |
| `/iv <percent>` | Update IV floor for "any species" alerts |
| `/raidtier <1-7>` | Update minimum raid tier (1-5 standard; 6=Mega/Elite; 7=Primal) |
| `/raidboss add|remove|list|clear` | Manage raid-boss allowlist |
| `/pvprank great <N>` / `/pvprank ultra <N>` | Tighten PvP rank floors |
| `/shinyalert on|off` | Toggle shiny override (default on) |
| `/mute <duration>` | e.g. `30m`, `8h`, `until 0700` — sets `mute_until` |
| `/unmute` | Clears mute |
| `/nearby [kind] [radius]` | Pull current active sightings |
| `/digest <interval>` / `/digest off` | Enable/disable periodic digest |
| `/silencethreshold <duration>` / `/silencealert on|off` | Configure silence detection |
| `/status` | Current config + last event timestamp + telegram_healthy + counts |
| `/audit [N]` | Last N events (matched + muted + failed) with reason |
| `/stats today` | Totals + top species + top bosses |

All commands restricted to `ALLOWED_CHAT_IDS`. Anyone else: silent ignore.

## 6. Filtering rules

### 6.1 Distance

Haversine on `(home_lat, home_lng)` vs `(event_lat, event_lng)`. For SQL queries (`/nearby`, digest), prefilter rows with a lat/lng bounding box, then haversine in Python on survivors.

### 6.2 Species

- Stored in `wanted_species` as `(pokemon_id, form_id, is_wildcard)`:
  - `(37, NULL, FALSE)` → "Vulpix" — base form only.
  - `(37, 65, FALSE)` → "Alolan Vulpix" — that specific form only.
  - `(37, NULL, TRUE)` → "Vulpix *" — any form (wildcard).
- Lookup function `species_matches_wanted(event, wanted_rows)` returns true if **any** of:
  - `(event.pokemon_id, event.form_id, FALSE)` exact match exists, or
  - `(event.pokemon_id, NULL, TRUE)` wildcard row exists.
- Lookups accept English names or IDs at command parse time.
- Ships a static `pogo_scout/data/pokedex.json` for id ↔ name + form mappings.

### 6.3 IV

Normalizer produces a single `iv_percent` float (0–100):

- Poracle: pass `iv` through.
- PokéAlarm: `(atk + def + sta) / 45 * 100`.

Filter: `iv_percent >= iv_floor` (default 90.0).

**Unencountered spawns** (`iv_percent is None`):

- If species is in wanted list → alert (you want to know before IV check).
- Otherwise → skip this filter (a later "encountered" event for the same `encounter_id` may re-trigger; the dedupe rule in §5.1 allows that specific case).

### 6.4 Raid

Tier normalization:

| Source value | `raid_level` |
|---|---|
| T1 | 1 |
| T2 | 2 |
| T3 | 3 |
| T4 | 4 |
| T5 | 5 |
| Mega, Elite | 6 |
| Primal | 7 |

Filter: `raid_level >= raid_tier_floor` (default 5) AND (`boss_allowlist` empty OR `boss_species_key` in `boss_allowlist`).

**Egg events** (raid known but boss unknown): inserted into `events_active` so `/nearby raids` shows upcoming, but **not** pushed. Hatch event (boss known) is what pushes.

**Shadow raids:** keep their numeric tier; tagged `is_shadow=True`. Not filtered specially in v1 (treated as their tier number).

### 6.5 PvP

Normalizer extracts:

- `pvp_great_rank` = best (lowest) rank in `pvp_rankings_great_league` array (or None if absent).
- `pvp_ultra_rank` = best rank in `pvp_rankings_ultra_league` array (or None).

Filter passes if either: `pvp_great_rank <= gl_rank_floor` (default 5) OR `pvp_ultra_rank <= ul_rank_floor` (default 5).

If both are None, this filter does not fire (older scanners that don't compute PvP just don't get PvP-based alerts).

### 6.6 Shiny override

If payload has `shiny == true`, override all monster filters and push the alert. Default on; toggle via `/shinyalert off`.

### 6.7 Mute

Single `mute_until` Unix timestamp in `config_kv`. Mute is implemented as a push-filter, not a kill-switch — muted events still land in `events_active` (so `/nearby` and digest work) and `audit_log` (marked `MUTED`).

### 6.8 The combined push-match decision

```python
def should_push_alert(event, config) -> tuple[bool, str]:
    if is_muted(config):
        return False, "muted"
    if event.kind == "monster":
        if config.shiny_alert and event.shiny:
            return True, "shiny"
        if species_matches_wanted(event, config.wanted_species):
            return True, f"wanted:{event.species_name}"
        if event.iv_percent is not None and event.iv_percent >= config.iv_floor:
            return True, f"iv:{event.iv_percent:.1f}%"
        if ((event.pvp_great_rank and event.pvp_great_rank <= config.gl_rank_floor)
            or (event.pvp_ultra_rank and event.pvp_ultra_rank <= config.ul_rank_floor)):
            return True, f"pvp:GL{event.pvp_great_rank}/UL{event.pvp_ultra_rank}"
        return False, "no-match"
    if event.kind == "raid":
        if event.raid_level < config.raid_tier_floor:
            return False, "tier-too-low"
        if config.raid_boss_allowlist and event.boss_species_key not in config.raid_boss_allowlist:
            return False, "boss-not-wanted"
        return True, f"raid:T{event.raid_level} {event.boss_name}"
```

The returned `reason` string is written to `audit_log.matched_by`.

## 7. Configuration and state

### 7.1 Layered config

| Layer | Lives in | Purpose |
|---|---|---|
| Secrets | `.env` (gitignored) | `TELEGRAM_BOT_TOKEN`, `WEBHOOK_SECRET`, `ALLOWED_CHAT_IDS` |
| Boot defaults | `config.yaml` | `HOME_LAT`, `HOME_LNG`, default `RADIUS_M`, `IV_FLOOR`, `RAID_TIER_FLOOR`, `GL_RANK_FLOOR`, `UL_RANK_FLOOR`, `SILENCE_THRESHOLD_MIN`, `DIGEST_INTERVAL_MIN` (0 = off) |
| Live state | SQLite | Anything the bot can change at runtime (wanted list, mute, current radius/iv overrides, digest interval) |

Read order: live state overrides yaml defaults overrides nothing. Secrets only ever from `.env`.

### 7.2 Database schema (summary)

| Table | Purpose |
|---|---|
| `schema_version` | Migration tracking |
| `config_kv` | Single-row config overrides (radius, iv_floor, raid_tier_floor, gl_rank_floor, ul_rank_floor, shiny_alert, mute_until, digest_interval_min, silence_threshold_min, silence_alert_enabled) |
| `wanted_species` | (pokemon_id, form_id_or_null, is_wildcard, added_at) — see §6.2 for lookup semantics |
| `raid_boss_allowlist` | (pokemon_id, added_at) |
| `events_active` | (event_id PK, kind, species_or_boss_id, form_id, lat, lng, iv_percent, cp, level, pvp_great_rank, pvp_ultra_rank, raid_level, gym_name, shiny, expires_at, inserted_at) |
| `alerted_events` | (event_id PK, kind, alerted_at) — used for dedupe + to surface in `/audit` |
| `audit_log` | (id, event_id, kind, status, matched_by, telegram_message_id, error, ts) — full history of decisions |

WAL mode + `busy_timeout=5s`. Single writer in practice (webhook + bot share one asyncio loop).

## 8. Error handling and operations

### 8.1 Failure mode table

| Failure | Response |
|---|---|
| Malformed webhook JSON | 400, log truncated payload + reason |
| Bad/missing secret header | 401, increment `bad_auth_count` metric |
| Unknown schema (neither Poracle nor PA shape) | 200 + log as `unknown_schema` with sample |
| Telegram 429 rate limit | Respect `retry_after`, retry |
| Telegram network / 5xx | 3 retries, backoff 1s/2s/4s; on final failure record FAILED |
| Telegram 401 (bad token) | Log critical, set `telegram_healthy=False`, keep accepting webhooks |
| SQLite locked | Retry once with backoff (WAL + busy_timeout cover almost all cases) |
| Disk free < 100 MB | Log critical + Telegram alert + stop inserting `events_active` (push alerts still fire) |
| Cloudflare tunnel disconnect | `cloudflared` auto-reconnects (separate systemd unit, `Restart=always`); detected via §8.4 silence detection |
| Upstream community pauses | Same as tunnel — detected via silence detection |
| Clock skew | `systemd-timesyncd` enabled; warn on events with `despawn_at > 60s` in the past |
| Pi reboot / power loss | Both systemd services restart; SQLite WAL recovers; vacuum clears stale `events_active` on next tick |

### 8.2 Always-200 policy

After auth passes (i.e. the request is from the trusted upstream), we always return 200 — even if Telegram dispatch fails or the event is dropped by filters. Reason: webhook providers commonly disable endpoints that return 5xx repeatedly. We absorb internal failures and surface them via logs + audit_log + `/status`.

### 8.3 Logging

`logging` stdlib → stdout/stderr → journald. Structured key=value lines:

```
INFO  webhook.received    src=poracle kind=monster pkmn=246 iv=98.0 match=wanted:Larvitar dispatched=True
INFO  webhook.received    src=poracle kind=monster pkmn=19  iv=12.0 match=no-match        dispatched=False
WARN  telegram.retry      attempt=2 reason=503
ERROR telegram.dispatch_failed event_id=… final_attempt=3
```

Log level via env var, default `INFO`.

### 8.4 Silence detection

Background `asyncio` task wakes every 10 minutes, checks `last_webhook_received_at`. If older than `silence_threshold_min` (default 45), sends one Telegram warning:

> ⚠️ No webhook received in 47 minutes. Tunnel or upstream may be down.

At most one warning per silence episode; resets on next webhook arrival. Configurable: `/silencethreshold 60m`, `/silencealert off`.

### 8.5 Health endpoint

`GET /healthz` — LAN-only. Bound to the Pi's LAN IP / 127.0.0.1; **not** mapped through `cloudflared`. Response:

```json
{
  "status": "ok",
  "uptime_s": 73291,
  "last_webhook_received_at": "2026-05-14T13:42:11Z",
  "last_webhook_age_s": 47,
  "telegram_healthy": true,
  "events_active_count": 62,
  "db_size_bytes": 4825088,
  "disk_free_bytes": 53847293952,
  "version": "0.1.3"
}
```

### 8.6 Backups

Daily cron on the Pi:
```
sqlite3 pogo_scout.db ".backup '/home/pi/backups/pogo_scout-$(date +%F).db'"
```
Keep last 7. Few-MB footprint.

### 8.7 Deploy / update workflow

- Git repo on the Pi, `main` branch.
- Deploy: `git pull && systemctl restart pogo-scout`.
- Schema migrations: `db/migrations/000N_*.sql`, applied in order at startup based on `schema_version` row.

## 9. Testing strategy

| Area | Coverage |
|---|---|
| `normalizer.py` | Heavy — one test per fixture (Poracle/PA × monster/raid × form/shiny/mega/egg/unencountered/malformed) |
| `filters/*` | Heavy — pure functions, trivial to test |
| `decide.should_push_alert` | Heavy — covers the matrix of match conditions |
| `notifier/format.py` | Snapshot tests against `tests/snapshots/*.txt` |
| `webhook` end-to-end | One happy path per event kind, using a fake-Telegram recorder |
| `bot/commands.py` | Light — one test per command verifying DB state |
| `db/repo.py` | Exercised transitively via filter + command tests against temp SQLite |
| `silence.py` | One test with a mocked clock |
| Cloudflare / systemd / journald | Not tested — manual smoke checklist in `deploy/README.md` |

### 9.1 Fixtures

```
tests/fixtures/
├── poracle_monster_iv_full.json
├── poracle_monster_iv_partial.json
├── poracle_monster_unencountered.json
├── poracle_monster_alolan_form.json
├── poracle_monster_shiny.json
├── poracle_raid_t5.json
├── poracle_raid_mega.json
├── poracle_raid_egg.json
├── pa_monster_iv_full.json
├── pa_raid_t5.json
└── malformed_missing_lat.json
```

Seeded from Poracle / PokéAlarm public docs at write-time; refined once we see real payloads from the SG community.

### 9.2 Manual smoke test (documented in `deploy/README.md`)

1. Curl a fixture payload at the tunnel URL with the secret header → Telegram message in <2s.
2. Curl without the secret → 401.
3. `/status` returns sensible values.
4. `/wanted add Larvitar` → Larvitar fixture fires; `/wanted remove Larvitar` → fixture no longer fires.
5. `/mute 5m` → fixture event lands in `audit_log` as `MUTED` but no Telegram message; after 5min, fires again.
6. `/nearby` with several active events seeded → returns them sorted by distance.
7. Kill `cloudflared` → after 45 min, silence alert arrives.
8. Reboot Pi → both services come back up unaided.

## 10. Deployment

### 10.1 Pi prerequisites

- Raspberry Pi OS (or any Linux), Python 3.11+, `git`, `sqlite3` CLI.
- `cloudflared` installed (official Cloudflare APT package or binary).
- `systemd-timesyncd` enabled.

### 10.2 Services

- `pogo-scout.service` — runs the Python app via uvicorn-in-process (started from `main.py`). `Restart=always`, `RestartSec=10`.
- `cloudflared.service` — runs the tunnel. Config in `/etc/cloudflared/config.yml` mapping the public hostname to `http://localhost:8000`. **Does not** map `/healthz`.

### 10.3 Cloudflare Tunnel setup

Documented step-by-step in `deploy/README.md`:

1. Cloudflare account with a domain on Cloudflare DNS (free).
2. `cloudflared tunnel login` → browser auth.
3. `cloudflared tunnel create pogo-scout`.
4. `config.yml` mapping `pogo-scout.<your-domain> → http://localhost:8000`.
5. `cloudflared tunnel route dns pogo-scout pogo-scout.<your-domain>`.
6. Enable & start the systemd unit.

### 10.4 First-run checklist

1. Create Telegram bot via @BotFather; record token.
2. Get your numeric Telegram chat ID (e.g. via `@userinfobot`).
3. Fill in `.env` (TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET (generate random), ALLOWED_CHAT_IDS).
4. Fill in `config.yaml` (HOME_LAT, HOME_LNG, RADIUS_M, etc.).
5. `systemctl enable --now pogo-scout cloudflared`.
6. Curl a fixture payload against the tunnel URL to verify end-to-end.
7. Provide your tunnel URL + secret to the SG community so they can route events to you.

## 11. Prerequisites and known dependencies

This bot is useless without a webhook event source. The path to that source is **social, not technical**:

- Identify which Singapore scanner Discord communities exist and how to gain access (research at design time; this spec does not catalogue them).
- Apply / contribute / pay (as required by the specific community) for personal-webhook permissions.
- Negotiate getting our tunnel URL + secret added to their Poracle/PA outbound config.

The implementation plan will note this as a parallel track to the code work. Code can be developed and tested against fixtures without an upstream; only the smoke test and real-world operation need it.

## 12. Out of scope (v1)

- Multi-user support (account isolation, per-user config).
- Anti-spam / cooldown beyond mute (e.g. "don't alert me on the same species more than once an hour").
- Web dashboard.
- Maps / image attachments in Telegram messages (text + Google/Apple Maps links only).
- Live-location-following proximity (fixed home coords only).
- Quest / invasion / lure / gym-control events (the protocol supports them; we ignore in v1).
- Direct scraping of Discord channels (we use webhooks only).
- Pokémon Go API scraping (out of scope and explicitly avoided per §2).
- Internationalization / Japanese-language scanner protocols.

## 13. Open questions to revisit after v1

- Should the digest mode evolve into a smart "novel only" mode (de-duplicate against pushed alerts)?
- Should we add per-species mute (e.g. mute Larvitar specifically when farming)?
- Is a tiny web dashboard (read-only, LAN-only, FastAPI on a `/dashboard` route) worth adding for `/audit` viewing?
- Should we expose a second tunnel hostname for accepting webhooks from multiple communities (different secrets per source)?

---

## Appendix A — Architecture sketch

```
                  ┌───────────────────────────────┐
                  │  SG community scanner stack   │
                  │  (Poracle / PokéAlarm pusher) │
                  └────────────────┬──────────────┘
                                   │ HTTPS POST
                                   │ X-Webhook-Secret
                                   ▼
                  ┌───────────────────────────────┐
                  │     Cloudflare Edge           │
                  │ pogo-scout.<your-domain>      │
                  └────────────────┬──────────────┘
                                   │ outbound-initiated tunnel
                                   ▼
                  ┌───────────────────────────────┐
                  │           Raspberry Pi        │
                  │  ┌─────────────────────────┐  │
                  │  │ cloudflared (systemd)   │  │
                  │  └────────────┬────────────┘  │
                  │               │ 127.0.0.1:8000│
                  │               ▼               │
                  │  ┌─────────────────────────┐  │
                  │  │  pogo-scout (systemd)   │  │
                  │  │  ┌───────────────────┐  │  │
                  │  │  │ FastAPI /webhook  │  │  │
                  │  │  │ FastAPI /healthz  │◄─┼──┼── LAN-only
                  │  │  │ Telegram bot loop │  │  │
                  │  │  │ Digest scheduler  │  │  │
                  │  │  │ Silence detector  │  │  │
                  │  │  │ Housekeeping      │  │  │
                  │  │  └─────────┬─────────┘  │  │
                  │  │            │             │  │
                  │  │  ┌─────────▼─────────┐  │  │
                  │  │  │ SQLite (WAL)      │  │  │
                  │  │  └───────────────────┘  │  │
                  │  └─────────┬───────────────┘  │
                  └────────────┼──────────────────┘
                               │ outbound HTTPS
                               ▼
                  ┌───────────────────────────────┐
                  │      Telegram Bot API         │
                  └────────────────┬──────────────┘
                                   │
                                   ▼
                  ┌───────────────────────────────┐
                  │   Operator's phone (you)      │
                  └───────────────────────────────┘
```
