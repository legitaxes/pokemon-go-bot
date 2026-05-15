# Deploying pogo-scout as a Dockge stack

Deployment model: paste `compose.yaml` into Dockge's UI. No repo on the host.
Image is built by GitHub Actions and published to
`ghcr.io/legitaxes/pokemon-go-bot:latest` (multi-arch: linux/amd64 + linux/arm64).

Public access: **Tailscale Funnel** (free, no domain required). The bot is
reachable at `https://pogo-scout.<your-tailnet>.ts.net/webhook` over the
public internet, while everything else (`/healthz`, etc.) returns 404 at
Tailscale's edge.

Two containers run in the stack:

| Container | Purpose |
|---|---|
| `pogo-scout` | The bot. FastAPI webhook + Telegram client. |
| `pogo-scout-tailscale` | Tailscale sidecar. Joins your tailnet, exposes `/webhook` via Funnel. |

The homeserver never exposes port 8000 publicly. `/webhook` reaches the bot only
through the Tailscale edge (path-scoped).

---

## One-time: make the GHCR package public

The first push to `main` triggered a GitHub Actions run that published the image
to `ghcr.io/legitaxes/pokemon-go-bot`. Packages start **private**, so the Dockge
host can't pull them anonymously. Make it public once:

1. https://github.com/legitaxes?tab=packages
2. Click `pokemon-go-bot` → **Package settings** (right sidebar)
3. **Danger Zone** → **Change visibility** → **Public** → confirm.

(You only do this once. After that, every push to `main` rebuilds the same public image.)

---

## 1. Set up Tailscale (free account, ~5 min)

If you already use Tailscale, skip to step 1.4.

### 1.1 Create a Tailscale account
Go to https://login.tailscale.com/start. Sign up with Google / GitHub / Microsoft / etc.
The Free plan covers personal use (up to 100 devices).

### 1.2 Enable Funnel
1. Open https://login.tailscale.com/admin/dns
2. Verify **MagicDNS** is enabled. (It is by default.)
3. Open https://login.tailscale.com/admin/settings/funnel
4. Confirm Funnel is enabled. (It is by default; if not, toggle it on.)

### 1.3 Generate an auth key
1. Open https://login.tailscale.com/admin/settings/keys
2. Click **Generate auth key…**
3. Settings:
   - **Reusable**: ✅ on (so you can re-deploy without regenerating)
   - **Ephemeral**: ❌ off (we want persistent state in `./data/ts-state`)
   - **Pre-approved**: ✅ on (skips a manual approval step)
   - **Tags**: optional (e.g. `tag:pogo-scout`); leave blank for simplicity
   - Expiry: 90 days is fine — the key is only used at first start. After that,
     the container's stored credentials handle re-auth automatically.
4. Generate, copy the key (`tskey-auth-...`).

### 1.4 Note your tailnet name
On https://login.tailscale.com/admin/machines you'll see your tailnet header,
e.g. `mycoolname.ts.net`. Your bot will be reachable at
`pogo-scout.mycoolname.ts.net` after deploy.

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

In the stack page, click the **Env** tab. Paste:

```env
TELEGRAM_BOT_TOKEN=<token from @BotFather>
WEBHOOK_SECRET=<output of: openssl rand -hex 32>
ALLOWED_CHAT_IDS=<your numeric chat id, from @userinfobot>
TS_AUTHKEY=<the auth key from step 1.3>
```

Save. Dockge writes this to `/opt/stacks/pogo-scout/.env`.

---

## 4. Create `data/config.yaml` on the host

The bot needs `home_lat` / `home_lng` at boot. One-time SSH on the Dockge host:

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
to the SQLite DB.

---

## 5. Deploy, then enable Funnel (one-time)

In Dockge: hit **Start** on the stack.

Tail logs via the **Logs** tab; you should see:
- `pogo-scout-tailscale`: `Success.` and a node URL like `https://pogo-scout.<tailnet>.ts.net`
- `pogo-scout`: `Uvicorn running on http://0.0.0.0:8000`

Now enable Funnel for `/webhook` — run this **once** on the Dockge host:

```bash
sudo docker exec pogo-scout-tailscale \
  tailscale funnel --bg --set-path=/webhook http://localhost:8000/webhook
```

You'll see Tailscale confirm `Available on the internet` with your funnel URL.
The state is persisted in `./data/ts-state`, so future container restarts
automatically re-enable Funnel without re-running this command.

To verify it's listening:
```bash
sudo docker exec pogo-scout-tailscale tailscale funnel status
```

---

## 6. Smoke test

From your laptop:
```bash
curl -X POST https://pogo-scout.<your-tailnet>.ts.net/webhook \
  -H "X-Webhook-Secret: <your WEBHOOK_SECRET>" \
  -H "Content-Type: application/json" \
  --data '[{"type":"monster","message":{"pokemon_id":25,"latitude":1.3521,"longitude":103.8198,"individual_attack":15,"individual_defense":15,"individual_stamina":15,"disappear_time":9999999999}}]'
```
(Substitute your home coords for 1.3521/103.8198.) Telegram message arrives
within ~2 s if Pikachu is on your wanted list, else logged as `NO_MATCH`.

Confirm `/healthz` is **NOT** publicly accessible:
```bash
curl -i https://pogo-scout.<your-tailnet>.ts.net/healthz
# Expect: HTTP 404 from Tailscale. The bot never sees this request.
```

---

## 7. Hand the URL + secret to your SG scanner community

- URL: `https://pogo-scout.<your-tailnet>.ts.net/webhook`
- Header: `X-Webhook-Secret: <your WEBHOOK_SECRET>`

The bot rejects any request missing the matching secret.

---

## 8. Updates

When you push code to `main`, GitHub Actions rebuilds and republishes `:latest`
within a couple of minutes. In Dockge, hit **Stop** then **Start** (or **Update**)
— `pull_policy: always` ensures the new image is fetched.

CLI form:
```bash
sudo docker compose -f /opt/stacks/pogo-scout/compose.yaml pull
sudo docker compose -f /opt/stacks/pogo-scout/compose.yaml up -d
```

DB migrations apply automatically on startup. Funnel state survives restarts.

---

## 9. Backups

SQLite DB lives at `/opt/stacks/pogo-scout/data/pogo_scout.db`. Daily backup:

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
| Stack won't start: `denied: not authorized` pulling the image | GHCR package still private. See **One-time: make the GHCR package public**. |
| `pogo-scout-tailscale` keeps restarting | `TS_AUTHKEY` blank, expired, or already used (non-reusable). Generate a new reusable key from the admin console. |
| `pogo-scout-tailscale` logs `permission denied: /dev/net/tun` | Host kernel doesn't have the `tun` module loaded. Run `sudo modprobe tun` on the host, or set `TS_USERSPACE=true` in compose.yaml. |
| `tailscale funnel` returns "funnel not available" | Funnel not enabled for your tailnet. See step 1.2. |
| Webhook returns 401 | Header `X-Webhook-Secret` missing or doesn't match `.env`. |
| Webhook returns 404 from Tailscale | The funnel rule was never set up, or it points at the wrong path. Re-run the `tailscale funnel` command from step 5 and verify with `tailscale funnel status`. |
| `/healthz` is reachable publicly | Your funnel was set up without `--set-path=/webhook`. Reset with `tailscale funnel reset` then re-run the command from step 5. |
| `Permission denied` writing `/data/pogo_scout.db` | `data/` owned by host root, not uid 568. `sudo chown -R 568:568 /opt/stacks/pogo-scout/data`. |
