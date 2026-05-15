# Deploying pogo-scout as a Dockge stack

Deployment model: paste `compose.yaml` into Dockge's UI. No repo on the host.
Image is built by GitHub Actions and published to
`ghcr.io/legitaxes/pokemon-go-bot:latest` (multi-arch: linux/amd64 + linux/arm64).

Two containers run on a private bridge network:

| Container | Purpose |
|---|---|
| `pogo-scout` | The bot. FastAPI webhook + Telegram client. |
| `pogo-scout-tunnel` | `cloudflared` sidecar. Outbound-only tunnel to Cloudflare. |

The Dockge host never exposes port 8000 publicly. `/webhook` reaches the bot only
through the Cloudflare tunnel (path-scoped); `/healthz` stays internal to the
docker network.

---

## One-time: make the GHCR package public

The first push to `main` after this guide existed triggered a GitHub Actions run
that published the image to `ghcr.io/legitaxes/pokemon-go-bot`. Packages start
**private**, so the Dockge host can't pull them anonymously. Make it public once:

1. Open https://github.com/legitaxes?tab=packages
2. Click `pokemon-go-bot` → **Package settings** (right sidebar)
3. Scroll to **Danger Zone** → **Change visibility** → **Public** → confirm.

(You only do this once. After that, every push to `main` rebuilds the same public image.)

---

## 1. Create the Cloudflare Tunnel

1. Cloudflare dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Pick **Cloudflared**, name it (e.g. `pogo-scout`).
3. On the install step, copy the **token** out of the `--token <TOKEN>` snippet.
4. On the **Public Hostnames** tab add one entry:
   - Subdomain + domain: `pogo-scout.<your-domain>`
   - Path: `webhook`
   - Service: **HTTP** → `pogo-scout:8000`
5. Save. The tunnel is now provisioned but won't connect until cloudflared runs.

Only `/webhook` is exposed publicly. Any other path returns 404 at the Cloudflare edge.

---

## 2. Create the stack in Dockge

In Dockge UI:
1. **Compose** → **+ Compose** (top-right).
2. Stack name: `pogo-scout`.
3. Paste the contents of [`compose.yaml`](../compose.yaml) into the editor.
4. **Save** (don't deploy yet).

Dockge creates `/opt/stacks/pogo-scout/` with your compose file inside.

---

## 3. Fill in `.env` from Dockge

Still in the stack page, click the **Env** tab. Paste:

```env
TELEGRAM_BOT_TOKEN=<token from @BotFather>
WEBHOOK_SECRET=<output of: openssl rand -hex 32>
ALLOWED_CHAT_IDS=<your numeric chat id, from @userinfobot>
TUNNEL_TOKEN=<the token from step 1>
```

Save. Dockge writes this to `/opt/stacks/pogo-scout/.env`.

---

## 4. Create `data/config.yaml` on the host

The bot needs `home_lat` / `home_lng` and a handful of tunable defaults at boot.
These live in `data/config.yaml`, which Dockge can't manage through the UI
(it's inside a bind-mounted directory, not the stack root). One-time SSH:

```bash
sudo mkdir -p /opt/stacks/pogo-scout/data
sudo curl -fsSL \
  https://raw.githubusercontent.com/legitaxes/pokemon-go-bot/main/config.yaml.example \
  -o /opt/stacks/pogo-scout/data/config.yaml
sudo nano /opt/stacks/pogo-scout/data/config.yaml   # set home_lat, home_lng
sudo chown -R 568:568 /opt/stacks/pogo-scout/data
```

Only `home_lat` and `home_lng` are required to change. Everything else can be
tuned later from Telegram (`/radius`, `/iv`, `/raidtier`, etc.) and is persisted
to the SQLite DB in `data/`.

---

## 5. Deploy

Back in Dockge UI: hit **Start** on the stack.

Dockge pulls `ghcr.io/legitaxes/pokemon-go-bot:latest`, pulls `cloudflared:latest`,
and starts both. Tail logs via the **Logs** tab; you should see:

- `pogo-scout`: `Uvicorn running on http://0.0.0.0:8000`
- `pogo-scout-tunnel`: `Registered tunnel connection`

---

## 6. Smoke test

From your laptop:
```bash
curl -X POST https://pogo-scout.<your-domain>/webhook \
  -H "X-Webhook-Secret: <your WEBHOOK_SECRET>" \
  -H "Content-Type: application/json" \
  --data '[{"type":"monster","message":{"pokemon_id":25,"latitude":1.3521,"longitude":103.8198,"individual_attack":15,"individual_defense":15,"individual_stamina":15,"disappear_time":9999999999}}]'
```
(Substitute your home coords for 1.3521/103.8198.) A Telegram message arrives
within ~2s if Pikachu is on your wanted list, or you'll see it logged as
`NO_MATCH` otherwise.

---

## 7. Hand the URL + secret to your SG scanner community

- URL: `https://pogo-scout.<your-domain>/webhook`
- Header: `X-Webhook-Secret: <your WEBHOOK_SECRET>`

The bot rejects any request missing the matching secret.

---

## 8. Updates

When you push code to `main`, GitHub Actions rebuilds and republishes `:latest`
within a couple of minutes. To pick up the new image on the homeserver, hit
**Stop** then **Start** in Dockge (or **Update** if your Dockge has that button)
— `pull_policy: always` in the compose ensures the new image is fetched.

For a CLI update:
```bash
sudo docker compose -f /opt/stacks/pogo-scout/compose.yaml pull
sudo docker compose -f /opt/stacks/pogo-scout/compose.yaml up -d
```

DB migrations in `pogo_scout/db/migrations/` apply automatically on startup.

---

## 9. Backups

SQLite DB lives at `/opt/stacks/pogo-scout/data/pogo_scout.db`. Daily backup via
host cron:

```bash
sudo crontab -e
# add:
# 0 3 * * * sqlite3 /opt/stacks/pogo-scout/data/pogo_scout.db ".backup '/opt/stacks/pogo-scout/data/backups/pogo_scout-$(date +\%F).db'" && find /opt/stacks/pogo-scout/data/backups -name 'pogo_scout-*.db' -mtime +7 -delete
```

WAL mode is on; the online `.backup` is safe while the bot is running.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Stack won't start: `denied: not authorized` pulling the image | GHCR package still private. Go back to **One-time: make the GHCR package public**. |
| `cloudflared` keeps restarting | `TUNNEL_TOKEN` blank, wrong, or rotated. Get a fresh token from the dashboard. |
| Bot starts but doesn't reply to `/start` on Telegram | Wrong `TELEGRAM_BOT_TOKEN`, or your chat id isn't in `ALLOWED_CHAT_IDS`. |
| Webhook returns 401 | Header `X-Webhook-Secret` missing or doesn't match `.env`. |
| Webhook returns 502 from Cloudflare | The dashboard ingress points at the wrong service. Must be `http://pogo-scout:8000`. |
| `Permission denied` writing `/data/pogo_scout.db` in logs | `data/` is owned by host root, not uid 568. Run `sudo chown -R 568:568 /opt/stacks/pogo-scout/data`. |
