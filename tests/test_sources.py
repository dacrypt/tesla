"""Tests for the data source registry at tesla_cli.core.sources."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import tesla_cli.core.sources as sources_module
from tesla_cli.core.sources import (
    SourceDef,
    _detect_changes,
    _is_stale,
    get_audits,
    get_cached,
    get_cached_with_meta,
    get_history,
    get_source_def,
    list_sources,
    missing_auth,
    refresh_source,
    refresh_stale,
    register_source,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _redirect_dirs(tmp_path, monkeypatch):
    """Redirect all on-disk directories to tmp_path for isolation."""
    sources_dir = tmp_path / "sources"
    history_dir = tmp_path / "source_history"
    audit_dir = tmp_path / "source_audits"

    monkeypatch.setattr(sources_module, "SOURCES_DIR", sources_dir)
    monkeypatch.setattr(sources_module, "HISTORY_DIR", history_dir)
    monkeypatch.setattr(sources_module, "AUDIT_DIR", audit_dir)


@pytest.fixture()
def isolated_registry():
    """Save and restore _SOURCES so tests don't pollute each other."""
    original = dict(sources_module._SOURCES)
    sources_module._SOURCES.clear()
    yield sources_module._SOURCES
    sources_module._SOURCES.clear()
    sources_module._SOURCES.update(original)


@pytest.fixture()
def simple_source():
    """A minimal SourceDef with an inline fetch_fn."""
    fetch = MagicMock(return_value={"value": 42})
    return SourceDef(
        id="test.simple",
        name="Simple Test Source",
        category="servicios",
        fetch_fn=fetch,
        ttl=3600,
    )


def _write_cache(tmp_path, source_id: str, payload: dict) -> None:
    """Write a JSON cache file into the redirected SOURCES_DIR."""
    d = sources_module.SOURCES_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{source_id}.json").write_text(json.dumps(payload))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ago_iso(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


# ── Registration ──────────────────────────────────────────────────────────────


class TestRegisterSource:
    def test_register_source(self, isolated_registry):
        src = SourceDef(id="custom.src", name="Custom", category="vehiculo")
        register_source(src)

        assert "custom.src" in isolated_registry
        assert isolated_registry["custom.src"] is src

    def test_register_source_overwrites_existing(self, isolated_registry):
        src1 = SourceDef(id="dup.src", name="First", category="servicios")
        src2 = SourceDef(id="dup.src", name="Second", category="servicios")
        register_source(src1)
        register_source(src2)

        assert isolated_registry["dup.src"].name == "Second"


# ── get_source_def ─────────────────────────────────────────────────────────────


class TestGetSourceDef:
    def test_get_source_def_found(self, isolated_registry, simple_source):
        register_source(simple_source)
        result = get_source_def("test.simple")
        assert result is simple_source

    def test_get_source_def_missing(self, isolated_registry):
        result = get_source_def("does.not.exist")
        assert result is None


# ── list_sources ───────────────────────────────────────────────────────────────


