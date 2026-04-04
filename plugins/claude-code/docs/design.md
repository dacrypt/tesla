# Tesla Claude Plugin — Design Document

## Problem

Tesla owners who use Claude Code have no way to interact with their vehicle through natural language. The existing Tesla APIs require custom tooling, and the CLI tools that exist require memorizing dozens of commands.

## Solution

A Claude Code plugin that wraps [tesla-cli](https://github.com/dacrypt/tesla) — a full-stack Tesla management platform with 100+ commands, 45+ REST endpoints, and a React dashboard. The plugin is the AI interface layer; the CLI is the execution engine.

```
User: "how's my battery?"
  → Claude loads /tesla:charge skill
  → Runs: tesla charge status --json
  → Interprets JSON result
  → Responds: "Your Model Y is at 78%, charging at 11 kW. 1h 12m to 80%."
```

## Architecture

```
User ←chat→ Claude Code ←skills→ tesla-cli ←APIs→ Tesla / TeslaMate / MQTT / HA
```

### Key Design Decisions

**1. Plugin, not MCP server (v1)**
Skills are simpler to distribute — no running server, no port management, no daemon. The CLI is already installed and configured. MCP is a v2 evolution once the skill-based approach is validated.

**2. Dynamic context via shell injection**
Instead of hardcoding VINs or personal data:
```markdown
!`tesla config show --json 2>/dev/null || echo '{"error":"not configured"}'`
```
Claude Code executes this at skill-load time and injects the user's own vehicle data.

**3. Nine focused skills, not one monolith**
Each skill maps to a user intent (status, control, charge, order, dossier, analytics, setup, serve) plus a background context skill. This gives Claude better signal for when to activate each capability.

**4. CLI as execution engine**
The plugin never duplicates CLI logic. It teaches Claude which command to run for a given user intent and how to interpret the output. All business logic, API calls, caching, and auth live in the CLI.

**5. Confirmation for destructive actions**
Skills explicitly instruct Claude to confirm before: unlock, disable sentry, open trunk, remote-start, install OTA update.

## Skill Inventory

| Skill | Invocation | Claude auto-loads? | Purpose |
|-------|-----------|-------------------|---------|
| `tesla-context` | automatic | yes | Background: vehicle config, terminology, error patterns |
| `status` | `/tesla:status` | yes | Battery, location, climate, readiness |
| `control` | `/tesla:control` | no (user-only) | Lock, unlock, climate, trunk, horn, sentry |
| `charge` | `/tesla:charge` | yes | Charge state, sessions, costs, forecast |
| `order` | `/tesla:order` | yes | Delivery tracking, gates, ETA, checklist |
| `dossier` | `/tesla:dossier` | yes | VIN decode, recalls, specs, 15 data sources |
| `analytics` | `/tesla:analytics` | yes | TeslaMate: trips, costs, battery health |
| `setup` | `/tesla:setup` | no (user-only) | Install + configure tesla-cli |
| `serve` | `/tesla:serve` | no (user-only) | Start web dashboard + API |

## Security Model

- **Credentials**: System keyring only (macOS Keychain, GNOME Keyring, Windows Credential Locker). Never in files, env vars, or skill content.
- **Zero PII in plugin**: No VINs, order numbers, or names anywhere in the repo. Everything resolved at runtime via `tesla config show --json`.
- **Local-only**: No telemetry, no cloud relay. All API calls go directly from the user's machine to Tesla.
- **Anonymization**: `tesla --anon` masks PII for demos/screenshots.

## Distribution Plan

| Phase | Channel | Install command |
|-------|---------|----------------|
| 1 | GitHub | `git clone` + `claude --plugin-dir` |
| 2 | ClawHub | `clawhub install dacrypt/tesla` |
| 3 | Anthropic Marketplace | `/plugin install dacrypt/tesla-claude-plugin` |

## Prerequisites

- Python 3.12+
- uv package manager
- Tesla account with vehicle or active order
- Claude Code with plugin support

## Future (v2)

- **MCP Server**: Expose the FastAPI as MCP tools for typed inputs/outputs
- **Fleet Telemetry**: Real-time WebSocket streaming (sub-second vehicle data)
- **Signed Commands**: Vehicle Command Protocol for 2024.26+ firmware
- **Multi-language skills**: ES/PT/FR/DE/IT skill variants
