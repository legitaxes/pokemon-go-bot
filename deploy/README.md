# Deploying Pokemon Go Scout on a Raspberry Pi

Target: Raspberry Pi 4/5 running Raspberry Pi OS (Debian 12), Python 3.11+, single-user setup.
All paths below assume the `pi` user and a checkout at `/home/pi/pokemon-go-bot`.

## 1. System dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git sqlite3
```

## 2. Clone and create the virtualenv

```bash
cd /home/pi
git clone <your-fork-url> pokemon-go-bot
cd pokemon-go-bot
python3 -m venv .venv
.venv/bin/pip install -e .
```

`-e .` reads `pyproject.toml` and installs runtime deps (FastAPI, uvicorn,
python-telegram-bot, pydantic, PyYAML, staticmap, Pillow, httpx).

## 3. Configure secrets and defaults

```bash
cp .env.example .env
cp config.yaml.example config.yaml
```

Edit `.env`:
- `TELEGRAM_BOT_TOKEN` — talk to [@BotFather](https://t.me/BotFather), `/newbot`, paste the token.
- `WEBHOOK_SECRET` — a long random string. `openssl rand -hex 32` is fine. You'll hand this to the
  feed operator (Section 6).
- `ALLOWED_CHAT_IDS` — your numeric Telegram chat id. Find it via
  [@userinfobot](https://t.me/userinfobot) or by running the bot once and reading the log.

Edit `config.yaml`:
- Set `home_lat` and `home_lng` to your actual coords.
- Tune `radius_m`, `iv_floor`, etc., or leave defaults and adjust later via `/setradius`, `/setiv`,
  and friends from inside Telegram.

## 4. Cloudflare Tunnel

The tunnel is outbound — your Pi connects to Cloudflare; no inbound ports are opened on your home
router. From the Pi:

```bash
# Install cloudflared (armhf or arm64 depending on your Pi)
curl -L -o /tmp/cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i /tmp/cloudflared.deb

cloudflared tunnel login          # opens a URL, complete in browser
cloudflared tunnel create pogo-scout
# Note the UUID and credentials file path that command prints.

# Point a hostname at the tunnel
cloudflared tunnel route dns pogo-scout pogo-scout.<your-domain>

# Wire it up
mkdir -p ~/.cloudflared
cp /home/pi/pokemon-go-bot/deploy/cloudflared-config.yml.example ~/.cloudflared/config.yml
# Edit ~/.cloudflared/config.yml: paste the tunnel UUID and full credentials path,
# and replace pogo-scout.<your-domain> with the real hostname.

# Install as a service
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Verify:
```bash
sudo systemctl status cloudflared
curl -i -X POST https://pogo-scout.<your-domain>/webhook \
  -H 'Content-Type: application/json' -d '{}'
# Expect 401 — the request reached the Pi but is missing the X-Webhook-Secret header.
```

## 5. systemd unit for the bot

```bash
sudo cp /home/pi/pokemon-go-bot/deploy/pogo-scout.service /etc/systemd/system/pogo-scout.service
sudo systemctl daemon-reload
sudo systemctl enable --now pogo-scout
journalctl -u pogo-scout -f
```

You should see "Pokemon Go Scout started" in the log and the bot answering `/start` in Telegram.

## 6. Hand the webhook URL + secret to the feed operator

Give the Singapore Discord feed admin (Poracle or PokéAlarm operator):
- URL: `https://pogo-scout.<your-domain>/webhook`
- Header: `X-Webhook-Secret: <your WEBHOOK_SECRET>`

They'll plug both into their forwarder. The bot rejects any request without the matching secret
header.

Smoke test from your laptop:
```bash
curl -i -X POST https://pogo-scout.<your-domain>/webhook \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Secret: <your secret>' \
  -d '[{"type":"monster","message":{"pokemon_id":25,"latitude":1.3521,"longitude":103.8198,"individual_attack":15,"individual_defense":15,"individual_stamina":15,"disappear_time":9999999999}}]'
```
The bot logs the event; it won't alert unless Pikachu is on your wanted list, but you'll see it
processed.

## 7. Daily SQLite backup

The DB is small (KV + caches + a few day's worth of dedupe + digest rows). A daily file copy is
enough:

```bash
mkdir -p /home/pi/pokemon-go-bot/backups
crontab -e
```
Add:
```
0 4 * * * sqlite3 /home/pi/pokemon-go-bot/pogo_scout.db ".backup '/home/pi/pokemon-go-bot/backups/pogo_scout-$(date +\%Y\%m\%d).db'" && find /home/pi/pokemon-go-bot/backups -name 'pogo_scout-*.db' -mtime +14 -delete
```
That runs an online `.backup` (safe with WAL) at 04:00 daily and prunes anything older than 14 days.

## 8. Updating

```bash
cd /home/pi/pokemon-go-bot
git pull
.venv/bin/pip install -e .
sudo systemctl restart pogo-scout
```

Migrations in `pogo_scout/db/migrations/` are applied automatically on startup.
