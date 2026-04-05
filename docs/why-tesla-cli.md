# Why tesla-cli?

## The Ultimate Tesla Management Platform

tesla-cli is the only tool that covers the entire Tesla ownership lifecycle — from order placed to daily driving — in a single, self-hosted, scriptable platform. Where every other tool solves one problem, tesla-cli solves all of them.

---

## Free vs Paid

| Feature | tesla-cli | Tessie ($12/mo) | TeslaMate (free) | TeslaFi ($8/mo) |
|---------|:---------:|:---------------:|:-----------------:|:---------------:|
| Vehicle control | ✅ 140+ commands | ✅ App only | ❌ | ❌ |
| Order tracking | ✅ | ❌ | ❌ | ❌ |
| Charging analytics | ✅ | ✅ | ✅ | ✅ |
| Automation engine | ✅ | ✅ | ❌ | ❌ |
| Real-time telemetry | ✅ Self-hosted | Via API | Via polling | Via polling |
| Web dashboard | ✅ Self-hosted | ✅ Cloud | Via Grafana | ✅ Cloud |
| CLI/scriptable | ✅ | ❌ | ❌ | ❌ |
| REST API | ✅ 70+ endpoints | ❌ | ❌ | ❌ |
| Privacy (self-hosted) | ✅ | ❌ Cloud | ✅ | ❌ Cloud |
| Powerwall/Solar | ⏳ Soon | ✅ | ✅ | ✅ |
| Claude AI plugin | ✅ | ❌ | ❌ | ❌ |
| Price | **Free** | $155/year | Free | $96/year |

---

## Self-Hosted & Private

Your vehicle data stays on your machine. No cloud account, no subscription, no third-party access to your driving patterns.

- Credentials stored in your system keyring — never plain text, never env vars
- TeslaMate stack managed locally via `tesla infra up/down`
- Prometheus metrics (27 gauges) exported to your own Grafana
- MQTT + Home Assistant auto-discovery over your local network

---

## Scriptable & Extensible

Every command speaks JSON. Every data command has `--json` and many have `--oneline` for tmux/polybar widgets:

```bash
# Status line for your bar
tesla vehicle status-line
# "75% | 22°C | Locked | Home"

# Daily companion
tesla vehicle ready
tesla charge last
tesla charge weekly

# Automate on state change
tesla vehicle watch --on-change-exec "notify-send 'Tesla' 'State changed'"

# Pipe into anything
tesla charge sessions --json | jq '.[-5:] | .[].energy_added'

# Schedule charging
tesla charge schedule --time 23:00 --limit 90

# Full climate control
tesla vehicle climate --temp 22 --seat-driver 3 --bioweapon-mode
```

The REST API (70+ endpoints, FastAPI) lets any service on your network query vehicle state, trigger commands, and subscribe to SSE streams.

---

## AI-Native

tesla-cli ships a Claude Code plugin (9 skills) that lets you control your vehicle conversationally:

```
"What's my charge state?"
"Precondition the car for 8am"
"Show me last month's charging costs"
```

No other Tesla tool integrates with an AI coding assistant at this depth.

---

## Order Tracking Nobody Else Does

From reservation to delivery, tesla-cli tracks every field change in your order:

```bash
tesla order status          # Full order snapshot
tesla order status --oneline  # Compact emoji output: "🚗 VIN assigned | 📅 Est. Feb 14"
tesla order diff            # What changed since last check
tesla order history         # Timeline of all field changes
```

Includes VIN decode, NHTSA recall lookup, and ship/rail tracking — all from one command.

---

## Multi-Backend, Future-Proof

The Owner API sunset doesn't break tesla-cli. Three backends, one interface:

| Backend | Best for |
|---------|----------|
| `owner` | Legacy vehicles, broad data access |
| `fleet` | Modern VINs (2024+), signed commands |
| `tessie` | No key enrollment needed, instant setup |

Switch backends with `tesla config set backend fleet`. Commands don't change.

---

## When to Use Something Else

tesla-cli is a power-user tool. If you want a polished mobile app, use the official Tesla app or Tessie. If you only need trip/charge dashboards and no CLI, TeslaMate is excellent. tesla-cli is for people who want to script, automate, and own their data.
