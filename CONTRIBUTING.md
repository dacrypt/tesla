# Contributing

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

## Setup

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla
uv sync --extra dev --extra serve --extra teslaMate --extra fleet --extra pdf
```

## Running tests

Unit tests only (no credentials required):

```bash
uv run pytest -m "not integration"
```

Integration tests hit real APIs and require valid credentials configured in `~/.tesla-cli/config.toml`:

```bash
uv run pytest -m integration
```

## Linting

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Auto-fix:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

## After making changes

Reinstall the CLI globally:

```bash
uv tool install -e .
```

## Pull requests

1. Fork the repo and create a branch from `main`
2. Ensure `uv run pytest -m "not integration"` passes
3. Ensure `uv run ruff check src/ tests/` passes
4. Open a PR with a clear description of the change

## Code style

- Python 3.12+, type hints everywhere
- Line length: 100 chars (configured in `pyproject.toml`)
- Ruff for linting and formatting
- Pydantic models for all data structures
- Credentials always via system keyring — never in files or environment variables

---

## Architecture Overview

### Directory layout

```
src/tesla_cli/
├── app.py              # Entry point — registers all Typer sub-apps
├── config.py           # Pydantic-Settings config model (~/.tesla-cli/config.toml)
├── output.py           # Rich rendering + JSON mode + --anon anonymizer
├── i18n.py             # Lightweight i18n: t(key) with en/es built-in
├── exceptions.py       # AuthenticationError, ApiError, BackendError, etc.
│
├── auth/               # OAuth2 + keyring token storage
├── backends/           # Raw API access (Owner, Fleet, Tessie, TeslaMate DB, dossier)
├── providers/          # Provider registry — routes capabilities to best available source
│   ├── base.py         # Capability enum + ProviderBase ABC
│   ├── registry.py     # ProviderRegistry: .for_capability(), .fanout()
│   ├── loader.py       # build_registry(cfg) factory — instantiates enabled providers
│   └── impl/           # 7 providers across 4 layers (see below)
├── commands/           # Typer CLI commands
├── models/             # Pydantic data models
└── server/             # FastAPI app, routes, static dashboard
    ├── app.py          # App factory — mounts routers, SSE stream, metrics
    ├── auth.py         # ApiKeyMiddleware
    ├── routes/         # vehicle, charge, climate, order, teslaMate
    └── static/         # index.html — single-page dashboard (PWA)
```

### Provider layers

| Layer | Provider | Key Capabilities |
|-------|----------|-----------------|
| L0 | **BLE** | Bluetooth local commands (planned) |
| L1 | **VehicleAPI** | Vehicle control + data (Owner / Fleet / Tessie) |
| L2 | **TeslaMate** | Trip analytics, charge history, heatmap, timeline |
| L3 | **ABRP** | Live telemetry push to A Better Route Planner |
| L3 | **HomeAssistant** | State sync push to Home Assistant |
| L3 | **Apprise** | Notifications (100+ channels via Apprise) |
| L3 | **MQTT** | Telemetry publish + HA MQTT Discovery |

The registry selects the first available provider for each capability and supports `fanout()` to broadcast to all providers for push-type operations (telemetry, notifications).

### Adding a new command

1. **Backend method** — add to `backends/` or `providers/impl/` as appropriate
2. **CLI command** — add a `@app.command()` function in `commands/`
3. **Register** — add the sub-app in `app.py` if it's a new command group
4. **Tests** — add a test class in `tests/`; patch at the `commands.<module>.get_vehicle_backend` boundary (unit) or use `pytest-httpx` for HTTP mocking

### Adding a REST endpoint

1. Add a route function to the appropriate `server/routes/*.py` file
2. For vehicle routes, use `_backend_and_vin(request)` — it automatically reads `?vin=` for multi-vehicle support
3. Tests: source-code analysis for SSE routes (avoids infinite generator hangs); `TestClient` for all others

### Testing patterns

- **Version assertions**: always use `packaging.version.Version(x) >= Version("X.Y.Z")` — never exact equality — so tests survive version bumps
- **SSE routes**: test with source-code analysis (`assert "event: battery" in src`) rather than `TestClient.stream()`, which hangs on infinite generators
- **TeslaMate tests**: patch `tesla_cli.commands.teslaMate._backend` to return a mock with the required methods
- **Vehicle tests**: patch `tesla_cli.commands.vehicle.get_vehicle_backend` (or the equivalent in the module under test)
