"""`tesla backup` — full data-directory backup and restore (core/backup.py)."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import stat
import tarfile

import pytest

from tesla_cli.core import backup as bk
from tesla_cli.core import config as config_mod
from tesla_cli.core.exceptions import ConfigurationError
from tests.conftest import run_cli


@pytest.fixture
def home(tmp_path, monkeypatch):
    d = tmp_path / "home" / ".tesla-cli"
    d.mkdir(parents=True)
    monkeypatch.setattr(config_mod, "CONFIG_DIR", d)
    (d / "config.toml").write_text('[server]\napi_key = "super-secret-key-123"\n')
    (d / "tokens.enc.json").write_text('{"fleet-access-token": "ENC"}')
    (d / "master.key").write_text("m" * 40)
    (d / "keys").mkdir()
    (d / "keys" / "private-key.pem").write_text("PEM")
    (d / "events").mkdir()
    (d / "events" / "audit.jsonl").write_text('{"x": 1}\n')
    (d / "server.pid").write_text("123")
    db = sqlite3.connect(d / "tesla.db")
    db.execute("create table t (v text)")
    db.execute("insert into t values ('row')")
    db.commit()
    db.close()
    return d


def _names(path):
    with tarfile.open(path) as tar:
        return set(tar.getnames())


def test_full_backup_contents_and_mode(home):
    path, manifest = bk.create_backup()
    assert path.parent == home / "backups"
    names = _names(path)
    assert {"config.toml", "tokens.enc.json", "master.key", "keys/private-key.pem"} <= names
    assert "events/audit.jsonl" in names and "tesla.db" in names and "manifest.json" in names
    assert "server.pid" not in names
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert manifest["include_secrets"] is True


def test_backups_dir_not_recursively_included(home):
    bk.create_backup()
    path, _ = bk.create_backup()
    assert not any(n.startswith("backups/") for n in _names(path))


def test_no_secrets_backup(home):
    path, manifest = bk.create_backup(include_secrets=False)
    names = _names(path)
    assert "tokens.enc.json" not in names and "master.key" not in names
    assert not any(n.startswith("keys/") for n in names)
    with tarfile.open(path) as tar:
        cfg = tar.extractfile("config.toml").read().decode()
    assert "super-secret-key-123" not in cfg
    assert set(manifest["skipped_secrets"]) >= {"tokens.enc.json", "master.key"}


def test_sqlite_copied_consistently(home, tmp_path):
    path, _ = bk.create_backup()
    with tarfile.open(path) as tar:
        data = tar.extractfile("tesla.db").read()
    copy = tmp_path / "copy.db"
    copy.write_bytes(data)
    assert sqlite3.connect(copy).execute("select v from t").fetchall() == [("row",)]


def test_refuses_git_repo(home, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(ConfigurationError, match="git repository"):
        bk.create_backup(repo / "b.tar.gz")


def test_restore_roundtrip_with_safety_backup(home):
    path, _ = bk.create_backup()
    (home / "config.toml").write_text("changed = true\n")
    (home / "events" / "audit.jsonl").unlink()
    restored, safety = bk.restore_backup(path)
    assert "config.toml" in restored
    assert "super-secret-key-123" in (home / "config.toml").read_text()
    assert (home / "events" / "audit.jsonl").exists()
    assert safety is not None and safety.exists()
    if os.name == "posix":
        assert stat.S_IMODE((home / "config.toml").stat().st_mode) == 0o600


def _evil_archive(tmp_path, name, *, symlink=False):
    path = tmp_path / "evil.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        manifest = json.dumps({"format": 1, "files": []}).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))
        info = tarfile.TarInfo(name)
        if symlink:
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        else:
            info.size = 4
            tar.addfile(info, io.BytesIO(b"evil"))
    return path


@pytest.mark.parametrize("name", ["../escape.txt", "/abs.txt", "a/../../escape.txt"])
def test_restore_rejects_path_traversal(home, tmp_path, name):
    with pytest.raises(ConfigurationError, match="Unsafe path"):
        bk.restore_backup(_evil_archive(tmp_path, name))
    assert not (tmp_path / "home" / "escape.txt").exists()


def test_restore_rejects_symlinks(home, tmp_path):
    with pytest.raises(ConfigurationError, match="Unsupported entry"):
        bk.restore_backup(_evil_archive(tmp_path, "link", symlink=True))


def test_restore_rejects_foreign_archive(home, tmp_path):
    path = tmp_path / "x.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo("readme.txt")
        info.size = 2
        tar.addfile(info, io.BytesIO(b"hi"))
    with pytest.raises(ConfigurationError, match="manifest"):
        bk.restore_backup(path)


def test_cli_create_list_restore(home):
    result = run_cli("backup", "create")
    assert result.exit_code == 0, result.output
    listed = run_cli("--json", "backup", "list")
    archive = json.loads(listed.output.strip().splitlines()[-1])[0]["path"]
    (home / "config.toml").write_text("x = 1\n")
    result = run_cli("backup", "restore", archive, "--force")
    assert result.exit_code == 0, result.output
    assert "super-secret-key-123" in (home / "config.toml").read_text()


def test_cli_refuses_repo_output(home, tmp_path):
    repo = tmp_path / "r"
    (repo / ".git").mkdir(parents=True)
    result = run_cli("backup", "create", "-o", str(repo / "b.tar.gz"))
    assert result.exit_code == 1
