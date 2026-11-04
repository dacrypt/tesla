# Self-hosting guide

tesla-cli is built to run on hardware you own — a home server, NAS, Raspberry
Pi or VPS. There is no hosted/SaaS version. This guide covers a production
setup: installation, remote access, upgrades and backups.

## 1. Install

### Docker (recommended)

Prebuilt images for `linux/amd64` and `linux/arm64` are published to
`ghcr.io/dacrypt/tesla-cli` on every release (`latest`, `X.Y.Z`, `X.Y`).

```bash
curl -O https://raw.githubusercontent.com/dacrypt/tesla/main/docker-compose.yml
docker compose up -d
docker compose logs tesla-cli | grep -A1 "API key generated"   # first start only
```

Pin a version for reproducible upgrades: `TESLA_CLI_TAG=5.4.0 docker compose up -d`.

Full stack with TeslaMate, Grafana, Postgres and Mosquitto:
`docker-compose.full.yml` (requires `DB_PASSWORD`, `ENCRYPTION_KEY`,
`GRAFANA_PASSWORD` in `.env` — see the README).

### Bare metal / VM

```bash
uv tool install "tesla-cli[serve,fleet]"    # or: pipx install ...
tesla setup
tesla serve install-service --host 0.0.0.0   # systemd (Linux) / launchd (macOS)
```

## 2. Security model (read this)

- Binding beyond `127.0.0.1` **requires an API key**; one is generated on first
  start. Show or rotate it with `tesla serve api-key [--rotate]`. A read-only
  key for wall displays / Home Assistant: `tesla serve api-key --read-only --rotate`.
- The dashboard signs in once with the key and keeps an HttpOnly cookie.
- Cross-site requests and DNS-rebinding attempts are blocked; raw vehicle
  commands are allowlisted (`server.extra_allowed_commands` to extend).
- Tokens live in the OS keyring, or — in Docker/headless — in an AES-256-GCM
  encrypted file. Keep the master key outside the volume with
  `TESLA_CLI_MASTER_KEY_FILE` (Docker secret).
- Every state-changing API call is written to `~/.tesla-cli/events/audit.jsonl`
  (secrets redacted). `GET /api/audit` shows it.

## 3. Remote access

Never port-forward the API to the internet. Pick one:

| Option | Effort | Notes |
|--------|--------|-------|
| **Tailscale / WireGuard** | low | Best default. Reach `http://<tailnet-host>:8080` from your phone; nothing is exposed publicly. |
| **Reverse proxy with HTTPS** (Caddy, Traefik, nginx) | medium | Terminate TLS at the proxy; keep the API key. With the proxy on the same host, uvicorn trusts its `X-Forwarded-Proto` and the session cookie is marked `Secure`. |
| **Cloudflare Tunnel + Access** | medium | Put Cloudflare Access (SSO) in front; keep the API key as a second factor. |

Caddy example (`Caddyfile`):

```
tesla.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Only if the proxy itself authenticates every request may you run
`tesla serve --insecure-no-auth`; add the public hostname to
`server.allowed_hosts`.

TeslaMate, Grafana and Mosquitto bind to `127.0.0.1` by default
(`STACK_BIND` / `TM_BIND_ADDR` to change) — they have weak or no auth of their
own, so reach them through the same VPN/proxy.

## 4. Upgrades

```bash
docker compose pull && docker compose up -d        # Docker
uv tool upgrade tesla-cli && tesla config migrate   # bare metal
```

`config.toml` carries a `schema_version`; older files are migrated
automatically on load, and `tesla config migrate` writes the upgraded file
(keeping a `0600` backup). Read the CHANGELOG "Upgrading" section of each
release before jumping major versions.

## 5. Backups

Everything tesla-cli owns lives in one directory (`~/.tesla-cli`, or the
`tesla-config` Docker volume):

| Path | Contents |
|------|----------|
| `config.toml` | settings, API keys, integration tokens (secret) |
| `tokens.enc.json` + `master.key` | encrypted Tesla OAuth tokens (Docker/headless) |
| `events/` | events, alerts, audit log |
| `dossier/`, source caches | vehicle dossier and data-source history |

```bash
# Docker volume → encrypted-at-rest location of your choice
docker run --rm -v tesla-config:/data -v "$PWD":/backup alpine \
  tar czf /backup/tesla-cli-$(date +%F).tgz -C /data .
chmod 600 tesla-cli-*.tgz
```

Treat backups as secrets. If you keep `master.key` outside the volume (Docker
secret), back it up separately — tokens cannot be decrypted without it.
TeslaMate data lives in Postgres: `docker exec tesla-postgres pg_dump -U teslamate teslamate > teslamate.sql`.

## 6. Health and troubleshooting

- `GET /api/health` (public) for uptime checks; `GET /api/health?deep=true`
  and `tesla doctor` for diagnostics.
- `tesla --debug <command>` (or `TESLA_LOG_LEVEL=DEBUG`) prints suppressed
  errors with tracebacks.
- Features built on unofficial Tesla endpoints (order tracking, ownership
  portal scraping) and Colombian registry scrapers (RUNT, SIMIT) can break
  without notice when the upstream site changes.

## Maintainer note: GHCR visibility

The first image push creates the `tesla-cli` package as **private**. Make it
public once in GitHub → Packages → tesla-cli → Package settings → Change
visibility, so `docker compose pull` works without a login.