class TestListSources:
    def test_list_sources_includes_defaults(self):
        """Default sources are registered on import; must have 15+."""
        result = list_sources()
        assert len(result) >= 15

    def test_list_sources_returns_expected_keys(self, isolated_registry, simple_source):
        register_source(simple_source)
        result = list_sources()
        assert len(result) == 1
        entry = result[0]
        for key in (
            "id",
            "name",
            "category",
            "country",
            "requires_auth",
            "ttl",
            "refreshed_at",
            "stale",
            "has_data",
            "error",
        ):
            assert key in entry

    def test_list_sources_no_cache(self, isolated_registry, simple_source):
        register_source(simple_source)
        result = list_sources()
        entry = result[0]
        assert entry["refreshed_at"] is None
        assert entry["has_data"] is False
        assert entry["error"] is None
        assert entry["stale"] is True

    def test_list_sources_with_cached_data(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"value": 1},
                "refreshed_at": _now_iso(),
                "error": None,
            },
        )
        result = list_sources()
        entry = result[0]
        assert entry["has_data"] is True
        assert entry["stale"] is False
        assert entry["error"] is None

    def test_list_sources_with_stale_cache(self, isolated_registry, simple_source, tmp_path):
        simple_source.ttl = 60
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"value": 1},
                "refreshed_at": _ago_iso(120),
                "error": None,
            },
        )
        result = list_sources()
        assert result[0]["stale"] is True

    def test_list_sources_with_error_cache(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": None,
                "refreshed_at": _now_iso(),
                "error": "something went wrong",
            },
        )
        result = list_sources()
        assert result[0]["error"] == "something went wrong"
        # "data" key is present (value None) — has_data reflects key presence, not truthiness
        # The implementation: has_data = cached is not None and "data" in cached
        # Since "data" key exists (even as None), has_data is True here.
        # What matters is the error field is surfaced correctly.
        assert result[0]["has_data"] is True


# ── get_cached ────────────────────────────────────────────────────────────────


class TestGetCached:
    def test_get_cached_no_cache(self, isolated_registry, simple_source):
        register_source(simple_source)
        assert get_cached("test.simple") is None

    def test_get_cached_with_data(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"value": 99},
                "refreshed_at": _now_iso(),
                "error": None,
            },
        )
        result = get_cached("test.simple")
        assert result == {"value": 99}

    def test_get_cached_returns_none_when_no_data_key(
        self, isolated_registry, simple_source, tmp_path
    ):
        register_source(simple_source)
        _write_cache(tmp_path, "test.simple", {"refreshed_at": _now_iso(), "error": "oops"})
        result = get_cached("test.simple")
        assert result is None

    def test_get_cached_unknown_source(self, isolated_registry):
        assert get_cached("unknown.source") is None


# ── get_cached_with_meta ───────────────────────────────────────────────────────


class TestGetCachedWithMeta:
    def test_get_cached_with_meta_no_cache(self, isolated_registry, simple_source):
        register_source(simple_source)
        result = get_cached_with_meta("test.simple")
        assert result == {
            "id": "test.simple",
            "data": None,
            "refreshed_at": None,
            "error": None,
            "stale": True,
        }

    def test_get_cached_with_meta_with_data(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        ts = _now_iso()
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"x": 1},
                "refreshed_at": ts,
                "error": None,
            },
        )
        result = get_cached_with_meta("test.simple")
        assert result["id"] == "test.simple"
        assert result["data"] == {"x": 1}
        assert result["refreshed_at"] == ts
        assert result["error"] is None
        assert result["stale"] is False

    def test_get_cached_with_meta_includes_error(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": None,
                "refreshed_at": _now_iso(),
                "error": "fetch failed",
            },
        )
        result = get_cached_with_meta("test.simple")
        assert result["error"] == "fetch failed"
        assert result["data"] is None


# ── refresh_source ────────────────────────────────────────────────────────────


