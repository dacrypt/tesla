"""Versioned migrations for ``~/.tesla-cli/config.toml``.

Every config file carries ``schema_version``. Files written before versioning
existed have none and are treated as version 0. On load, the raw TOML dict
is upgraded step by step (``MIGRATIONS[n]`` turns version *n* into *n + 1*)
before Pydantic validation, so a migration can rename, move or drop keys —
not just add defaults.

To change the config shape:
1. bump ``CURRENT_SCHEMA_VERSION``;
2. add ``MIGRATIONS[old_version] = fn`` that rewrites the raw dict;
3. add a test with a config file in the old shape.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tesla_cli.core.exceptions import ConfigurationError

CURRENT_SCHEMA_VERSION = 1

Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Baseline: unversioned configs (≤ 5.3.0) start carrying schema_version."""
    return data


MIGRATIONS: dict[int, Migration] = {
    0: _v0_to_v1,
}


def migrate(data: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
    """Upgrade raw config *data* to the current schema.

    Returns ``(data, applied)`` where *applied* lists the source versions of
    the migrations that ran. Raises :class:`ConfigurationError` for a config
    written by a newer tesla-cli (refuse to silently drop unknown fields).
    """
    version = int(data.get("schema_version", 0) or 0)
    if version > CURRENT_SCHEMA_VERSION:
        raise ConfigurationError(
            f"config.toml has schema_version {version}, but this tesla-cli only "
            f"understands up to {CURRENT_SCHEMA_VERSION}. Upgrade tesla-cli."
        )
    applied: list[int] = []
    while version < CURRENT_SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:  # pragma: no cover - guarded by tests
            raise ConfigurationError(f"No config migration from schema_version {version}.")
        data = step(dict(data))
        applied.append(version)
        version += 1
        data["schema_version"] = version
    return data, applied
