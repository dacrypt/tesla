"""Tests for `tesla teslaMate doctor` and the underlying diagnostics module.

All external dependencies (docker, postgres, http) are mocked at the
``tesla_cli.core.diagnostics.teslamate_doctor`` boundary so the suite runs
without any infrastructure.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from tesla_cli.cli.commands.teslaMate import teslaMate_app
from tesla_cli.core.diagnostics import teslamate_doctor as td

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(database_url: str = "postgresql://teslamate:pw@localhost:5432/teslamate") -> SimpleNamespace:
    """Build a minimal cfg object with a `.teslaMate` namespace."""
    tm = SimpleNamespace(
        database_url=database_url,
        car_id=1,
        managed=True,
        stack_dir="",
        postgres_port=5432,
        grafana_port=3000,
        teslamate_port=4000,
        mqtt_port=1883,
    )
    return SimpleNamespace(teslaMate=tm)


def _stack_running() -> list[dict]:
    return [
        {"name": "teslamate", "state": "running", "status": "Up"},
        {"name": "postgres", "state": "running", "status": "Up"},
        {"name": "grafana", "state": "running", "status": "Up"},
        {"name": "mosquitto", "state": "running", "status": "Up"},
    ]


class _FakeCursor:
    """Minimal cursor stub that returns scripted results per query."""

    def __init__(self, script):
        # script: list of (predicate(sql) -> bool, result)
        self.script = script
        self._next = None

    def execute(self, sql, params=None):
        for pred, result in self.script:
            if pred(sql):
                self._next = result
                return
        self._next = None

    def fetchone(self):
        result = self._next
        if isinstance(result, list):
            return result[0] if result else None
        return result

    def fetchall(self):
        result = self._next
        if isinstance(result, list):
            return result
        if result is None:
            return []
        return [result]

    def close(self):
        pass


def _patch_backend(monkeypatch, *, ping=True, cursor_script=None):
    """Patch TeslaMateBacked used inside teslamate_doctor to a fake."""

    class _FakeBacked:
        def __init__(self, url, car_id=1):
            self._url = url
            self._car_id = car_id

        def ping(self):
            return ping

        @contextmanager
        def _cursor(self):
            yield _FakeCursor(cursor_script or [])

    # Patch the symbol at the lookup site (it is imported lazily inside the
    # module via _backend_for, so patch the source module instead).
    import tesla_cli.core.backends.teslaMate as backend_mod

    monkeypatch.setattr(backend_mod, "TeslaMateBacked", _FakeBacked)


def _default_cursor_script(*, cars: int = 1, charges: int = 5, columns=None):
    columns = (
        list(td.REQUIRED_CHARGES_COLUMNS) if columns is None else columns
    )
    return [
        (lambda sql: "FROM cars" in sql, {"n": cars}),
        (lambda sql: "FROM charges" in sql, {"n": charges}),
        (
            lambda sql: "information_schema.columns" in sql,
            [{"column_name": c} for c in columns],
        ),
    ]


# ---------------------------------------------------------------------------
# 1. all-pass
# ---------------------------------------------------------------------------


def test_run_doctor_all_pass(monkeypatch):
    monkeypatch.setattr(
        td.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(td, "_stack_status", lambda: _stack_running())
    monkeypatch.setattr(td, "_stack_grafana_port", lambda: 3000)
    _patch_backend(monkeypatch, ping=True, cursor_script=_default_cursor_script())

    class _FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResp())

    report = td.run_doctor(_cfg())
    assert report.total == 8
    assert report.failed == 0, [
        (c.name, c.ok, c.message) for c in report.checks if not c.ok
    ]
    names = [c.name for c in report.checks]
    assert names == [
        "docker_daemon",
        "stack_running",
        "db_reachable",
        "dsn_host_correct",
        "car_registered",
        "recent_charge_data",
        "grafana_reachable",
        "schema_columns",
    ]


# ---------------------------------------------------------------------------
# 2. db unreachable cascades gracefully
# ---------------------------------------------------------------------------


def test_run_doctor_db_unreachable(monkeypatch):
    monkeypatch.setattr(
        td.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(td, "_stack_status", lambda: _stack_running())
    monkeypatch.setattr(td, "_stack_grafana_port", lambda: 3000)

    # Build a backend whose every query raises and ping returns False.
    class _BrokenBacked:
        def __init__(self, url, car_id=1):
            pass

        def ping(self):
            return False

        @contextmanager
        def _cursor(self):
            raise RuntimeError("connection refused")
            yield  # pragma: no cover

    import tesla_cli.core.backends.teslaMate as backend_mod

    monkeypatch.setattr(backend_mod, "TeslaMateBacked", _BrokenBacked)

    class _FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResp())

    report = td.run_doctor(_cfg())
    by_name = {c.name: c for c in report.checks}

    assert by_name["db_reachable"].ok is False
    assert by_name["db_reachable"].hint
    # Downstream SQL-dependent checks must not crash, must report failure
    # with informative messages.
    for n in ("car_registered", "recent_charge_data", "schema_columns"):
        c = by_name[n]
        assert c.ok is False, f"{n} should have failed gracefully"
        assert c.message, f"{n} message should be non-empty"
        assert c.hint, f"{n} hint should be non-empty"


# ---------------------------------------------------------------------------
# 3. DSN host mismatch
# ---------------------------------------------------------------------------


def test_run_doctor_dsn_host_mismatch(monkeypatch):
    monkeypatch.setattr(
        td.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(td, "_stack_status", lambda: _stack_running())
    monkeypatch.setattr(td, "_stack_grafana_port", lambda: 3000)
    _patch_backend(monkeypatch, ping=True, cursor_script=_default_cursor_script())

    class _FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResp())

    cfg = _cfg("postgresql://teslamate:pw@db:5432/teslamate")
    report = td.run_doctor(cfg)
    by_name = {c.name: c for c in report.checks}
    dsn = by_name["dsn_host_correct"]
    assert dsn.ok is False
    assert dsn.hint and "localhost" in dsn.hint.lower()


# ---------------------------------------------------------------------------
# 4. schema drift
# ---------------------------------------------------------------------------


def test_run_doctor_schema_drift(monkeypatch):
    monkeypatch.setattr(
        td.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(td, "_stack_status", lambda: _stack_running())
    monkeypatch.setattr(td, "_stack_grafana_port", lambda: 3000)

    # Only 5 of the 7 required columns present.
    partial = list(td.REQUIRED_CHARGES_COLUMNS[:5])
    missing = list(td.REQUIRED_CHARGES_COLUMNS[5:])
    _patch_backend(
        monkeypatch,
        ping=True,
        cursor_script=_default_cursor_script(columns=partial),
    )

    class _FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResp())

    report = td.run_doctor(_cfg())
    schema = next(c for c in report.checks if c.name == "schema_columns")
    assert schema.ok is False
    assert schema.hint
    for col in missing:
        assert col in schema.hint, f"hint should mention missing column {col}"


# ---------------------------------------------------------------------------
# 5. CLI exit code
# ---------------------------------------------------------------------------


def test_doctor_cli_exit_code_matches_failures(monkeypatch):
    runner = CliRunner()
    fake_report = td.DoctorReport(
        checks=[
            td.DoctorCheck(name="a", label="A", ok=True, message="ok"),
            td.DoctorCheck(name="b", label="B", ok=False, message="bad", hint="fix it"),
            td.DoctorCheck(name="c", label="C", ok=False, message="bad2", hint="fix it 2"),
        ],
        failed=2,
        total=3,
    )

    import tesla_cli.cli.commands.teslaMate as teslaMate_cmd

    monkeypatch.setattr(teslaMate_cmd, "load_config", lambda: _cfg())
    monkeypatch.setattr(td, "run_doctor", lambda cfg: fake_report)

    result = runner.invoke(teslaMate_app, ["doctor"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# 6. CLI --json output
# ---------------------------------------------------------------------------


def test_doctor_cli_json_output(monkeypatch):
    runner = CliRunner()
    fake_report = td.DoctorReport(
        checks=[
            td.DoctorCheck(name="a", label="A", ok=True, message="ok"),
            td.DoctorCheck(name="b", label="B", ok=True, message="ok"),
        ],
        failed=0,
        total=2,
    )

    import tesla_cli.cli.commands.teslaMate as teslaMate_cmd

    monkeypatch.setattr(teslaMate_cmd, "load_config", lambda: _cfg())
    monkeypatch.setattr(td, "run_doctor", lambda cfg: fake_report)

    result = runner.invoke(teslaMate_app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "checks" in data
    assert "failed" in data
    assert "total" in data
    assert data["total"] == 2
    assert data["failed"] == 0
    assert len(data["checks"]) == 2


# ---------------------------------------------------------------------------
# Bonus: doctor never raises even when everything is broken
# ---------------------------------------------------------------------------


def test_run_doctor_never_raises_when_all_fail(monkeypatch):
    def _raise(*a, **kw):
        raise OSError("docker not installed")

    monkeypatch.setattr(td.subprocess, "run", _raise)
    monkeypatch.setattr(td, "_stack_status", lambda: [])
    monkeypatch.setattr(td, "_stack_grafana_port", lambda: 3000)

    class _BrokenBacked:
        def __init__(self, url, car_id=1):
            pass

        def ping(self):
            raise RuntimeError("nope")

        @contextmanager
        def _cursor(self):
            raise RuntimeError("nope")
            yield  # pragma: no cover

    import tesla_cli.core.backends.teslaMate as backend_mod

    monkeypatch.setattr(backend_mod, "TeslaMateBacked", _BrokenBacked)

    import urllib.request

    def _bad_urlopen(*a, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _bad_urlopen)

    report = td.run_doctor(_cfg(database_url=""))
    assert report.total == 8
    assert isinstance(report.failed, int)
    # And the report must serialize to JSON (Pydantic).
    json.loads(report.model_dump_json())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