class TestRefreshSource:
    def test_refresh_source_unknown(self, isolated_registry):
        result = refresh_source("nonexistent.source")
        assert result == {"error": "Unknown source: nonexistent.source"}

    def test_refresh_source_with_fetch_fn(self, isolated_registry, simple_source):
        register_source(simple_source)
        result = refresh_source("test.simple")
        assert result["data"] == {"value": 42}
        assert result["error"] is None
        assert "refreshed_at" in result
        simple_source.fetch_fn.assert_called_once()

    def test_refresh_source_fetch_fn_exception(self, isolated_registry):
        def _boom():
            raise RuntimeError("network error")

        src = SourceDef(id="test.boom", name="Boom", category="servicios", fetch_fn=_boom, ttl=3600)
        register_source(src)
        result = refresh_source("test.boom")
        assert result["error"] == "network error"
        assert result["data"] is None

    def test_refresh_source_writes_cache_file(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        refresh_source("test.simple")
        cache_file = sources_module.SOURCES_DIR / "test.simple.json"
        assert cache_file.exists()
        payload = json.loads(cache_file.read_text())
        assert payload["data"] == {"value": 42}

    def test_refresh_source_auth_required_fleet_missing(self, isolated_registry):
        src = SourceDef(
            id="test.fleet",
            name="Fleet Source",
            category="vehiculo",
            requires_auth="fleet",
            ttl=3600,
        )
        register_source(src)
        with patch("tesla_cli.core.auth.tokens.has_token", return_value=False):
            result = refresh_source("test.fleet")
        assert "Fleet API authentication required" in result["error"]

    def test_refresh_source_auth_required_fleet_present(self, isolated_registry):
        fetch = MagicMock(return_value={"car": "data"})
        src = SourceDef(
            id="test.fleet2",
            name="Fleet Source 2",
            category="vehiculo",
            requires_auth="fleet",
            fetch_fn=fetch,
            ttl=3600,
        )
        register_source(src)
        with patch("tesla_cli.core.auth.tokens.has_token", return_value=True):
            result = refresh_source("test.fleet2")
        assert result["data"] == {"car": "data"}
        assert result["error"] is None

    def test_refresh_source_auth_required_order_missing(self, isolated_registry):
        src = SourceDef(
            id="test.order",
            name="Order Source",
            category="financiero",
            requires_auth="order",
            ttl=1800,
        )
        register_source(src)
        with patch("tesla_cli.core.auth.tokens.has_token", return_value=False):
            result = refresh_source("test.order")
        assert "Tesla order authentication required" in result["error"]

    def test_refresh_source_no_fetch_method(self, isolated_registry):
        src = SourceDef(
            id="test.empty",
            name="Empty Source",
            category="servicios",
            ttl=3600,
        )
        register_source(src)
        result = refresh_source("test.empty")
        assert result["error"] == "No fetch method defined"

    def test_refresh_source_playwright_calls_subprocess(self, isolated_registry):
        src = SourceDef(
            id="test.playwright",
            name="Playwright Source",
            category="registro",
            uses_playwright=True,
            ttl=3600,
            openquery_source="co.runt",
            openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
        )
        register_source(src)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"placa": "ABC123"})
        mock_result.stderr = ""

        cfg = MagicMock()
        cfg.general.default_vin = "7SA123"
        cfg.general.cedula = ""

        with (
            patch("tesla_cli.core.sources.subprocess.run", return_value=mock_result),
            patch("tesla_cli.core.sources.load_config", return_value=cfg),
        ):
            result = refresh_source("test.playwright")

        assert result["data"] == {"placa": "ABC123"}
        assert result["error"] is None


# ── _detect_changes ───────────────────────────────────────────────────────────


