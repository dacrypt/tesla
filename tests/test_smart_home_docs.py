"""docs/smart-home.md must only reference API routes that exist, with the right method."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

DOC = Path(__file__).resolve().parent.parent / "docs" / "smart-home.md"


def _routes() -> set[tuple[str, str]]:
    from tesla_cli.api.app import create_app

    out = set()
    for r in create_app().routes:
        for m in getattr(r, "methods", None) or ():
            out.add((m, r.path.rstrip("/")))
    return out


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path.rstrip("/"))


def test_documented_endpoints_exist():
    text = DOC.read_text()
    documented = set(re.findall(r"`(GET|POST) (/api/[^\s`]+)`", text))
    # Endpoints in full URLs (rest_command / Shortcuts / IFTTT / curl examples) are POSTs.
    documented |= {("POST", p) for p in re.findall(r"https?://[^/\s\"]+(/api/[\w/\-]+)", text)}
    assert len(documented) >= 15
    routes = {(m, _normalise(p)) for m, p in _routes()}
    missing = [(m, p) for m, p in documented if (m, _normalise(p)) not in routes]
    assert not missing, missing
