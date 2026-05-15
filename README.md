# pogo-scout

Personal Pokémon Go scout bot for Singapore.

Receives webhook events from a community scanner (Poracle / PokéAlarm protocol),
filters within a proximity radius (home or live location), and sends Telegram
alerts with map images. Runs in Docker behind Tailscale Funnel (or on a Raspberry Pi behind a Cloudflare Tunnel).

## Quick start

Two supported deployment paths:

- **Dockge / Docker Compose** — see [deploy/dockge.md](deploy/dockge.md). Bot image pulled from `ghcr.io/legitaxes/pokemon-go-bot`, Tailscale Funnel sidecar exposes `/webhook` publicly without a domain. Recommended.
- **Raspberry Pi (bare metal + systemd)** — see [deploy/README.md](deploy/README.md). Bot runs as a systemd unit behind a Cloudflare Tunnel.

## Telegram commands

| Command | Purpose |
|---|---|
| `/wanted add\|remove\|list <species>` | Manage wanted-species list |
| `/radius <m>` | Set proximity radius |
| `/iv <%>` | Set IV floor |
| `/raidtier <1-7>` | Set minimum raid tier |
| `/pvprank great\|ultra <N>` | Tighten PvP rank floors |
| `/raidboss add\|remove\|list\|clear <species>` | Manage raid-boss allowlist |
| `/shinyalert on\|off` | Toggle shiny override |
| `/mapimage on\|off` | Toggle map image attachments |
| `/mute <30m\|8h\|until HHMM>` / `/unmute` | Pause push alerts |
| `/follow on\|off\|status` | Use shared live location as proximity center |
| `/nearby [monsters\|raids] [radius]` | List active sightings in radius |
| `/digest <interval>\|off` | Periodic summary push |
| `/silencethreshold <duration>` / `/silencealert on\|off` | Configure silence detection |
| `/status` / `/audit [N]` / `/stats today` | Read current state + history |

## Architecture

See [`docs/superpowers/specs/2026-05-14-pokemon-go-scout-design.md`](docs/superpowers/specs/2026-05-14-pokemon-go-scout-design.md).

## Dev

```bash
pip install -e .[dev]
pytest -v
```

## Manual smoke test

See [deploy/README.md §6](deploy/README.md) and the eleven-step checklist in the design spec §9.2.
