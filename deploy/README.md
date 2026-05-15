# Deploying pogo-scout

Target: Raspberry Pi 4/5 running Raspberry Pi OS (Debian 12), Python 3.11+, single-user setup.
All paths below assume the `pi` user and a checkout at `/home/pi/pokemon-go-bot`.

## 1. Pi setup

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv git sqlite3 libjpeg-dev zlib1g-dev
sudo systemctl enable systemd-timesyncd
```

`libjpeg-dev` and `zlib1g-dev` are required for Pillow (map rendering). The Pi has no real-time
clock, so enabling `systemd-timesyncd` keeps event timestamps sane after reboots.

## 2. Clone + venv

```bash
git clone <repo> /home/pi/pokemon-go-bot
cd /home/pi/pokemon-go-bot
python3.11 -m venv .venv
.venv/bin/pip install -e .
```

## 3. Telegram bot

1. `/newbot` to [@BotFather](https://t.me/BotFather), record the token.
2. `/start` your bot from your own account (otherwise it cannot DM you).
3. Get your chat id via [@userinfobot](https://t.me/userinfobot).
4. `cp .env.example .env` — fill in `TELEGRAM_BOT_TOKEN`, `WEBHOOK_SECRET` (`openssl rand -hex 32`), `ALLOWED_CHAT_IDS`.
5. `cp config.yaml.example config.yaml` — set `home_lat` / `home_lng`.

## 4. Cloudflare Tunnel

The tunnel is outbound — the Pi initiates the connection to Cloudflare, so no inbound ports are
opened on your home router and your home IP stays hidden.

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
cloudflared tunnel login                       # browser auth
cloudflared tunnel create pogo-scout           # records UUID + credentials json
sudo mkdir -p /etc/cloudflared
sudo cp deploy/cloudflared-config.yml.example /etc/cloudflared/config.yml
# Edit /etc/cloudflared/config.yml — fill in tunnel UUID and hostname.
cloudflared tunnel route dns pogo-scout pogo-scout.<your-domain>
sudo cloudflared service install
```

## 5. pogo-scout service

```bash
sudo cp deploy/pogo-scout.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pogo-scout
```

## 6. Smoke test

```bash
journalctl -u pogo-scout -f
curl -X POST https://pogo-scout.<your-domain>/webhook \
  -H "X-Webhook-Secret: $(grep WEBHOOK_SECRET .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  --data @tests/fixtures/poracle_monster_iv_full.json
# A Telegram message should arrive within ~2s.
```

## 7. Hand the URL + secret to your SG scanner community

Provide them: `https://pogo-scout.<your-domain>/webhook` and the `WEBHOOK_SECRET` value.
They will configure their Poracle / PokéAlarm outbound to push events to you.

## 8. Daily SQLite backup (optional, recommended)

```bash
sudo crontab -e
# add:
# 0 3 * * * sqlite3 /home/pi/pokemon-go-bot/pogo_scout.db ".backup '/home/pi/backups/pogo_scout-$(date +\%F).db'" && find /home/pi/backups -name 'pogo_scout-*.db' -mtime +7 -delete
```

That runs an online `.backup` (safe with WAL) at 03:00 daily and prunes anything older than 7 days.
