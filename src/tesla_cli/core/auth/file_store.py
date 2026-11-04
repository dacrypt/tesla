"""Encrypted on-disk token store for machines without a system keyring.

Headless Linux, Docker and NAS boxes have no Secret Service, so ``keyring``
cannot persist OAuth tokens there. This store keeps them in
``~/.tesla-cli/tokens.enc.json`` encrypted with AES-256-GCM.

Master key resolution (first match wins):

1. ``TESLA_CLI_MASTER_KEY_FILE`` — path to a file holding the key, e.g. a
   Docker secret mounted at ``/run/secrets/tesla_master_key``. Keeping the key
   outside the config volume means a copied volume/backup alone does not
   reveal the tokens.
2. ``~/.tesla-cli/master.key`` — generated on first use (mode 0600).

Both files are written owner-only and atomically. The store is selected
automatically when no keyring backend exists, or explicitly with
``TESLA_CLI_TOKEN_STORE=file``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

_STORE_NAME = "tokens.enc.json"
_KEY_NAME = "master.key"
_NONCE_LEN = 12


def _config_dir() -> Path:
    from tesla_cli.core import config as _config

    return Path(_config.CONFIG_DIR)


def _write_private(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _master_key() -> bytes:
    env_path = os.environ.get("TESLA_CLI_MASTER_KEY_FILE", "").strip()
    if env_path:
        material = Path(env_path).read_text().strip()
        if len(material) < 16:
            raise ValueError("TESLA_CLI_MASTER_KEY_FILE must contain at least 16 characters.")
    else:
        key_path = _config_dir() / _KEY_NAME
        if key_path.exists():
            material = key_path.read_text().strip()
        else:
            material = secrets.token_urlsafe(32)
            _write_private(key_path, material + "\n")
    return hashlib.sha256(b"tesla-cli-token-store-v1:" + material.encode()).digest()


def _aead():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(_master_key())


def _store_path() -> Path:
    return _config_dir() / _STORE_NAME


def _load() -> dict[str, str]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(key: str) -> str | None:
    blob = _load().get(key)
    if not blob:
        return None
    try:
        raw = base64.b64decode(blob)
        nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
        return _aead().decrypt(nonce, ct, key.encode()).decode()
    except Exception:  # noqa: BLE001 — wrong master key / corrupted entry reads as unset
        return None


def set(key: str, value: str) -> None:  # noqa: A001 — mirrors keyring API
    data = _load()
    nonce = os.urandom(_NONCE_LEN)
    ct = _aead().encrypt(nonce, value.encode(), key.encode())  # key bound as AAD
    data[key] = base64.b64encode(nonce + ct).decode()
    _write_private(_store_path(), json.dumps(data, indent=2, sort_keys=True))


def delete(key: str) -> None:
    data = _load()
    if data.pop(key, None) is not None:
        _write_private(_store_path(), json.dumps(data, indent=2, sort_keys=True))
