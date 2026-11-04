"""Versioned config migrations (core/config_migrations.py)."""

from __future__ import annotations

import pytest
import tomli_w

from tesla_cli.core import config as config_mod
from tesla_cli.core.config_migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS, migrate
from tesla_cli.core.exceptions import ConfigurationError


def test_every_version_has_a_migration_path():
    for v in range(CURRENT_SCHEMA_VERSION):
        assert v in MIGRATIONS, f"missing migration from schema_version {v}"


def test_unversioned_config_is_upgraded():
    data, applied = migrate({"general": {"default_vin": "X"}})
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert applied == list(range(CURRENT_SCHEMA_VERSION))
    assert data["general"]["default_vin"] == "X"


def test_current_config_untouched():
    data, applied = migrate({"schema_version": CURRENT_SCHEMA_VERSION})
    assert applied == []


def test_newer_config_refused():
    with pytest.raises(ConfigurationError, match="Upgrade tesla-cli"):
        migrate({"schema_version": CURRENT_SCHEMA_VERSION + 1})


def test_load_config_migrates_legacy_file(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text(tomli_w.dumps({"general": {"default_vin": "5YJ3LEGACY"}}))
    monkeypatch.setattr(config_mod, "CONFIG_FILE", path)
    cfg = config_mod.load_config()
    assert cfg.schema_version == CURRENT_SCHEMA_VERSION
    assert cfg.general.default_vin == "5YJ3LEGACY"


def test_save_config_persists_schema_version(tmp_path, monkeypatch):
    import tomllib

    path = tmp_path / "config.toml"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", path)
    config_mod.save_config(config_mod.Config())
    assert tomllib.loads(path.read_text())["schema_version"] == CURRENT_SCHEMA_VERSION
