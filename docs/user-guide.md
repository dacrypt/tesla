# User Guide

Complete command reference for tesla-cli. For installation, see [README](../README.md). For configuration details, see [configuration.md](configuration.md).

---

## Global Flags

```bash
tesla -j <command>         # JSON output (pipe to jq)
tesla --json <command>     # same
tesla --vin modely <cmd>   # target specific vehicle (VIN or alias)
tesla --anon <command>     # anonymize PII (VIN, RN, email masked)
tesla --lang es <command>  # Spanish output (also: TESLA_LANG=es)
tesla --verbose <command>  # debug logging
```

Supported languages: `en` (default), `es`, `pt`, `fr`, `de`, `it`.

---

## 1. Order Tracking

```bash
tesla order status                 # order status, VIN, model, delivery window
tesla order details                # full: status + tasks + vehicle + delivery + financing
tesla order watch                  # monitor changes every 10 min
tesla order watch -i 5             # every 5 min
tesla order watch --no-notify      # without notifications
tesla order watch --on-change-exec "echo changed"  # shell automation hook
tesla order eta                    # delivery ETA (best/typical/worst)
tesla order stores                 # Tesla store/SC locations (--country, --city, --near lat,lon)
```

### Authentication

```bash
tesla config auth order
```

**Option 1 — Browser (OAuth2 + PKCE)**: browser opens, log in, copy redirect URL, paste in terminal.
**Option 2 — Refresh token**: paste an existing refresh token directly.

---

## 2. Notifications