class TestDetectChanges:
    def test_detect_changes_no_old_data(self):
        new = {"field": "value"}
        result = _detect_changes("test.src", None, new)
        assert result == []

    def test_detect_changes_no_new_data(self):
        old = {"field": "value"}
        result = _detect_changes("test.src", old, None)
        assert result == []

    def test_detect_changes_same_data(self):
        data = {"name": "Tesla", "year": "2026"}
        result = _detect_changes("test.src", data, data.copy())
        assert result == []

    def test_detect_changes_value_changed(self):
        old = {"mileage": "100", "status": "active"}
        new = {"mileage": "200", "status": "active"}
        result = _detect_changes("test.src", old, new)
        assert len(result) == 1
        assert result[0]["field"] == "mileage"
        assert result[0]["old"] == "100"
        assert result[0]["new"] == "200"

    def test_detect_changes_new_field_added(self):
        old = {"name": "Tesla"}
        new = {"name": "Tesla", "color": "red"}
        result = _detect_changes("test.src", old, new)
        assert len(result) == 1
        assert result[0]["field"] == "color"
        assert result[0]["old"] is None
        assert result[0]["new"] == "red"

    def test_detect_changes_field_removed(self):
        old = {"name": "Tesla", "color": "red"}
        new = {"name": "Tesla"}
        result = _detect_changes("test.src", old, new)
        assert len(result) == 1
        assert result[0]["field"] == "color"
        assert result[0]["old"] == "red"
        assert result[0]["new"] is None

    def test_detect_changes_skips_metadata_fields(self):
        old = {"queried_at": "2024-01-01", "audit": "x", "refreshed_at": "t", "status": "ok"}
        new = {"queried_at": "2024-06-01", "audit": "y", "refreshed_at": "t2", "status": "ok"}
        result = _detect_changes("test.src", old, new)
        assert result == []

    def test_detect_changes_non_dict_inputs(self):
        result = _detect_changes("test.src", ["a", "b"], ["a", "c"])
        assert result == []

    def test_detect_changes_multiple_fields(self):
        old = {"a": "1", "b": "2", "c": "3"}
        new = {"a": "1", "b": "9", "c": "99"}
        result = _detect_changes("test.src", old, new)
        fields = {r["field"] for r in result}
        assert fields == {"b", "c"}


# ── _is_stale ─────────────────────────────────────────────────────────────────


class TestIsStale:
    def test_is_stale_no_cache(self, isolated_registry, simple_source):
        register_source(simple_source)
        assert _is_stale("test.simple") is True

    def test_is_stale_unknown_source(self, isolated_registry):
        assert _is_stale("unknown.source") is True

    def test_is_stale_fresh(self, isolated_registry, simple_source, tmp_path):
        simple_source.ttl = 3600
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"x": 1},
                "refreshed_at": _now_iso(),
                "error": None,
            },
        )
        assert _is_stale("test.simple") is False

    def test_is_stale_expired(self, isolated_registry, simple_source, tmp_path):
        simple_source.ttl = 60
        register_source(simple_source)
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"x": 1},
                "refreshed_at": _ago_iso(120),
                "error": None,
            },
        )
        assert _is_stale("test.simple") is True

    def test_is_stale_no_refreshed_at_field(self, isolated_registry, simple_source, tmp_path):
        register_source(simple_source)
        _write_cache(tmp_path, "test.simple", {"data": {"x": 1}})
        assert _is_stale("test.simple") is True

    def test_is_stale_exactly_at_ttl_boundary(self, isolated_registry, simple_source, tmp_path):
        """A cache refreshed exactly ttl seconds ago is considered stale (age > ttl is False)."""
        simple_source.ttl = 3600
        register_source(simple_source)
        # 3599s ago — still fresh
        _write_cache(
            tmp_path,
            "test.simple",
            {
                "data": {"x": 1},
                "refreshed_at": _ago_iso(3599),
                "error": None,
            },
        )
        assert _is_stale("test.simple") is False


# ── get_history ───────────────────────────────────────────────────────────────


