"""Secure token storage via system keyring (macOS Keychain, etc.)."""

import keyring

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


def get_token(key: str) -> str | None:
    """Retrieve a token from the system keyring."""
    return keyring.get_password(SERVICE, key)


def set_token(key: str, value: str) -> None:
    """Store a token in the system keyring."""
    keyring.set_password(SERVICE, key, value)


def delete_token(key: str) -> None:
    """Remove a token from the system keyring."""
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass


def has_token(key: str) -> bool:
    """Check if a token exists in the keyring."""
    return get_token(key) is not None
