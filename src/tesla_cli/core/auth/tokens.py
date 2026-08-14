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

# Native EV planner BYOK keys (Phase 1 + Phase 2)
PLANNER_OPENROUTE_KEY = "planner-openroute-key"
PLANNER_OPENCHARGEMAP_KEY = "planner-openchargemap-key"
PLANNER_WEATHER_KEY = "planner-weather-key"


NO_BACKEND_HINT = (
    "No system keyring backend is available. On headless Linux or in Docker, "
    "install one (e.g. `apt install gnome-keyring`, or `pip install keyrings.alt` "
    "for a file-backed store) or set PYTHON_KEYRING_BACKEND to a supported backend."
)


def get_token(key: str) -> str | None:
    """Retrieve a token from the system keyring.

    Returns None when no keyring backend is available — headless Linux, Docker,
    CI — rather than raising. Every caller treats a missing token as "this
    credential is not configured", which is the correct reading here: a machine
    with no keyring cannot have stored one.
    """
    try:
        return keyring.get_password(SERVICE, key)
    except keyring.errors.KeyringError:
        return None


def set_token(key: str, value: str) -> None:
    """Store a token in the system keyring.

    Unlike reads, a failed write is never silent: the caller asked to persist a
    credential, and pretending it worked would lose it.
    """
    try:
        keyring.set_password(SERVICE, key, value)
    except keyring.errors.NoKeyringError as exc:
        raise keyring.errors.NoKeyringError(NO_BACKEND_HINT) from exc


def delete_token(key: str) -> None:
    """Remove a token from the system keyring."""
    try:
        keyring.delete_password(SERVICE, key)
    except (keyring.errors.PasswordDeleteError, keyring.errors.NoKeyringError):
        pass


def has_token(key: str) -> bool:
    """Check if a token exists in the keyring."""
    return get_token(key) is not None
