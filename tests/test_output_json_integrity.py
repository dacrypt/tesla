"""Regression tests: --json output must survive piping and hostile values.

The JSON emitters used to route through the human-facing Rich console, which
wrapped payloads to the console width (80 columns whenever stdout is not a TTY)
and parsed square brackets inside values as markup. Both corrupted the document.
"""

from __future__ import annotations

import io
import json

import pytest
from pydantic import BaseModel

from tesla_cli.cli import output

# A value long enough to wrap at any realistic console width, plus bracket
# sequences that Rich would treat as markup (the second one used to raise).
LONG_VALUE = (
    "Push notifications (Apprise) delivered over Telegram, Slack, email and a "
    "dozen other transports, described at length so the line must wrap"
)
MARKUP_VALUES = ["see [bold] section", "[/close]", "[red]not a color[/red]", "[dim]x"]


@pytest.fixture
def narrow_console(monkeypatch):
    """Point the JSON consoles at a 40-column buffer and return the buffer."""
    buf = io.StringIO()
    from rich.console import Console

    monkeypatch.setattr(
        output,
        "json_console",
        Console(file=buf, width=40, soft_wrap=True, markup=False, highlight=False),
    )
    monkeypatch.setattr(output, "_json_mode", True)
    return buf


@pytest.fixture(autouse=True)
def _reset_modes():
    yield
    output.set_json_mode(False)
    output.set_anon_mode(False)


def test_render_dict_json_survives_narrow_console(narrow_console):
    payload = {"description": LONG_VALUE, "name": "apprise"}
    output.render_dict(payload)
    assert json.loads(narrow_console.getvalue()) == payload


def test_render_table_json_survives_narrow_console(narrow_console):
    rows = [{"description": LONG_VALUE, "n": i} for i in range(3)]
    output.render_table(rows, columns=["description", "n"])
    assert json.loads(narrow_console.getvalue()) == rows


@pytest.mark.parametrize("value", MARKUP_VALUES)
def test_render_dict_json_preserves_markup_like_values(narrow_console, value):
    """Square brackets are data, not Rich markup -- and must not raise."""
    output.render_dict({"note": value})
    assert json.loads(narrow_console.getvalue()) == {"note": value}


def test_render_model_json_survives_narrow_console(narrow_console):
    class Sample(BaseModel):
        description: str
        tag: str

    model = Sample(description=LONG_VALUE, tag="[/close]")
    output.render_model(model)
    assert json.loads(narrow_console.getvalue()) == model.model_dump()


def test_render_success_json_is_parseable(narrow_console):
    output.render_success(LONG_VALUE)
    assert json.loads(narrow_console.getvalue()) == {"status": "ok", "message": LONG_VALUE}


def test_module_level_json_console_is_configured_for_machine_output():
    """The real module-level console -- not just the narrowed test double.

    Uses Console.capture() rather than swapping ``file``: ``Console.file`` is a
    property, so monkeypatching it pins the console to the captured stream for
    the rest of the session and breaks every later CliRunner test.
    """
    payload = {"description": LONG_VALUE, "tag": "[/close]"}
    with output.json_console.capture() as cap:
        output.write_json(json.dumps(payload, indent=2))
    assert json.loads(cap.get()) == payload
