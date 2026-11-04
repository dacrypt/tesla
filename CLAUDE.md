# Tesla CLI — Project Context

## What is this?

Full-stack Tesla management platform: CLI (Typer) + REST API (FastAPI) + Web Dashboard (React/Ionic). Tracks orders, controls vehicles, aggregates data from 15+ sources, integrates with TeslaMate/MQTT/HA/ABRP.

**Version**: v5.5.0 | **Python**: 3.12+ | **Package manager**: uv | **Tests**: 2400+

## Architecture (quick reference)

```
src/tesla_cli/
├── core/          # Framework-independent business logic
│   ├── auth/      # OAuth2 + keyring token storage
│   ├── backends/  # API access (Owner, Fleet, Tessie, TeslaMate, order, dossier)
│   ├── models/    # Pydantic data models
│   ├── providers/ # 7 providers across 4 layers (BLE → VehicleAPI → TeslaMate → ABRP/HA/MQTT/Apprise)
│   └── sources.py # 15 registered data sources with TTL cache
├── cli/commands/  # 25 Typer command groups (175+ commands)
├── api/           # FastAPI REST API + SSE stream + Prometheus
└── infra/         # Docker Compose lifecycle (TeslaMate stack)

ui/                # React 19 + Ionic + Vite + TypeScript frontend
tests/             # 70+ test files, pytest
```

Full architecture: [docs/architecture.md](docs/architecture.md)

## Code conventions

- **Type hints everywhere** — Python 3.12+ syntax
- **Pydantic models** for all API data structures
- **Credentials in system keyring** — never plain text, never env vars
- **API is secure by default** — off-localhost requires `server.api_key`; new
  state-changing routes are covered by the CSRF/role middleware (`api/auth.py`);
  raw vehicle commands must be in `api/command_policy.py`; never `shell=True` with
  interpolated data; outbound URLs go through `core/url_safety.py`
- **Line length**: 100 chars (ruff)
- **core/ is framework-independent** — no CLI or API framework imports
- **Backends are the API boundary** — commands never call APIs directly

## Development commands

```bash
uv sync --extra dev --extra serve --extra teslaMate --extra fleet --extra pdf --extra query
uv run pytest -m "not integration" -x    # unit tests (fast)
uv run pytest                            # all tests including integration
uv run ruff check src/ tests/            # lint
uv run ruff format src/ tests/           # format
make serve                               # build UI + run production server
make ui                                  # Vite dev server (port 5173)
make api                                 # FastAPI dev server (port 8080)
```

## Testing patterns

- **Version assertions**: `>= Version("X.Y.Z")` — never exact, survives bumps
- **SSE routes**: source-code analysis, not TestClient.stream() (hangs on infinite generators)
- **Mock boundary**: patch at `commands.<module>.get_vehicle_backend`, not deeper
- **TeslaMate**: patch `commands.teslaMate._backend`
- **HTTP**: `pytest-httpx` for all external API mocking
- **No real API calls** in unit suite — all mocked

## Adding features (checklist)

1. Backend method in `core/backends/` or `core/providers/impl/`
2. Pydantic model in `core/models/` if new data shape
3. CLI command in `cli/commands/` (`@app.command()`)
4. Register sub-app in `app.py` if new command group
5. REST endpoint in `api/routes/` if API exposure needed
6. Tests in `tests/` — patch at module boundary
7. Update `docs/user-guide.md` with usage examples

## Key files for common tasks

| Task | Key files |
|------|-----------|
| Add vehicle command | `core/backends/fleet.py`, `cli/commands/vehicle/_control.py` (actions) / `_info.py` (queries) / `_monitor.py` (live), `tests/test_commands.py` — call `_v.load_config()`, `_v._backend()` etc. so test patches apply |
| Add TeslaMate analytics | `core/backends/teslaMate.py`, `cli/commands/teslaMate.py`, `api/routes/teslaMate.py` |
| Add data source | `core/source_catalog.py` (definitions), `core/sources.py` (engine), `cli/commands/dossier/` |
| Add provider | `core/providers/impl/`, `core/providers/loader.py` |
| Modify config | `config.py` (Pydantic Settings model) |
| Dashboard feature | `ui/src/pages/`, `ui/src/components/`, `api/routes/` |

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/user-guide.md](docs/user-guide.md) | Command reference (13 groups) |
| [docs/architecture.md](docs/architecture.md) | System design, ADRs, testing patterns |
| [docs/configuration.md](docs/configuration.md) | Config keys, auth, tokens |
| [docs/api-reference.md](docs/api-reference.md) | REST endpoints, SSE, Prometheus |
| [docs/data-sources.md](docs/data-sources.md) | Tesla APIs, 15 registered sources |
| [docs/self-hosting.md](docs/self-hosting.md) | Production install, remote access, upgrades, backups |
| [docs/roadmap.md](docs/roadmap.md) | Remaining gaps, priorities |
