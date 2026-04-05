# Contributing to tesla-cli

## Quick Start

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla
uv sync --extra dev --extra serve --extra teslaMate --extra fleet --extra pdf
uv run pytest -m "not integration" -x   # unit tests (no credentials needed)
uv run ruff check src/ tests/           # lint
uv run ruff format src/ tests/          # format
```

Python 3.12+ required. All dependencies managed with [uv](https://docs.astral.sh/uv/).

---

## Architecture Overview

```
src/tesla_cli/
├── core/          # Framework-independent business logic
│   ├── backends/  # VehicleBackend implementations (owner, fleet, tessie, teslaMate)
│   ├── providers/ # 7 ecosystem providers across 4 layers (BLE → API → LocalDB → External)
│   ├── models/    # Pydantic data models
│   └── sources.py # 15 registered data sources with TTL cache
├── cli/commands/  # 14 Typer command groups (100+ commands)
├── api/           # FastAPI REST API + SSE stream + Prometheus
└── infra/         # Docker Compose TeslaMate stack lifecycle
```

Key rule: `core/` is framework-independent — no Typer or FastAPI imports inside it.

---

## Adding a Backend

Backends are the API boundary. Commands never call Tesla APIs directly.

1. Subclass `VehicleBackend` from `src/tesla_cli/core/backends/base.py`
2. Implement all `@abstractmethod` methods: `list_vehicles`, `get_vehicle_data`, `get_charge_state`, `get_climate_state`, `get_drive_state`, `get_vehicle_config`, `wake_up`, `command`
3. Override any extended methods your backend supports (e.g. `get_charge_history`, `get_nearby_charging_sites`)
4. Place the file in `src/tesla_cli/core/backends/`
5. Export from `src/tesla_cli/core/backends/__init__.py`
6. Add tests — patch at `commands.<module>.get_vehicle_backend`

---

## Adding a Provider

Providers handle ecosystem integrations (ABRP, HA, MQTT, Grafana, BLE) across 4 layers.

1. Subclass `Provider` from `src/tesla_cli/core/providers/base.py`
2. Set class attributes: `name`, `description`, `layer` (0–3), `priority` (`ProviderPriority`), `capabilities` (frozenset of `Capability` strings)
3. Implement `is_available()` (fast, no I/O) and `health_check()` (full connectivity probe returning `{"status", "latency_ms", "detail"}`)
4. Override `fetch()` and/or `execute()` — both return `ProviderResult`
5. Register in `src/tesla_cli/core/providers/loader.py`
6. Add tests

---

## Adding a CLI Command

1. Find or create a command file in `src/tesla_cli/cli/commands/`
2. Add a `@app.command()` decorated function — type hints required, docstring becomes the help text
3. Call backend methods via `get_vehicle_backend()` — never call Tesla APIs directly
4. Use `render_*` helpers from `src/tesla_cli/cli/output.py` for consistent output
5. If creating a new command group, register the sub-app in `src/tesla_cli/cli/app.py`:

```python
from tesla_cli.cli.commands.my_cmd import my_app
app.add_typer(my_app, name="my-group")
```

---

## Adding a Data Source

Data sources are registered in `src/tesla_cli/core/sources.py` using `register_source()`:

```python
from tesla_cli.core.sources import SourceDef, register_source

register_source(SourceDef(
    id="my.source",
    name="My Source",
    category="vehiculo",       # vehiculo | registro | infracciones | financiero | seguridad
    requires_auth="fleet",     # "fleet" | "order" | "" (none)
    ttl=3600,                  # seconds before stale
    fetch_fn=my_fetch_function,
))
```

---

## Adding a REST Endpoint

1. Add a route function to `src/tesla_cli/api/routes/*.py`
2. For vehicle routes, use `_backend_and_vin(request)` for multi-vehicle support
3. Tests: source-code analysis for SSE routes; `TestClient` for all others

---

## Running Tests

```bash
uv run pytest -m "not integration" -x        # fast unit tests
uv run pytest -m integration                 # integration (requires real credentials)
uv run pytest tests/test_commands.py -x      # specific file
uv run pytest -k "charge" -x                # by keyword
```

Test patterns to follow:
- Mock at `commands.<module>.get_vehicle_backend`, not deeper
- Use `pytest-httpx` for all external HTTP mocking — no real API calls in unit tests
- For TeslaMate commands, patch `commands.teslaMate._backend`
- Version assertions: `>= Version("X.Y.Z")`, never exact match
- SSE routes: test via source-code analysis, not `TestClient.stream()` (hangs on infinite generators)

---

## Code Style

- **Type hints everywhere** — Python 3.12+ union syntax (`X | Y`, not `Optional[X]`)
- **Line length**: 100 chars (enforced by ruff, configured in `pyproject.toml`)
- **Pydantic models** for all structured data
- **Credentials in system keyring** — never plain text, never env vars, never logged
- **No framework imports in `core/`** — keep business logic portable
- Errors: raise `TeslaCliError` subclasses from `src/tesla_cli/core/exceptions.py`

---

## Pull Requests

1. Fork the repo and create a branch from `main`
2. Ensure `uv run pytest -m "not integration"` passes
3. Ensure `uv run ruff check src/ tests/` passes
4. Open a PR with a clear description of what and why

For full system design, provider layers, and data flow: [docs/architecture.md](docs/architecture.md).
