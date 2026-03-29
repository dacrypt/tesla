# Contributing

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

## Setup

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla
uv sync --extra dev
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
- Credentials always via system keyring — never in files or environment variables in production paths
