"""Architecture guard: core/ stays framework-independent, api/ never imports cli/.

CLAUDE.md: "core/ is framework-independent — no CLI or API framework imports".
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "tesla_cli"

FORBIDDEN = {
    "core": ("tesla_cli.cli", "tesla_cli.api", "typer", "rich", "fastapi", "starlette"),
    "api": ("tesla_cli.cli",),
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_imports(layer):
    violations = []
    for path in sorted((SRC / layer).rglob("*.py")):
        for name in _imports(path):
            if any(name == f or name.startswith(f + ".") for f in FORBIDDEN[layer]):
                violations.append(f"{path.relative_to(SRC)} imports {name}")
    assert not violations, "\n".join(violations)


def test_no_silently_swallowed_exceptions():
    """`except Exception: pass` hides real failures; log them at debug instead."""
    import re

    pattern = re.compile(r"except Exception(?: as \w+)?:[^\n]*\n\s+pass\s*\n")
    offenders = [
        str(p.relative_to(SRC)) for p in sorted(SRC.rglob("*.py")) if pattern.search(p.read_text())
    ]
    assert not offenders, offenders


def test_debug_flag_enables_debug_logging(monkeypatch):
    import logging

    from tesla_cli.cli.app import _configure_logging

    monkeypatch.delenv("TESLA_LOG_LEVEL", raising=False)
    _configure_logging(True)
    assert logging.getLogger("tesla_cli.core").isEnabledFor(logging.DEBUG)
    _configure_logging(False)
    assert not logging.getLogger("tesla_cli.core").isEnabledFor(logging.DEBUG)
    monkeypatch.setenv("TESLA_LOG_LEVEL", "info")
    _configure_logging(False)
    assert logging.getLogger("tesla_cli").level == logging.INFO
    logging.getLogger("tesla_cli").setLevel(logging.NOTSET)
    logging.getLogger("tesla-cli").setLevel(logging.NOTSET)


# Names tests patch on each split command package; submodules must reach them
# through the package (`_v.<name>` / `_m.<name>`) or those patches silently miss.
_PATCHABLE = {
    "vehicle": {
        "get_vehicle_backend",
        "load_config",
        "resolve_vin",
        "time",
        "_backend",
        "_vin",
        "_with_wake",
    },
    "teslaMate": {"_backend", "load_config"},
    "dossier": {"DossierBackend", "build_legacy_mission_control_payload"},
}


@pytest.mark.parametrize("package", sorted(_PATCHABLE))
def test_split_packages_resolve_patchable_names_through_package(package):
    for path in sorted((SRC / "cli" / "commands" / package).glob("_*.py")):
        if path.name == "__init__.py":  # defines them
            continue
        tree = ast.parse(path.read_text())
        bare = [
            f"{path.name}:{n.lineno} {n.id}"
            for n in ast.walk(tree)
            if isinstance(n, ast.Name) and n.id in _PATCHABLE[package]
        ]
        assert not bare, bare
