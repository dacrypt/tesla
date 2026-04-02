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

Integration tests hit real APIs and require valid credentials in `~/.tesla-cli/config.toml`:

```bash
uv run pytest -m integration
```

## Linting

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Auto-fix
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

## After making changes

```bash
uv tool install -e .       # reinstall CLI globally
```

## Pull requests

1. Fork the repo and create a branch from `main`
2. Ensure `uv run pytest -m "not integration"` passes
3. Ensure `uv run ruff check src/ tests/` passes
4. Open a PR with a clear description

## Code style

- Python 3.12+, type hints everywhere
- Line length: 100 chars (configured in `pyproject.toml`)
- Ruff for linting and formatting
- Pydantic models for all data structures
- Credentials always via system keyring — never in files or environment variables

## Adding a new command

1. **Backend method** — add to `core/backends/` or `core/providers/impl/`
2. **CLI command** — add a `@app.command()` function in `cli/commands/`
3. **Register** — add the sub-app in `app.py` if it's a new command group
4. **Tests** — add a test class in `tests/`; patch at the module boundary

## Adding a REST endpoint

1. Add a route function to `api/routes/*.py`
2. For vehicle routes, use `_backend_and_vin(request)` for multi-vehicle support
3. Tests: source-code analysis for SSE routes; `TestClient` for all others

## Architecture

See [docs/architecture.md](docs/architecture.md) for system design, provider layers, data flow, and testing patterns.