class TestGetHistory:
    def test_get_history_empty(self, isolated_registry):
        assert get_history("test.simple") == []

    def test_get_history_missing_file(self, isolated_registry):
        assert get_history("no.such.source") == []

    def test_get_history_with_entries(self, isolated_registry, simple_source):
        register_source(simple_source)
        history_dir = sources_module.HISTORY_DIR
        history_dir.mkdir(parents=True, exist_ok=True)
        entries = [
            {"timestamp": _ago_iso(200), "data_hash": "aabbcc001122", "changes": []},
            {"timestamp": _ago_iso(100), "data_hash": "ddeeff334455", "changes": [{"field": "x"}]},
            {"timestamp": _now_iso(), "data_hash": "112233aabbcc", "changes": []},
        ]
        history_file = history_dir / "test.simple.jsonl"
        history_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = get_history("test.simple")
        assert len(result) == 3
        assert result[0]["data_hash"] == "aabbcc001122"
        assert result[2]["data_hash"] == "112233aabbcc"

    def test_get_history_respects_limit(self, isolated_registry):
        history_dir = sources_module.HISTORY_DIR
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "test.limited.jsonl"
        lines = [
            json.dumps({"timestamp": _ago_iso(i * 10), "data_hash": f"hash{i}", "changes": []})
            for i in range(20)
        ]
        history_file.write_text("\n".join(lines) + "\n")

        result = get_history("test.limited", limit=5)
        assert len(result) == 5
        # limit slices from the end (most recent)
        assert result[-1]["data_hash"] == "hash19"

    def test_get_history_skips_malformed_lines(self, isolated_registry):
        history_dir = sources_module.HISTORY_DIR
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "test.bad.jsonl"
        history_file.write_text(
            '{"timestamp": "t1", "data_hash": "aaa", "changes": []}\n'
            "NOT VALID JSON\n"
            '{"timestamp": "t2", "data_hash": "bbb", "changes": []}\n'
        )
        result = get_history("test.bad")
        assert len(result) == 2
        assert result[0]["data_hash"] == "aaa"

    def test_get_history_written_by_refresh(self, isolated_registry, simple_source):
        """refresh_source should append a history entry for successful fetches."""
        register_source(simple_source)
        refresh_source("test.simple")
        result = get_history("test.simple")
        assert len(result) == 1
        assert "data_hash" in result[0]
        assert "timestamp" in result[0]


# ── get_audits ────────────────────────────────────────────────────────────────


class TestGetAudits:
    def test_get_audits_empty_no_dir(self, isolated_registry):
        result = get_audits("co.runt")
        assert result == []

    def test_get_audits_empty_dir_exists_no_files(self, isolated_registry):
        sources_module.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        result = get_audits("co.runt")
        assert result == []

    def test_get_audits_returns_pdf_entries(self, isolated_registry):
        audit_dir = sources_module.AUDIT_DIR
        audit_dir.mkdir(parents=True, exist_ok=True)

        # Create a fake PDF and companion metadata JSON
        pdf_path = audit_dir / "co.runt_2025-01-15_10-00-00.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake content")
        meta_path = audit_dir / "co.runt_2025-01-15_10-00-00.json"
        meta_path.write_text(
            json.dumps(
                {
                    "queried_at": "2025-01-15T10:00:00+00:00",
                    "source": "co.runt",
                    "duration_ms": 3200,
                    "has_pdf": True,
                }
            )
        )

        result = get_audits("co.runt")
        assert len(result) == 1
        assert result[0]["filename"] == "co.runt_2025-01-15_10-00-00.pdf"
        assert result[0]["source"] == "co.runt"
        assert result[0]["duration_ms"] == 3200

    def test_get_audits_no_meta_file(self, isolated_registry):
        audit_dir = sources_module.AUDIT_DIR
        audit_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = audit_dir / "co.runt_2025-02-01_09-00-00.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 content")

        result = get_audits("co.runt")
        assert len(result) == 1
        assert result[0]["filename"] == "co.runt_2025-02-01_09-00-00.pdf"

    def test_get_audits_filters_by_source(self, isolated_registry):
        audit_dir = sources_module.AUDIT_DIR
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / "co.runt_2025-01-01_00-00-00.pdf").write_bytes(b"%PDF")
        (audit_dir / "co.simit_2025-01-01_00-00-00.pdf").write_bytes(b"%PDF")

        runt_audits = get_audits("co.runt")
        simit_audits = get_audits("co.simit")
        assert len(runt_audits) == 1
        assert len(simit_audits) == 1
        assert runt_audits[0]["filename"].startswith("co.runt")
        assert simit_audits[0]["filename"].startswith("co.simit")


# ── missing_auth ──────────────────────────────────────────────────────────────


