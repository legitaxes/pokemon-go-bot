# Deploying pogo-scout as a Dockge stack

This walkthrough assumes you already have Dockge running on a Debian/Ubuntu host
with Docker installed, and that Dockge's stacks directory is `/opt/stacks/`
(adjust paths if yours differs).

The stack runs two containers on a private bridge network:

| Container | Purpose |
|---|---|
| `pogo-scout` | The bot. FastAPI webhook + Telegram client. Binds 0.0.0.0:8000 on the stack network only. |
| `pogo-scout-tunnel` | `cloudflared` sidecar. Outbound-only tunnel to Cloudflare; no inbound ports on the host. |

The host never exposes port 8000 publicly. `/webhook` reaches the bot only through
the Cloudflare tunnel (path-scoped); `/healthz` stays internal to the docker network.

## 1. Clone into Dockge's stacks directory

```bash
sudo git clone https://github.com/legitaxes/pokemon-go-bot.git /opt/stacks/pogo-scout
cd /opt/stacks/pogo-scout
```

Dockge will auto-discover the new stack once `compose.yaml` exists in this dir.

## 2. Create the Cloudflare Tunnel and grab the token

1. Open the Cloudflare dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Pick **Cloudflared**, name it (e.g. `pogo-scout`), then on the install step copy
   the **token** value out of the `docker run … --token <TOKEN>` snippet.
3. On the **Public Hostnames** tab add one entry:
   - Subdomain + domain: `pogo-scout.<your-domain>`
   - Path: `webhook`
   - Service: **HTTP** → `pogo-scout:8000`
4. Leave the **Private Networks** tab empty.

Cloudflare creates a public hostname that routes only `/webhook` to the bot container.
Any other path returns 404 at the edge — `/healthz` is never reachable from the internet.

## 3. Fill in secrets

```bash
sudo cp .env.example .env
sudo nano .env
```

Set:
- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather), `/newbot`.
- `WEBHOOK_SECRET` — long random string. `openssl rand -hex 32` is fine.
  You'll hand this to your scanner-community feed admin in step 6.
- `ALLOWED_CHAT_IDS` — your numeric chat id (find via [@userinfobot](https://t.me/userinfobot)).
- `TUNNEL_TOKEN` — the token from step 2.

## 4. Fill in the bot config

```bash
sudo mkdir -p data
sudo cp config.yaml.example data/config.yaml
sudo nano data/config.yaml
```

Set `home_lat` / `home_lng` and tune any defaults. Everything else can be changed
later from Telegram (`/setradius`, `/setiv`, etc.).

Make sure the `data/` directory is writable by uid 1000 (the `pogo` user inside
the container):

```bash
sudo chown -R 1000:1000 data
```

## 5. Deploy from Dockge

In the Dockge UI:
1. The `pogo-scout` stack should now appear as **Inactive**.
2. Click into it and hit **Deploy**. Dockge builds the image and starts both containers.
3. Tail logs via the **Logs** tab; you should see `Uvicorn running on http://0.0.0.0:8000`
   and `cloudflared` reporting `Registered tunnel connection`.

Alternatively from the shell:
```bash
sudo docker compose -f /opt/stacks/pogo-scout/compose.yaml up -d --build
sudo docker compose -f /opt/stacks/pogo-scout/compose.yaml logs -f
```

## 6. Smoke test and hand off the URL

Smoke test from your laptop:
```bash
curl -X POST https://pogo-scout.<your-domain>/webhook \
  -H "X-Webhook-Secret: <your WEBHOOK_SECRET>" \
  -H "Content-Type: application/json" \
  --data @tests/fixtures/poracle_monster_iv_full.json
```

A Telegram message should arrive within ~2 seconds.

Then give your SG scanner-community feed admin:
- URL: `https://pogo-scout.<your-domain>/webhook`
- Header: `X-Webhook-Secret: <your WEBHOOK_SECRET>`

The bot rejects any request missing the matching secret header.

## 7. Updating

```bash
cd /opt/stacks/pogo-scout
sudo git pull
sudo docker compose up -d --build
```

DB migrations in `pogo_scout/db/migrations/` apply automatically on startup.

## 8. Backups

The SQLite DB lives at `./data/pogo_scout.db` on the host. A simple daily backup:

```bash
sudo crontab -e
# add:
# 0 3 * * * sqlite3 /opt/stacks/pogo-scout/data/pogo_scout.db ".backup '/opt/stacks/pogo-scout/data/backups/pogo_scout-$(date +\%F).db'" && find /opt/stacks/pogo-scout/data/backups -name 'pogo_scout-*.db' -mtime +7 -delete
```

WAL mode is on, so the online `.backup` is safe while the bot is running.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `cloudflared` keeps restarting | `TUNNEL_TOKEN` blank or stale — rotate from the dashboard. |
| Bot starts, no Telegram replies to `/start` | Wrong `TELEGRAM_BOT_TOKEN`, or your chat id isn't in `ALLOWED_CHAT_IDS`. |
| Webhook returns 401 | Header `X-Webhook-Secret` missing or doesn't match `.env`. |
| Webhook returns 502 from Cloudflare | The dashboard ingress points at the wrong service name; must be `http://pogo-scout:8000`. |
| Permission denied writing `/data/pogo_scout.db` | `data/` is owned by host root, not uid 1000. Run `sudo chown -R 1000:1000 data`. |
