# Configuration Reference

---

## Config File

Location: `~/.tesla-cli/config.toml`

### Sample config

```toml
[general]
default_vin = "7SAYGDEF..."
reservation_number = "RN126460939"
backend = "owner"                # owner | tessie | fleet
region = "na"                    # na | eu | cn (Fleet API only)
client_id = ""                   # Fleet API app client ID
notifications_enabled = true
cost_per_kwh = 0.22              # for charging cost calculations

[aliases]
modely = "7SAYGDEF..."
model3 = "5YJ3E1EA..."

[mqtt]
broker = "192.168.1.100"
port = 1883
topic_prefix = "tesla"
username = ""
password = ""
qos = 0
retain = false
tls = false

[server]
api_key = ""                     # optional; protects all /api/* routes
pid_file = "~/.tesla-cli/tesla-serve.pid"

[home_assistant]
url = "http://homeassistant.local:8123"
token = ""

[abrp]
token = ""
car_model = ""

[ble]
tesla_control_path = ""          # path to tesla-control binary

[grafana]
url = "http://localhost:3000"
```

---

## CLI Config Commands

```bash
tesla config show                          # show full config
tesla config set backend owner             # set a key
tesla config set default-vin 7SAYGDEF...   # set default vehicle
tesla config set cost-per-kwh 0.22         # for cost calculations
tesla config alias modely 7SAYGDEF...      # create VIN alias

tesla config validate                      # health check: format + values + reachability
                                           # exit 0 = ok, exit 1 = errors

tesla config migrate                       # update config to current schema (dry-run)
tesla config migrate --apply               # apply changes (auto-backup first)

tesla config backup                        # export config (token-redacted)
tesla config restore config-backup.toml    # import config

tesla config encrypt-token                 # AES-256-GCM encryption for headless servers
tesla config decrypt-token                 # reverse token encryption
```

---

## Config Keys (`tesla config set`)

| Key | Description | Values |
|-----|-------------|--------|
| `default-vin` | Default vehicle VIN | VIN string |
| `backend` | Vehicle control backend | `owner`, `tessie`, `fleet` |
| `reservation-number` | Order number | `RNXXXXXXXXX` |
| `region` | Fleet API region | `na`, `eu`, `cn` |
| `client-id` | Fleet API client ID | app ID string |
| `notifications-enabled` | Enable Apprise notifications | `true`, `false` |
| `cost-per-kwh` | kWh cost for charging reports | decimal (e.g. `0.22`) |
| `server.api_key` | API server auth key | any string |

---

## Authentication

### Token Storage

Tokens are stored in the system keyring (macOS Keychain / Linux Secret Service) — never in plain text.

| Key | Source | Used By |
|-----|--------|---------|
| `order-access-token` | Owner API OAuth (`client_id=ownerapi`) | OrderBackend, OwnerApiVehicleBackend |
| `order-refresh-token` | Owner API OAuth | Token refresh |
| `fleet-access-token` | Fleet API OAuth (app `client_id`) | FleetBackend |
| `fleet-refresh-token` | Fleet API OAuth | Token refresh |
| `tessie-token` | Tessie dashboard (paste) | TessieBackend |
| `fleet-client-secret` | developer.tesla.com | Partner registration |
| `teslamate-db-password` | TeslaMate stack install | TeslaMateBackend |
| `teslamate-grafana-password` | TeslaMate stack install | Grafana access |
| `teslamate-encryption-key` | TeslaMate stack install | TeslaMate encryption |

### Auth Commands

```bash
tesla config auth order          # Tesla OAuth2 (browser flow or paste refresh token)
tesla config auth tessie         # Paste Tessie API token
tesla config auth fleet          # Fleet API OAuth2 flow
```

### OAuth2 Flow (Tesla)

1. Browser opens `https://auth.tesla.com/oauth2/v3/authorize` with PKCE challenge
2. User logs in (email + password + MFA)
3. Tesla redirects to `https://auth.tesla.com/void/callback?code=...`
4. User copies the full URL back to the terminal
5. CLI exchanges code for access + refresh tokens
6. Tokens stored in system keyring

---

## Files and Directories

| Path | Contents |
|------|----------|
| `~/.tesla-cli/config.toml` | General configuration |
| `~/.tesla-cli/state/last_order.json` | Last known state (change detection) |
| `~/.tesla-cli/dossier/dossier.json` | Complete vehicle dossier |
| `~/.tesla-cli/dossier/snapshots/` | Historical snapshots (cumulative) |
| `~/.tesla-cli/sources/{id}.json` | Cached data source responses |
| `~/.tesla-cli/source_history/{id}.jsonl` | Append-only change log per source |
| `~/.tesla-cli/source_audits/{id}_{ts}.pdf` | Playwright screenshot/PDF evidence |
| System Keyring | Authentication tokens |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TESLA_LANG` | UI language (`en`, `es`, `pt`, `fr`, `de`, `it`) |
| `TESLA_API_KEY` | API server authentication key (alternative to config) |