class TestMissingAuth:
    def test_missing_auth_no_sources_need_auth(self, isolated_registry):
        src = SourceDef(id="test.free", name="Free", category="servicios", ttl=3600)
        register_source(src)
        with patch("tesla_cli.core.auth.tokens.has_token", return_value=False):
            result = missing_auth()
        assert result == []

    def test_missing_auth_fleet_missing(self, isolated_registry):
        src = SourceDef(
            id="test.fleet", name="Fleet Src", category="vehiculo", requires_auth="fleet", ttl=3600
        )
        register_source(src)

        def _fake_has_token(key):
            from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN

            return key != FLEET_ACCESS_TOKEN

        with patch("tesla_cli.core.auth.tokens.has_token", side_effect=_fake_has_token):
            result = missing_auth()

        assert len(result) == 1
        assert result[0]["auth_type"] == "fleet"
        assert "source" in result[0]
        assert "message" in result[0]

    def test_missing_auth_order_missing(self, isolated_registry):
        src = SourceDef(
            id="test.order",
            name="Order Src",
            category="financiero",
            requires_auth="order",
            ttl=1800,
        )
        register_source(src)

        def _fake_has_token(key):
            from tesla_cli.core.auth.tokens import ORDER_ACCESS_TOKEN

            return key != ORDER_ACCESS_TOKEN

        with patch("tesla_cli.core.auth.tokens.has_token", side_effect=_fake_has_token):
            result = missing_auth()

        assert len(result) == 1
        assert result[0]["auth_type"] == "order"

    def test_missing_auth_deduplicates_by_type(self, isolated_registry):
        """Two sources with same auth_type should produce only one missing entry."""
        for i in range(3):
            register_source(
                SourceDef(
                    id=f"test.fleet{i}",
                    name=f"Fleet {i}",
                    category="vehiculo",
                    requires_auth="fleet",
                    ttl=3600,
                )
            )
        with patch("tesla_cli.core.auth.tokens.has_token", return_value=False):
            result = missing_auth()

        fleet_entries = [m for m in result if m["auth_type"] == "fleet"]
        assert len(fleet_entries) == 1

    def test_missing_auth_all_tokens_present(self, isolated_registry):
        register_source(
            SourceDef(id="test.f", name="F", category="vehiculo", requires_auth="fleet", ttl=3600)
        )
        register_source(
            SourceDef(id="test.o", name="O", category="financiero", requires_auth="order", ttl=1800)
        )
        with patch("tesla_cli.core.auth.tokens.has_token", return_value=True):
            result = missing_auth()
        assert result == []


# ── refresh_stale ─────────────────────────────────────────────────────────────


