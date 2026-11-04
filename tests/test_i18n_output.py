"""`--lang` translates CLI output (cli/i18n.translate via cli/output)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tesla_cli.cli import i18n
from tesla_cli.cli.i18n import SUPPORTED_LANGS, normalize_lang, set_lang, translate
from tests.conftest import run_cli


@pytest.fixture(autouse=True)
def _reset_lang():
    yield
    set_lang("en")


def test_catalog_complete_in_every_language():
    en = set(i18n._STRINGS["en"])
    for lang in SUPPORTED_LANGS:
        assert set(i18n._STRINGS[lang]) == en, lang


def test_every_template_compiles_and_roundtrips():
    """Each English template, filled with sample values, is recognised."""
    import string

    set_lang("es")
    for key, template in i18n._STRINGS["en"].items():
        fields = {f for _, f, _, _ in string.Formatter().parse(template) if f}
        sample = template.format(**{f: f"X{n}" for n, f in enumerate(sorted(fields))})
        assert translate(sample) == i18n.t(
            key, **{f: f"X{n}" for n, f in enumerate(sorted(fields))}
        ), key


@pytest.mark.parametrize(
    ("raw", "lang", "expected"),
    [
        ("es_CO.UTF-8", None, "es"),
        ("pt-BR", None, "pt"),
        ("DE", None, "de"),
        ("xx", None, None),
        ("", None, None),
    ],
)
def test_normalize_lang(raw, lang, expected):
    assert normalize_lang(raw) == expected


def test_english_is_passthrough():
    assert translate("Vehicle locked") == "Vehicle locked"


def test_plain_message():
    set_lang("es")
    assert translate("Vehicle locked") == i18n._STRINGS["es"]["vehicle.locked"]


def test_placeholder_and_suffix():
    set_lang("es")
    assert translate("Charge limit set to 80%") == "Límite de carga establecido en 80%"
    assert translate("Vehicle locked 🔒") == i18n._STRINGS["es"]["vehicle.locked"] + " 🔒"


def test_trailing_placeholder_takes_whole_value():
    set_lang("es")
    out = translate("Delivery date set: 2026-01-05")
    assert out.endswith("2026-01-05")


def test_markup_wrapper_kept():
    set_lang("de")
    out = translate("[yellow]No dossier found. Run: tesla dossier build[/yellow]")
    assert out.startswith("[yellow]") and out.endswith("[/yellow]")
    assert "No dossier found" not in out


def test_no_false_prefix_match():
    set_lang("es")
    assert translate("Climate ONLINE status") == "Climate ONLINE status"


def test_unknown_message_unchanged():
    set_lang("fr")
    assert translate("Something nobody translated") == "Something nobody translated"


def test_cli_lang_flag_translates_success(monkeypatch):
    backend = type("B", (), {"command": lambda self, v, c, **k: {"result": True}})()
    with (
        patch("tesla_cli.cli.commands.vehicle._backend", return_value=backend),
        patch("tesla_cli.cli.commands.charge._vin", return_value="5YJ3E1EA1PF000001"),
    ):
        result = run_cli("--lang", "es", "charge", "start")
    assert result.exit_code == 0, result.output
    assert i18n._STRINGS["es"]["charge.started"] in result.output


def test_json_output_stays_english():
    backend = type("B", (), {"command": lambda self, v, c, **k: {"result": True}})()
    with (
        patch("tesla_cli.cli.commands.vehicle._backend", return_value=backend),
        patch("tesla_cli.cli.commands.charge._vin", return_value="5YJ3E1EA1PF000001"),
    ):
        result = run_cli("--lang", "es", "--json", "charge", "start")
    assert json.loads(result.output.strip().splitlines()[-1])["message"] == "Charging started"


def test_unsupported_lang_warns_and_falls_back():
    result = run_cli("--lang", "klingon", "--version")
    assert result.exit_code == 0
    assert i18n.get_lang() == "en"


def test_explicit_call_sites_translate():
    """Messages wired with i18n_t() (multi-part / markup-heavy output)."""
    from tesla_cli.core.config import Config

    with patch("tesla_cli.cli.commands.order.load_config", return_value=Config()):
        result = run_cli("--lang", "es", "order", "status")
    assert "No hay número de reserva configurado" in result.output


def test_runtime_error_messages_from_core_are_translated():
    """Typed errors raised in core reach render_error and get localized."""
    set_lang("pt")
    assert translate("No VIN configured. Run: tesla config set default-vin <VIN>") == i18n.t(
        "error.no_vin"
    )


def test_majority_of_catalog_reaches_output():
    """Guard against the catalog silently drifting from what commands print."""
    import ast
    import glob

    set_lang("es")
    reached = set()
    for f in glob.glob("src/tesla_cli/cli/**/*.py", recursive=True):
        src = Path(f).read_text()
        for key in i18n._STRINGS["en"]:
            if f"i18n_t('{key}'" in src or f'i18n_t("{key}"' in src:
                reached.add(key)
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for key, rx in i18n._template_patterns():
                    if rx.match(node.value.strip().replace("...", "…")):
                        reached.add(key)
                        break
    assert len(reached) >= 40, len(reached)
