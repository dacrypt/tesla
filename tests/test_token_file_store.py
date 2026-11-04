"""Encrypted on-disk token store used when no keyring backend exists."""

from __future__ import annotations

import os
import stat

import pytest

from tesla_cli.core.auth import file_store, tokens


def _dir():
    return file_store._config_dir()


def test_roundtrip_and_never_plaintext():
    file_store.set("fleet-access-token", "eyJ-super-secret")
    assert file_store.get("fleet-access-token") == "eyJ-super-secret"
    raw = (_dir() / "tokens.enc.json").read_text()
    assert "eyJ-super-secret" not in raw


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_files_are_owner_only():
    file_store.set("k", "v")
    for name in ("tokens.enc.json", "master.key"):
        assert stat.S_IMODE((_dir() / name).stat().st_mode) == 0o600, name


def test_missing_key_returns_none_without_creating_master_key():
    assert file_store.get("nope") is None
    assert not (_dir() / "master.key").exists()


def test_delete():
    file_store.set("k", "v")
    file_store.delete("k")
    assert file_store.get("k") is None
    file_store.delete("k")  # idempotent


def test_entries_are_bound_to_their_key():
    """Swapping ciphertexts between entries must not decrypt (key is AAD)."""
    import json

    file_store.set("a", "alpha")
    file_store.set("b", "beta")
    path = _dir() / "tokens.enc.json"
    data = json.loads(path.read_text())
    data["a"], data["b"] = data["b"], data["a"]
    path.write_text(json.dumps(data))
    assert file_store.get("a") is None


def test_wrong_master_key_reads_as_unset():
    file_store.set("k", "v")
    (_dir() / "master.key").write_text("a-completely-different-master-key\n")
    assert file_store.get("k") is None


def test_master_key_from_docker_secret(tmp_path, monkeypatch):
    secret = tmp_path / "secret"
    secret.write_text("docker-secret-master-key-123456\n")
    monkeypatch.setenv("TESLA_CLI_MASTER_KEY_FILE", str(secret))
    file_store.set("k", "v")
    assert file_store.get("k") == "v"
    assert not (_dir() / "master.key").exists()
    monkeypatch.delenv("TESLA_CLI_MASTER_KEY_FILE")
    assert file_store.get("k") is None  # auto-generated key differs


def test_short_master_key_rejected(tmp_path, monkeypatch):
    secret = tmp_path / "secret"
    secret.write_text("short")
    monkeypatch.setenv("TESLA_CLI_MASTER_KEY_FILE", str(secret))
    with pytest.raises(ValueError):
        file_store.set("k", "v")


def test_forced_file_store_bypasses_keyring(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setenv("TESLA_CLI_TOKEN_STORE", "file")
    with patch("keyring.set_password") as kr_set, patch("keyring.get_password") as kr_get:
        tokens.set_token(tokens.FLEET_REFRESH_TOKEN, "r-123")
        assert tokens.get_token(tokens.FLEET_REFRESH_TOKEN) == "r-123"
        tokens.delete_token(tokens.FLEET_REFRESH_TOKEN)
        assert tokens.get_token(tokens.FLEET_REFRESH_TOKEN) is None
    kr_set.assert_not_called()
    kr_get.assert_not_called()
