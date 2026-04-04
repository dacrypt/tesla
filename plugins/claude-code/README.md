# Tesla Plugin for Claude Code

Control your Tesla from Claude Code -- natural language vehicle management, charging analytics, order tracking, and a self-hosted web dashboard.

```
You: "how's my battery?"
Claude: Your Model Y is at 78%, plugged in at home charging at 11 kW.
        Estimated 1h 12m to reach your 80% limit.

You: "turn on the AC and set to 21"
Claude: I'll turn on climate and set the temperature. Can you confirm? (unlock/climate/trunk commands always require your OK)
You: "yes"
Claude: Done -- HVAC is on, target 21 C. Interior is currently 34 C, should cool down in ~10 min.
```

## Install

### 1. Install the CLI (execution engine)

```bash
uv tool install tesla-cli
```

With optional features:

```bash
uv tool install "tesla-cli[serve,teslaMate,fleet,pdf]"
```

### 2. Set up your Tesla account

```bash
tesla setup
```

The interactive wizard handles OAuth2 authentication, VIN discovery, backend selection, and first data build.

### 3. Install the plugin

**Step A** — Register the Tesla marketplace (once):

```bash
claude settings set extraKnownMarketplaces.tesla.source.source git
claude settings set extraKnownMarketplaces.tesla.source.url https://github.com/dacrypt/tesla-claude-plugin.git
```

Or manually add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "tesla": {
      "source": {
        "source": "git",
        "url": "https://github.com/dacrypt/tesla-claude-plugin.git"
      }
    }
  }
}
```

**Step B** — Install the plugin in Claude Code:

```
/plugin install tesla@tesla
```

Restart Claude Code and the plugin is ready.

### 4. Use it

Just talk to Claude about your Tesla. Or use slash commands:

```
/tesla:status           # quick vehicle status
/tesla:control lock     # lock doors (with confirmation)
/tesla:charge weekly    # weekly charging cost summary
/tesla:order status     # delivery tracking
/tesla:dossier build    # vehicle intelligence from 15+ sources
/tesla:analytics trips  # TeslaMate trip history
/tesla:serve            # start web dashboard
/tesla:setup            # first-time onboarding
```

## Skills

| Skill | Command | Purpose |
|-------|---------|---------|
| **status** | `/tesla:status` | Battery, location, climate, readiness |
| **control** | `/tesla:control` | Lock, unlock, climate, trunk, horn, sentry |
| **charge** | `/tesla:charge` | Charge state, sessions, costs, forecast |
| **order** | `/tesla:order` | Order tracking, delivery ETA, inspection checklist |
| **dossier** | `/tesla:dossier` | VIN decode, recalls, specs, data sources |
| **analytics** | `/tesla:analytics` | Trips, costs, battery health (TeslaMate) |
| **serve** | `/tesla:serve` | Start web dashboard + REST API |
| **setup** | `/tesla:setup` | Install + configure tesla-cli |

Plus a background context skill that auto-loads your vehicle config and charging state.

## How it works

```
You <--chat--> Claude Code
                  |
          tesla-claude-plugin (AI interface)
                  |
              tesla-cli (execution engine)
                  |
        Tesla APIs / TeslaMate / MQTT / HA
```

The plugin teaches Claude *when* to run *which* `tesla` command and how to interpret the output. All logic lives in the CLI -- the plugin never duplicates it.

## Security

- **Credentials in system keyring** -- never in files, env vars, or skill content
- **Zero PII in the plugin** -- no VINs, order numbers, or names. Everything resolved at runtime
- **Destructive action confirmation** -- unlock, trunk, sentry off always require your OK
- **100% local** -- no telemetry, no cloud relay, self-hosted
- **PII anonymization** -- `tesla --anon` masks sensitive data for screenshots/demos

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Tesla account with at least one vehicle or active order
- Claude Code with plugin support

## Optional integrations

| Integration | What it adds | Setup |
|-------------|-------------|-------|
| **TeslaMate** | Deep analytics, trip history, charging costs | `tesla teslaMate install` |
| **MQTT** | Home Assistant discovery, broker publishing | `tesla mqtt setup` |
| **Home Assistant** | 18 sensor entities synced to HA | `tesla ha connect` |
| **ABRP** | Live route telemetry to A Better Route Planner | `tesla abrp setup` |
| **Notifications** | Push to Telegram, Discord, Slack, email, 100+ | `tesla notify add <url>` |
| **Grafana** | 27 Prometheus gauges for dashboards | `tesla serve` exposes `/api/metrics` |

## License

MIT
