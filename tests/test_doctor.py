"""Unit tests for `tesla doctor` and the health FEATURES model."""

from __future__ import annotations

import json

from tesla_cli.core.config import Config
from tesla_cli.core.health.features import FEATURES, probe, probe_all
from tests.conftest import run_cli


def test_features_list_has_at_least_22_entries():
    assert len(FEATURES) >= 22
    names = [f.name for f in FEATURES]
    # no duplicate names
    assert len(names) == len(set(names))


def test_probe_t0_missing_scope_classifies_correctly():
    cfg = Config()
    cfg.general.backend = "fleet"
    # token has no scopes
    t0_with_scope = next(f for f in FEATURES if f.tier == "T0" and f.required_scope is not None)
    row = probe(t0_with_scope, cfg=cfg, token_scopes=[])
    assert row["status"] == "missing-scope"
    assert "remediation" in row
    assert t0_with_scope.required_scope in row["remediation"]


def test_probe_t0_with_scope_returns_ok():
    cfg = Config()
    cfg.general.backend = "fleet"
    t0 = next(f for f in FEATURES if f.tier == "T0" and f.required_scope is not None)
    row = probe(t0, cfg=cfg, token_scopes=[t0.required_scope])
    assert row["status"] == "ok"
    assert "remediation" not in row


def test_probe_t2_requires_fleet_signed_backend():
    cfg = Config()
    cfg.general.backend = "fleet"  # not fleet-signed
    t2 = next(f for f in FEATURES if f.tier == "T2")
    row = probe(t2, cfg=cfg, token_scopes=["vehicle_cmds"])
    assert row["status"] == "external-blocker"
    assert "fleet-signed" in row["remediation"]


def test_probe_t2_ok_when_fleet_signed():
    cfg = Config()
    cfg.general.backend = "fleet-signed"
    cfg.fleet.domain = "myusername.github.io"
    t2 = next(f for f in FEATURES if f.tier == "T2")
    row = probe(t2, cfg=cfg, token_scopes=["vehicle_cmds"])
    assert row["status"] == "ok"


def test_probe_t2_external_blocker_when_domain_empty():
    """backend=fleet-signed without fleet.domain → blocker, not ok."""
    cfg = Config()
    cfg.general.backend = "fleet-signed"
    cfg.fleet.domain = ""  # the new OSS default
    t2 = next(f for f in FEATURES if f.tier == "T2")
    row = probe(t2, cfg=cfg, token_scopes=["vehicle_cmds"])
    assert row["status"] == "external-blocker"
    assert "fleet-domain" in row["remediation"]


def test_probe_t3_missing_scope():
    cfg = Config()
    t3 = next(f for f in FEATURES if f.tier == "T3")
    row = probe(t3, cfg=cfg, token_scopes=[])
    assert row["status"] == "missing-scope"
    assert "24h" in row["remediation"]


def test_probe_t4_not_configured():
    cfg = Config()
    t4 = next(f for f in FEATURES if f.tier == "T4" and f.name == "teslamate")
    row = probe(t4, cfg=cfg, token_scopes=[])
    assert row["status"] == "not-configured"
    assert "teslaMate-up" in row["remediation"]


def test_probe_t4_configured_teslamate():
    cfg = Config()
    cfg.teslaMate.database_url = "postgresql://user:pass@localhost/teslaMate"
    t4 = next(f for f in FEATURES if f.name == "teslamate")
    row = probe(t4, cfg=cfg, token_scopes=[])
    assert row["status"] == "ok"


def test_probe_all_returns_all_features():
    cfg = Config()
    rows = probe_all(cfg=cfg, token_scopes=[])
    assert len(rows) == len(FEATURES)
    allowed_statuses = {"ok", "missing-scope", "external-blocker", "not-configured"}
    assert all(r["status"] in allowed_statuses for r in rows)


def test_cli_doctor_exits_zero_with_json():
    result = run_cli("doctor", "--json")
    assert result.exit_code == 0
    rows = json.loads(result.output.strip())
    assert isinstance(rows, list)
    assert len(rows) >= 22
    allowed_statuses = {"ok", "missing-scope", "external-blocker", "not-configured"}
    for r in rows:
        assert r["status"] in allowed_statuses
        assert "name" in r
        assert "tier" in r


def test_cli_doctor_table_exits_zero():
    result = run_cli("doctor")
    assert result.exit_code == 0
    # table should mention at least one known feature
    assert "flash_lights" in result.output or "vehicle_list" in result.output
