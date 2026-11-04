"""Writing files that contain secrets or personal data.

Root cause of the October 2026 disclosure: `tesla config backup` wrote
`tesla-config-backup.json` into the current directory — a git checkout — and
it was committed. Every command that writes config/backups must go through
:func:`write_private_file`, which refuses paths inside a git work tree and
writes owner-only (0600) atomically.
"""

from __future__ import annotations

import os
from pathlib import Path

from tesla_cli.core.exceptions import ConfigurationError


def find_git_worktree(path: Path) -> Path | None:
    """Return the git work tree containing *path*, if any."""
    current = path.resolve().parent if not path.is_dir() else path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def write_private_file(path: Path | str, content: str, *, allow_in_git: bool = False) -> Path:
    """Write *content* to *path* with mode 0600.

    Raises :class:`ConfigurationError` when *path* is inside a git work tree,
    unless ``allow_in_git`` is set explicitly.
    """
    target = Path(path).expanduser()
    repo = find_git_worktree(target)
    if repo is not None and not allow_in_git:
        raise ConfigurationError(
            f"Refusing to write secrets into the git repository at {repo}: "
            "files there are easily committed and published. Choose a path "
            "outside the repository (default: ~/.tesla-cli/backups/)."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    return target


def default_backup_path(stem: str, suffix: str) -> Path:
    """``~/.tesla-cli/backups/<stem>-<YYYY-MM-DD>.<suffix>``."""
    from datetime import date

    from tesla_cli.core import config as _config

    return Path(_config.CONFIG_DIR) / "backups" / f"{stem}-{date.today().isoformat()}.{suffix}"


_SECRET_KEY_PARTS = ("token", "secret", "password", "key", "apprise_url", "webhook_url", "pin")
REDACTED = "[REDACTED]"


def redact_config(obj: object) -> object:
    """Replace credential-bearing values (by key name) with ``[REDACTED]``.

    Notification URLs are credentials too: Apprise URLs embed bot tokens
    (``tgram://<token>/<chat>``) — the old key-name filter missed them.
    """
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            name = str(k).lower()
            if any(part in name for part in _SECRET_KEY_PARTS) and v not in ("", None, [], {}):
                out[k] = [REDACTED] * len(v) if isinstance(v, list) else REDACTED
            else:
                out[k] = redact_config(v)
        return out
    if isinstance(obj, list):
        return [redact_config(i) for i in obj]
    return obj
