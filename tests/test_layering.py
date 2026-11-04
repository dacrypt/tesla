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
