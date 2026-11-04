"""Full backup / restore of the tesla-cli data directory (``~/.tesla-cli``).

A backup is a ``.tar.gz`` holding the data directory plus ``manifest.json``.

Safety properties (see the Oct 2026 disclosure in SECURITY.md):

- Written with :func:`write_private_file` semantics: mode 0600, never inside a
  git work tree, default location ``~/.tesla-cli/backups/``.
- ``include_secrets=False`` drops tokens, keys and the master key and stores a
  redacted ``config.toml`` — suitable for sharing with support.
- SQLite databases are copied with the online-backup API, so a running
  ``tesla serve`` cannot produce a torn copy.
- Restore accepts only regular files and directories with relative paths
  inside the archive (no links, devices, absolute paths or ``..``), keeps a
  safety backup of the current data first, and writes files 0600.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from tesla_cli import __version__
from tesla_cli.core.exceptions import ConfigurationError
from tesla_cli.core.private_files import find_git_worktree, redact_config

MANIFEST = "manifest.json"
FORMAT_VERSION = 1

# Never archived: transient state and the backups themselves.
_EXCLUDED_TOP = {"backups"}
_EXCLUDED_SUFFIXES = (".tmp", ".pid", ".lock", "-journal", "-wal", "-shm")
# Credential material, dropped by include_secrets=False.
_SECRET_FILES = {"tokens.enc.json", "master.key"}
_SECRET_DIRS = {"keys"}
_SECRET_NAMES = {".env"}
_MAX_RESTORE_BYTES = 2 * 1024**3


def data_dir() -> Path:
    from tesla_cli.core import config as _config

    return Path(_config.CONFIG_DIR)


def backups_dir() -> Path:
    return data_dir() / "backups"


def _is_secret(rel: PurePosixPath) -> bool:
    return (
        rel.name in _SECRET_FILES
        or rel.name in _SECRET_NAMES
        or rel.name.startswith(".env.")
        or (rel.parts and rel.parts[0] in _SECRET_DIRS)
    )


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if rel.parts[0] in _EXCLUDED_TOP or path.is_symlink() or not path.is_file():
            continue
        if path.name.endswith(_EXCLUDED_SUFFIXES):
            continue
        yield path, rel


def _sqlite_snapshot(path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "copy.db"
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            dst = sqlite3.connect(target)
            with dst:
                src.backup(dst)
            dst.close()
        finally:
            src.close()
        return target.read_bytes()


def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o600
    info.mtime = int(datetime.now(UTC).timestamp())
    tar.addfile(info, io.BytesIO(data))


def default_backup_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return backups_dir() / f"tesla-cli-backup-{stamp}.tar.gz"


def create_backup(
    dest: Path | str | None = None, *, include_secrets: bool = True
) -> tuple[Path, dict]:
    """Archive the data directory. Returns ``(path, manifest)``."""
    root = data_dir()
    target = Path(dest).expanduser() if dest else default_backup_path()
    repo = find_git_worktree(target)
    if repo is not None:
        raise ConfigurationError(
            f"Refusing to write a backup into the git repository at {repo}. "
            "Choose a path outside it (default: ~/.tesla-cli/backups/)."
        )
    target.parent.mkdir(parents=True, exist_ok=True)

    files: list[str] = []
    skipped_secrets: list[str] = []
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
            if root.exists():
                for path, rel in _iter_files(root):
                    name = rel.as_posix()
                    if not include_secrets and _is_secret(rel):
                        skipped_secrets.append(name)
                        continue
                    if name == "config.toml" and not include_secrets:
                        import tomllib

                        import tomli_w

                        data = tomli_w.dumps(redact_config(tomllib.loads(path.read_text())))
                        _add_bytes(tar, name, data.encode())
                    elif path.suffix == ".db":
                        _add_bytes(tar, name, _sqlite_snapshot(path))
                    else:
                        _add_bytes(tar, name, path.read_bytes())
                    files.append(name)
            manifest = {
                "format": FORMAT_VERSION,
                "tesla_cli_version": __version__,
                "created": datetime.now(UTC).isoformat(),
                "include_secrets": include_secrets,
                "files": files,
                "skipped_secrets": skipped_secrets,
            }
            _add_bytes(tar, MANIFEST, json.dumps(manifest, indent=2).encode())
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return target, manifest


def _safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = []
    total = 0
    for m in tar.getmembers():
        p = PurePosixPath(m.name)
        if p.is_absolute() or ".." in p.parts or not m.name or m.name.startswith("/"):
            raise ConfigurationError(f"Unsafe path in backup: {m.name!r}")
        if not (m.isfile() or m.isdir()):
            raise ConfigurationError(f"Unsupported entry type in backup: {m.name!r}")
        total += m.size
        if total > _MAX_RESTORE_BYTES:
            raise ConfigurationError("Backup is larger than 2 GB; refusing to restore.")
        members.append(m)
    return members


def read_manifest(src: Path | str) -> dict:
    with tarfile.open(Path(src).expanduser(), mode="r:gz") as tar:
        _safe_members(tar)
        try:
            fh = tar.extractfile(MANIFEST)
        except KeyError:
            fh = None
        if fh is None:
            raise ConfigurationError("Not a tesla-cli backup (manifest.json missing).")
        manifest = json.loads(fh.read())
    if manifest.get("format") != FORMAT_VERSION:
        raise ConfigurationError(f"Unsupported backup format {manifest.get('format')!r}.")
    return manifest


def restore_backup(src: Path | str) -> tuple[list[str], Path | None]:
    """Restore files from *src* into the data directory.

    Returns ``(restored_files, safety_backup_path)``; the safety backup holds
    the data that was present before restoring (None if the directory was empty).
    """
    src = Path(src).expanduser()
    read_manifest(src)  # validates format + member safety
    root = data_dir()
    safety: Path | None = None
    if root.exists() and any(_iter_files(root)):
        safety, _ = create_backup(
            backups_dir() / f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
        )
    restored: list[str] = []
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    with tarfile.open(src, mode="r:gz") as tar:
        for m in _safe_members(tar):
            if m.name == MANIFEST or m.isdir():
                continue
            dest = root / m.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            fh = tar.extractfile(m)
            assert fh is not None
            tmp = dest.with_name(dest.name + ".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(fh.read())
            os.replace(tmp, dest)
            restored.append(m.name)
    return restored, safety


def list_backups() -> list[Path]:
    d = backups_dir()
    return sorted(d.glob("*.tar.gz"), reverse=True) if d.exists() else []
