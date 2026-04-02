"""Tessie authentication helpers."""

from tesla_cli.core.auth.tokens import TESSIE_TOKEN, get_token
from tesla_cli.core.exceptions import AuthenticationError


def get_tessie_token() -> str:
    """Get Tessie token or raise."""
    token = get_token(TESSIE_TOKEN)
    if not token:
        raise AuthenticationError("Tessie not configured. Run: tesla config auth tessie")
    return token
