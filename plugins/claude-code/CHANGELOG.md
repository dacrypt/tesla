# Changelog

## v1.2.0 (2026-04-04)

### New Skills

- **automations**: Create, list, enable/disable, and trigger event-driven automations with 9 trigger types
- **telemetry**: Self-hosted Fleet Telemetry streaming — start/stop receiver, inspect live data

### Updated Skills

- **charge**: Supercharging invoice download, energy cost breakdown enhancements
- **order**: Improved delivery gate detection, portal document download (`tesla portal documents`)
- **tesla-context**: Updated for CLI v4.8.0 — scene commands, energy commands, signed-command backend

### Compatibility

- Requires tesla-cli v4.8.0+
- Signed commands supported on 2024.26+ firmware via Fleet API backend

## v1.1.0 (2026-04-04)

### Marketplace Readiness

- **marketplace.json**: Added Anthropic marketplace manifest with schema, owner, category (`iot`), and tags
- **Plugin discovery**: Added `"skills": "./skills/"` to plugin.json for automatic skill loading
- **Skill levels**: Added `level` metadata to all 9 skills (1=read-only, 2=side-effects)
- **Simplified install**: One-command setup via `extraKnownMarketplaces` (same pattern as OMC)

## v1.0.0 (2026-04-03)

Initial release.

### Skills

- **tesla-context**: Background knowledge auto-loaded for Tesla conversations
- **status**: Quick vehicle status (battery, location, climate, readiness)
- **control**: Vehicle commands with destructive action confirmation
- **charge**: Charging management, sessions, costs, forecast
- **order**: Order tracking, delivery ETA, gates, inspection checklist
- **dossier**: Vehicle intelligence from 15+ data sources
- **analytics**: TeslaMate deep analytics (trips, costs, battery health)
- **setup**: First-time onboarding wizard
- **serve**: Self-hosted web dashboard + REST API

### Other

- `bin/tesla-check` pre-flight validation script
- Design document at `docs/design.md`
- MIT license