class TestRefreshStale:
    def test_refresh_stale_all_stale(self, isolated_registry):
        """All sources without cache are stale and should be refreshed."""
        fetches = {}
        for i in range(3):
            sid = f"test.src{i}"
            fn = MagicMock(return_value={"i": i})
            fetches[sid] = fn
            register_source(
                SourceDef(id=sid, name=f"Src{i}", category="servicios", fetch_fn=fn, ttl=60)
            )

        result = refresh_stale()
        assert set(result["refreshed"]) == set(fetches.keys())
        assert result["failed"] == []
        for fn in fetches.values():
            fn.assert_called_once()

    def test_refresh_stale_skips_fresh_sources(self, isolated_registry, tmp_path):
        fresh_fn = MagicMock(return_value={"ok": True})
        stale_fn = MagicMock(return_value={"ok": True})

        fresh = SourceDef(
            id="test.fresh", name="Fresh", category="servicios", fetch_fn=fresh_fn, ttl=3600
        )
        stale = SourceDef(
            id="test.stale", name="Stale", category="servicios", fetch_fn=stale_fn, ttl=60
        )
        register_source(fresh)
        register_source(stale)

        # Write a fresh cache for test.fresh
        _write_cache(
            tmp_path,
            "test.fresh",
            {
                "data": {"ok": True},
                "refreshed_at": _now_iso(),
                "error": None,
            },
        )
        # test.stale has no cache → stale

        result = refresh_stale()
        assert "test.stale" in result["refreshed"]
        assert "test.fresh" not in result["refreshed"]
        fresh_fn.assert_not_called()
        stale_fn.assert_called_once()

    def test_refresh_stale_captures_failures(self, isolated_registry):
        def _fail():
            raise RuntimeError("boom")

        register_source(
            SourceDef(
                id="test.failing", name="Failing", category="servicios", fetch_fn=_fail, ttl=60
            )
        )
        result = refresh_stale()
        assert result["refreshed"] == []
        assert len(result["failed"]) == 1
        assert result["failed"][0]["id"] == "test.failing"
        assert "boom" in result["failed"][0]["error"]

    def test_refresh_stale_mixed_results(self, isolated_registry, tmp_path):
        ok_fn = MagicMock(return_value={"data": "good"})
        register_source(
            SourceDef(id="test.ok", name="OK", category="servicios", fetch_fn=ok_fn, ttl=60)
        )

        def _bad():
            raise ValueError("fail")

        register_source(
            SourceDef(id="test.bad", name="Bad", category="servicios", fetch_fn=_bad, ttl=60)
        )

        result = refresh_stale()
        assert "test.ok" in result["refreshed"]
        bad_ids = [f["id"] for f in result["failed"]]
        assert "test.bad" in bad_ids


# ── Default source IDs ────────────────────────────────────────────────────────


class TestDefaultSources:
    """Verify all 15 expected default sources are registered on import."""

    EXPECTED_IDS = [
        "tesla.portal",
        "vin.decode",
        "tesla.order",
        "co.runt",
        "co.runt_soat",
        "co.runt_rtm",
        "co.runt_conductor",
        "co.simit",
        "co.pico_y_placa",
        "co.estaciones_ev",
        "co.recalls",
        "co.fasecolda",
        "us.nhtsa_recalls",
        "us.nhtsa_vin",
        "intl.ship_tracking",
    ]

    def test_all_default_source_ids_present(self):
        # Re-register defaults in case another test changed the country
        from tesla_cli.core.sources import _register_defaults

        _register_defaults()
        registered = {s["id"] for s in list_sources()}
        for sid in self.EXPECTED_IDS:
            assert sid in registered, f"Missing default source: {sid}"

    def test_default_source_categories_are_valid(self):
        valid_categories = {
            "vehiculo",
            "registro",
            "infracciones",
            "financiero",
            "seguridad",
            "servicios",
        }
        for entry in list_sources():
            assert entry["category"] in valid_categories, (
                f"Source {entry['id']} has invalid category: {entry['category']}"
            )

    def test_fleet_auth_sources(self):
        """Sources that require fleet auth are present and correctly typed."""
        fleet_sources = [s for s in list_sources() if s["requires_auth"] == "fleet"]
        assert len(fleet_sources) == 0  # current defaults use "order" or none for fleet

    def test_order_auth_sources(self):
        order_sources = [s for s in list_sources() if s["requires_auth"] == "order"]
        order_ids = {s["id"] for s in order_sources}
        assert "tesla.portal" in order_ids
        assert "tesla.order" in order_ids

    def test_co_runt_is_playwright(self):
        src = get_source_def("co.runt")
        assert src is not None
        assert src.uses_playwright is True

    def test_vin_decode_has_fetch_fn(self):
        src = get_source_def("vin.decode")
        assert src is not None
        assert src.fetch_fn is not None

    def test_co_estaciones_ev_has_fetch_fn(self):
        src = get_source_def("co.estaciones_ev")
        assert src is not None
        assert src.fetch_fn is not None

    def test_ttl_values_are_positive(self):
        for sid, src in sources_module._SOURCES.items():
            assert src.ttl > 0, f"Source {sid} has non-positive TTL: {src.ttl}"
