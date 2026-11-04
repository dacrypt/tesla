"""Secure token storage via system keyring (macOS Keychain, etc.).

Falls back to an AES-256-GCM encrypted file (``core/auth/file_store.py``) when
no keyring backend exists (Docker, headless Linux), or when
``TESLA_CLI_TOKEN_STORE=file`` is set. Tokens are never stored in plain text.
"""

import os

import keyring

from tesla_cli.core.auth import file_store

SERVICE = "tesla-cli"

# Token keys
ORDER_ACCESS_TOKEN = "order-access-token"
ORDER_REFRESH_TOKEN = "order-refresh-token"
TESSIE_TOKEN = "tessie-token"
FLEET_ACCESS_TOKEN = "fleet-access-token"
FLEET_REFRESH_TOKEN = "fleet-refresh-token"
FLEET_CLIENT_SECRET = "fleet-client-secret"

# TeslaMate managed stack credentials
TESLAMATE_DB_PASSWORD = "teslamate-db-password"
TESLAMATE_GRAFANA_PASSWORD = "teslamate-grafana-password"
TESLAMATE_ENCRYPTION_KEY = "teslamate-encryption-key"

# Native EV planner BYOK keys (Phase 1 + Phase 2)
PLANNER_OPENROUTE_KEY = "planner-openroute-key"
PLANNER_OPENCHARGEMAP_KEY = "planner-openchargemap-key"
PLANNER_WEATHER_KEY = "planner-weather-key"


NO_BACKEND_HINT = (
    "No system keyring backend is available and the encrypted file store could "
    "not be used. Check that ~/.tesla-cli is writable (or that "
    "TESLA_CLI_MASTER_KEY_FILE points to a readable key file)."
)


def _forced_file_store() -> bool:
    return os.environ.get("TESLA_CLI_TOKEN_STORE", "").strip().lower() == "file"


def get_token(key: str) -> str | None:
    """Retrieve a token from the system keyring.

    Returns None when no keyring backend is available — headless Linux, Docker,
    CI — rather than raising. Every caller treats a missing token as "this
    credential is not configured", which is the correct reading here: a machine
    with no keyring cannot have stored one.
    """
    if _forced_file_store():
        return file_store.get(key)
    try:
        return keyring.get_password(SERVICE, key)
    except keyring.errors.NoKeyringError:
        try:
            return file_store.get(key)
        except Exception:  # noqa: BLE001 — unreadable store reads as "not configured"
            return None
    except keyring.errors.KeyringError:
        return None


def set_token(key: str, value: str) -> None:
    """Store a token in the system keyring.

    Unlike reads, a failed write is never silent: the caller asked to persist a
    credential, and pretending it worked would lose it.
    """
    if _forced_file_store():
        file_store.set(key, value)
        return
    try:
        keyring.set_password(SERVICE, key, value)
    except keyring.errors.NoKeyringError:
        try:
            file_store.set(key, value)
        except Exception as file_exc:  # noqa: BLE001
            raise keyring.errors.NoKeyringError(NO_BACKEND_HINT) from file_exc


def delete_token(key: str) -> None:
    """Remove a token from the system keyring."""
    if _forced_file_store():
        file_store.delete(key)
        return
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.NoKeyringError:
        try:
            file_store.delete(key)
        except Exception:  # noqa: BLE001
            pass
    except keyring.errors.PasswordDeleteError:
        pass


def has_token(key: str) -> bool:
    """Check if a token exists in the keyring."""
    return get_token(key) is not None
