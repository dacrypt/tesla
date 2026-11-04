"""Regression tests for the Oct 2026 disclosure: a config backup written into
the git checkout was committed with a Telegram token, VIN and order number."""

from __future__ import annotations

import json
import os
import stat
from unittest.mock import patch

import pytest

from tesla_cli.core.config import Config
from tesla_cli.core.exceptions import ConfigurationError
from tesla_cli.core.private_files import (
    REDACTED,
    find_git_worktree,
    redact_config,
    write_private_file,
)
from tests.conftest import run_cli

FAKE_TG = "tgram://1234567890:" + "A" * 35 + "/987654"


def _cfg() -> Config:
    cfg = Config()
    cfg.general.default_vin = "5YJ3E1EA1PF000001"
    cfg.notifications.apprise_urls = [FAKE_TG]
    cfg.server.api_key = "server-api-key-123456"
    cfg.mqtt.password = "mqtt-pass"
    cfg.fleet.client_id = "client-id-abc"
    return cfg


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    return tmp_path / "repo"


def test_refuses_to_write_inside_git_repo(repo):
    with pytest.raises(ConfigurationError, match="git repository"):
        write_private_file(repo / "tesla-config-backup.json", "{}")
    assert not (repo / "tesla-config-backup.json").exists()


def test_refuses_nested_paths_in_repo(repo):
    with pytest.raises(ConfigurationError):
        write_private_file(repo / "sub" / "dir" / "backup.json", "{}")


def test_explicit_override_allowed(repo):
    assert write_private_file(repo / "x.json", "{}", allow_in_git=True).exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_written_owner_only(tmp_path):
    out = write_private_file(tmp_path / "b" / "backup.json", "{}")
    assert stat.S_IMODE(out.stat().st_mode) == 0o600


def test_find_git_worktree(repo, tmp_path):
    assert find_git_worktree(repo / "a.json") == repo.resolve()
    assert find_git_worktree(tmp_path / "elsewhere" / "a.json") is None


def test_redaction_covers_notification_urls_and_keys():
    data = redact_config(_cfg().model_dump())
    dumped = json.dumps(data)
    assert "1234567890:" not in dumped  # Telegram bot token inside the Apprise URL
    assert "server-api-key-123456" not in dumped
    assert "mqtt-pass" not in dumped
    assert data["notifications"]["apprise_urls"] == [REDACTED]
    assert data["server"]["api_key"] == REDACTED


def test_backup_command_defaults_outside_cwd_and_redacts(tmp_path, monkeypatch, repo):
    from tesla_cli.core import config as config_mod

    monkeypatch.chdir(repo)  # simulate running inside the project checkout
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path / "home" / ".tesla-cli")
    with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=_cfg()):
        result = run_cli("config", "backup")
    assert result.exit_code == 0, result.output
    assert list(repo.iterdir()) == [repo / ".git"]  # nothing written to the checkout
    backups = list((tmp_path / "home" / ".tesla-cli" / "backups").glob("*.json"))
    assert len(backups) == 1
    text = backups[0].read_text()
    assert "1234567890:" not in text and "server-api-key-123456" not in text
    assert json.loads(text)["_meta"]["tesla_cli_version"] != "1.9.0"


def test_backup_command_refuses_repo_output(repo):
    with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=_cfg()):
        result = run_cli("config", "backup", "-o", str(repo / "tesla-config-backup.json"))
    assert result.exit_code == 1
    assert not (repo / "tesla-config-backup.json").exists()


def test_export_redacts_by_default(tmp_path, monkeypatch):
    import tomli_w

    from tesla_cli.core import config as config_mod

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(tomli_w.dumps(_cfg().model_dump()))
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_file)
    result = run_cli("config", "export")
    assert result.exit_code == 0, result.output
    assert "server-api-key-123456" not in result.output
    assert "1234567890:" not in result.output
    out = tmp_path / "out" / "cfg.toml"
    assert run_cli("config", "export", "-o", str(out), "--include-secrets").exit_code == 0
    assert "server-api-key-123456" in out.read_text()


def test_restore_does_not_write_redacted_placeholders(tmp_path):
    backup = tmp_path / "b.json"
    backup.write_text(json.dumps(redact_config(_cfg().model_dump())))
    current = _cfg()
    saved: list[Config] = []
    with (
        patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=current),
        patch("tesla_cli.cli.commands.config_cmd.save_config", side_effect=saved.append),
    ):
        assert run_cli("config", "restore", str(backup), "--force").exit_code == 0
    assert saved[0].notifications.apprise_urls == [FAKE_TG]
    assert saved[0].server.api_key == "server-api-key-123456"