Uses [Apprise](https://github.com/caronc/apprise) — supports 100+ services.

```bash
tesla notify add tgram://BOT_TOKEN/CHAT_ID      # Telegram
tesla notify add discord://webhook_id/token      # Discord
tesla notify add ntfy://my-tesla                 # ntfy.sh
tesla notify list                                # show configured channels
tesla notify test                                # send test to all channels
tesla notify remove 1                            # remove channel #1

tesla notify set-template "{event}: {vehicle} -- {detail}"
tesla notify show-template
```

Template placeholders: `{event}`, `{vehicle}`, `{detail}`, `{ts}`.

---

## 3. Vehicle Control

### Backend setup

| Backend | Setup | Cost |
|---------|-------|------|
| **Owner API** (recommended) | `tesla config set backend owner` | Free |
| **Tessie** | `tesla config auth tessie` | ~$13/month |
| **Fleet API** | `tesla config set client-id ID && tesla config auth fleet` | Free* |

### Information

```bash
tesla vehicle list             # list all your Teslas
tesla vehicle info             # full vehicle data
tesla vehicle bio              # comprehensive single-screen profile (5 panels)
tesla vehicle location         # GPS + Google Maps link
tesla vehicle health-check     # 7-point system check
tesla vehicle software         # current version + pending update
tesla vehicle summary          # compact one-screen snapshot
tesla vehicle summary --oneline  # single line for tmux/cron: 🔋 72% | 🔒 Locked | 🛡 Sentry ON
tesla vehicle export           # JSON to stdout
tesla vehicle export -o car.json  # JSON to file
tesla vehicle export -f csv -o car.csv  # CSV with flattened fields
tesla vehicle stream           # live telemetry (Rich dashboard, 5s refresh)
tesla vehicle stream --interval 10 --count 20
tesla vehicle dashboard        # unified multi-panel status view
tesla vehicle alerts           # recent fault codes and warnings
tesla vehicle ready            # morning check: am I ready to drive?
tesla vehicle ready --oneline  # ✅ Ready | 🔋 82% | 🌡 22°C
tesla vehicle status-line      # ultra-compact: 🔋72% 🔒 🛡 🌡22° (for tmux/polybar)
tesla vehicle last-seen        # online/asleep + last contact time
tesla vehicle invite           # create driver invitation
tesla vehicle invitations      # list driver invitations
```

### Charging

```bash
tesla charge status            # state: %, range, time remaining
tesla charge start / stop
tesla charge set-limit 80      # charge limit (50-100%)
tesla charge set-amps 16       # charge current (1-48A)
tesla charge profile           # view/set limit + amps + schedule
tesla charge forecast          # ETA + kWh estimate to target SoC
tesla charge schedule-amps 22:00 32  # time + amperage together
tesla charge limit             # show/set limit
tesla charge amps              # show/set amps
tesla charge sessions          # unified sessions (TeslaMate + Fleet API)
tesla charge sessions -n 50    # last 50 sessions
tesla charge cost-summary      # aggregated cost report
tesla charge history           # Fleet API raw history
tesla charge sessions --csv charges.csv  # export to CSV
tesla charge cost-summary --csv costs.csv
tesla charge schedule-preview  # show charge + departure schedule
tesla charge schedule-preview --oneline  # 🔌 Charge @ 23:30 | 🚗 Depart @ 07:00
tesla charge last              # most recent session with cost
tesla charge weekly            # weekly kWh, cost, sessions
tesla charge weekly --weeks 8  # last 8 weeks
tesla charge invoices           # Supercharging invoices (Tessie backend)
tesla charge invoices --csv invoices.csv  # export
```

### Climate

```bash
tesla climate status           # inside/outside temperature
tesla climate on / off
tesla climate set-temp 22.5    # target temperature (C)
tesla climate temp             # show/set (--passenger)
tesla climate seat driver 3    # seat heater (0-3)
tesla climate steering-wheel --on / --off
```

### Security

```bash
tesla security lock / unlock
tesla security trunk rear      # open trunk
tesla security trunk front     # open frunk
tesla security remote-start    # keyless drive
```

### Sentry & Cabin Protection

```bash
tesla vehicle sentry               # show status
tesla vehicle sentry --on / --off
tesla vehicle sentry-events        # recent events (TeslaMate)

tesla vehicle cabin-protection               # show status
tesla vehicle cabin-protection --on / --off
tesla vehicle cabin-protection --level FAN_ONLY  # FAN_ONLY | NO_AC | CHARGE_ON
```

### Windows & Charge Port

```bash
tesla vehicle windows vent / close
tesla vehicle charge-port open / close / stop
```

### Software Updates

```bash
tesla vehicle software             # current + pending
tesla vehicle software --install   # schedule pending update
tesla vehicle schedule-update --delay 30  # schedule after N minutes
tesla vehicle sw-update --watch --notify  # watch for OTA, notify via Apprise
```

### Watch / Live Monitor

```bash
tesla vehicle watch            # live Rich dashboard, refresh every 5s
tesla vehicle watch --interval 10
tesla vehicle watch --all      # watch ALL vehicles simultaneously
tesla vehicle watch --all --notify  # per-vehicle Apprise notifications
```

### Other

```bash
tesla vehicle horn / flash / wake
tesla vehicle speed-limit              # view
tesla vehicle speed-limit --on 90      # activate at 90 mph
tesla vehicle speed-limit --off
tesla vehicle tires                    # TPMS pressure
tesla vehicle homelink                 # trigger garage door
tesla vehicle dashcam                  # save clip to USB
tesla vehicle rename "My Tesla"
tesla vehicle map                      # ASCII terminal map
```

### Media & Navigation

```bash
tesla media play / pause       # toggle media playback
tesla media next / prev        # next/previous track
tesla media volume 7.5         # set volume (0-11)
tesla media fav                # next favorite
tesla media send-destination "123 Main St, Austin TX"  # send nav destination
tesla media supercharger       # navigate to nearest Supercharger
tesla media home               # navigate home
tesla media work               # navigate to work
```

### Multi-Vehicle

```bash
tesla config alias modely YOUR_VIN
tesla config alias model3 OTHER_VIN
tesla vehicle info --vin modely
tesla charge status --vin model3
tesla vehicle watch --all
```

---

## 4. Vehicle Identity & Specs

VIN decoding, option codes, battery health, and complete vehicle profile:

```bash
tesla vehicle vin                      # decode your configured VIN
tesla vehicle vin 7SAYGDEF1TF123456    # decode any Tesla VIN
tesla vehicle option-codes             # decode Tesla option codes
tesla vehicle battery-health           # degradation from snapshot history
tesla vehicle profile                  # complete multi-source profile (Tesla + RUNT + NHTSA)
```

---

## 4b. Order Lifecycle (Delivery Pipeline)

Delivery tracking: gates, inspection checklist, ship tracking, delivery estimates.

```bash
tesla order gates                      # 13-gate delivery journey tracker
tesla order estimate                   # community delivery date estimation
tesla order checklist                  # 34-item delivery inspection
tesla order checklist --mark 5,12      # check items off
tesla order ships                      # Tesla car carrier ship tracking
tesla order set-delivery 2026-04-15    # set confirmed delivery date
tesla order documents            # list portal documents
tesla order documents --download # download all
tesla order status --oneline     # compact status
```

---

## 4c. Data Aggregation & Export

Build, compare, and export vehicle data from all sources:

```bash
tesla data build                      # query all sources, save snapshot
tesla data history                    # view snapshot history
tesla data diff                       # compare last two snapshots
tesla data diff 1 3                   # compare specific snapshots
tesla data data-sources               # show all 15 data sources + cache status
tesla data clean                      # prune old snapshots
tesla data export-html                # dark theme (default)
tesla data export-html --theme light
tesla data export-pdf                 # requires pdf extra
```

> The `data` group includes both vehicle data management (build/export) and Colombian public data queries (RUNT, SIMIT, etc.).

---

## 4d. Source-First Domains & Event Streams

Inspect the new derived model directly from the CLI:

```bash
tesla domain list                    # all derived domain projections
tesla domain show delivery           # delivery projection
tesla domain show legal              # legal/registration projection
tesla domain show financial          # payment, lender, valuation, fines debt
tesla domain show safety             # recalls, complaints, investigations
tesla domain show identity           # VIN/model/manufacturer/plant summary
tesla domain show source_health      # fleet-wide source freshness and errors

tesla alerts                         # active alerts
tesla alerts --all                   # include resolved alerts
tesla alerts --ack alt_123           # acknowledge one alert
tesla events                         # recent source/domain events
tesla events --limit 100
```

These commands expose the same source-first architecture used by Mission Control:
- per-source state
- derived domains
- persistent events
- persistent alerts

---

## 5. Fleet Telemetry

Self-hosted real-time vehicle streaming — zero polling, zero vampire drain.

### Setup

```bash
tesla telemetry install          # Docker stack + TLS certificates
tesla telemetry start            # start the server
tesla telemetry configure        # configure which fields to stream
tesla telemetry status           # check health
```

### Streaming

```bash
tesla vehicle stream-live                    # real-time dashboard
tesla vehicle stream-live --fields battery_level,speed  # specific fields
tesla vehicle stream-live --oneline          # compact output
```

### Management

```bash
tesla telemetry stop             # stop the server
tesla telemetry restart          # restart
tesla telemetry logs             # view server logs
tesla telemetry stop-streaming   # remove streaming config from vehicle
```

---

## 6. Automations

Config-driven rule engine — triggers fire notifications or commands automatically.

### Quick Start

```bash
tesla automations list           # show all rules
tesla automations add            # interactive rule builder
tesla automations run            # start watching (foreground)
tesla automations install        # install as background service
```

### Default Rules

`tesla setup` creates three default rules:
- **Low battery** — notify when battery drops below 20%
- **Charge complete** — notify when charging finishes
- **Sentry event** — notify on sentry mode events

### Custom Rules

```bash
tesla automations add            # interactive
tesla automations remove <name>  # delete a rule
tesla automations enable <name>  # enable
tesla automations disable <name> # disable
tesla automations test <name>    # dry-run against live data
```

### Daemon

```bash
tesla automations install        # install as launchd (macOS) or systemd (Linux) service
tesla automations uninstall      # remove background service
tesla automations status         # service health + rule summary
tesla automations run --source mqtt  # use MQTT instead of polling
```

---

## 7. TeslaMate Integration

Connect to your [TeslaMate](https://github.com/adriankumpf/teslamate) PostgreSQL database.

```bash
tesla teslaMate connect postgresql://user:pass@localhost:5432/teslaMate

tesla teslaMate status               # lifetime stats + connection
tesla teslaMate trips                # last 20 trips (--limit N)
tesla teslaMate charging             # last 20 charging sessions
tesla teslaMate updates              # OTA history
tesla teslaMate timeline             # unified events (--days N)
tesla teslaMate cost-report          # monthly cost (--month YYYY-MM)
tesla teslaMate trip-stats           # summary + top routes (--days N)
tesla teslaMate charging-locations   # top locations (--days N --limit N)
tesla teslaMate heatmap              # drive days calendar (--year N)
tesla teslaMate graph                # ASCII bar chart of charging sessions
tesla teslaMate vampire              # vampire drain analysis
tesla teslaMate efficiency           # per-trip energy efficiency
tesla teslaMate daily-chart          # daily kWh chart (--days N)
tesla teslaMate report               # monthly summary (DC vs AC, Wh/km)
tesla teslaMate stats                # lifetime stats
tesla teslaMate geo                  # most-visited locations
tesla teslaMate grafana              # open Grafana dashboards
tesla teslaMate drive-path <ID>           # export drive as GPX
tesla teslaMate drive-path <ID> -f geojson  # export as GeoJSON
```

Requires: `uv tool install -e ".[teslaMate]"`

### Managed TeslaMate Stack (v4.0.0)

```bash
tesla teslaMate install              # auto-provision Docker stack
tesla teslaMate start / stop / restart
tesla teslaMate update               # update containers
tesla teslaMate logs                 # container logs
tesla teslaMate uninstall
```

---

## 8. MQTT Integration

```bash
tesla mqtt setup           # interactive broker configuration
tesla mqtt status          # connection test
tesla mqtt test            # publish one test message
tesla mqtt publish         # single publish of current state

tesla mqtt ha-discovery    # publish 15 HA sensor auto-discovery payloads (retained)
```

Sensors: battery level, range, charge limit, charging state, charger power, energy added, odometer, inside/outside temp, GPS, speed, locked, sentry mode, software version.

---

## 9. Home Assistant

```bash
tesla ha setup             # configure HA URL + token
tesla ha status            # connectivity check
tesla ha push              # push current state (18 sensor entities)
tesla ha sync              # continuous sync
```

---

## 10. ABRP (A Better Route Planner)

```bash
tesla abrp setup           # configure ABRP token
tesla abrp status          # check connection
tesla abrp send            # push current telemetry
tesla abrp stream          # continuous telemetry push
```

---

## 11. BLE Control

Local Bluetooth commands (proximity required, wraps `tesla-control`):

```bash
tesla ble status           # check binary + key
tesla ble setup-key        # enroll BLE key
tesla ble lock / unlock
tesla ble climate-on / climate-off
tesla ble charge-start / charge-stop
tesla ble flash / honk
```

---

## 12. Geofencing

```bash
tesla geofence add "Home" 4.711 -74.072 200    # name lat lon radius_m
tesla geofence list
tesla geofence remove "Home"
tesla geofence watch       # monitor enter/exit with Apprise alerts
```

---

## 13. Live Telemetry Stream

```bash
tesla stream live                    # refresh every 5s
tesla stream live --interval 10      # every 10s
tesla stream live --count 20         # stop after 20 refreshes
tesla stream live --mqtt             # publish to MQTT simultaneously
```

Real-time Rich dashboard: battery, charge rate, temperature, GPS, locks, sentry, software, odometer.

---

## 14. REST API Server

```bash
tesla serve                 # http://localhost:8000
tesla serve --port 9000
tesla serve --host 0.0.0.0
tesla serve --daemon        # detach to background
tesla serve stop            # stop background server
tesla serve status          # running/stopped + PID
tesla serve install-service # generate systemd/launchd service file
```

See [api-reference.md](api-reference.md) for full endpoint documentation.

### Mission Control read models

Once the server is running, the React UI and API expose the new source-first read models:

```bash
# API surfaces
GET /api/mission-control
GET /api/mission-control/dashboard-summary
GET /api/domains
GET /api/events
GET /api/alerts

# UI routes
/dashboard   # executive Mission Control
/alerts      # persisted alerts stream
/timeline    # persisted event stream
```

---

## 15. Config Management

```bash
tesla config show / set / alias / auth
tesla config validate          # health check (exit 0/1)
tesla config migrate           # update to current schema
tesla config backup / restore
tesla config doctor            # deep health check
tesla config encrypt-token / decrypt-token
```

See [configuration.md](configuration.md) for full reference.

---

## 16. Provider Registry

```bash
tesla providers                    # show all providers + availability
tesla providers test               # deep health check (network calls)
tesla providers capabilities       # capability map
```

---

## 17. Privacy & JSON

```bash
tesla --anon order status          # VIN and RN masked
tesla --anon dossier show          # safe to screenshot

tesla -j order status              # raw JSON
tesla -j order status | jq .raw    # raw API response
tesla -j charge status | jq .battery_level

# Save snapshot
tesla -j order status > ~/tesla-order-$(date +%Y%m%d).json

# CSV export (TeslaMate commands)
tesla teslaMate trips --csv
tesla teslaMate charging --csv
```
