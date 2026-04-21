"""Regression: refresh_access_token() must preserve the original token's scopes.

If the refresh endpoint silently returns a narrower scope set, commands will
start failing at runtime with confusing 403s even though the user never
changed anything.  The oauth layer should not drop scopes on refresh — any
new token's ``scp`` claim must be a superset of the original.
"""

from __future__ import annotations

import base64
import json


def _mk_jwt(scopes: list[str]) -> str:
    """Build a minimal unsigned JWT with the given ``scp`` claim.

    The three-segment format is the only thing the decoder here cares about;
    the signature is irrelevant because the test decodes the payload
    directly (no verification).
    """

    def _b64(obj: object) -> str:
        data = json.dumps(obj).encode("utf-8") if not isinstance(obj, bytes) else obj
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64({"scp": scopes, "sub": "test"})
    signature = _b64(b"sig")
    return f"{header}.{payload}.{signature}"


def _decode_scp(token: str) -> list[str]:
    """Decode the ``scp`` claim from an unsigned/signed JWT (no verification)."""
    payload_b64 = token.split(".")[1]
    # Pad to a multiple of 4.
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    return list(payload.get("scp", []))


def test_refresh_preserves_scope(httpx_mock):
    """refresh_access_token() must return a token whose scp claim is a
    superset of the original token's scopes."""
    from tesla_cli.core.auth.oauth import TOKEN_URL, refresh_access_token

    original_scopes = [
        "openid",
        "email",
        "offline_access",
        "user_data",
        "vehicle_device_data",
        "vehicle_location",
        "vehicle_cmds",
        "vehicle_charging_cmds",
    ]
    original_refresh = _mk_jwt(original_scopes)

    # The refresh endpoint returns a NEW access token that carries the same
    # scopes (Tesla's actual behaviour on a successful refresh).
    new_access = _mk_jwt(original_scopes)
    httpx_mock.add_response(
        url=TOKEN_URL,
        method="POST",
        json={
            "access_token": new_access,
            "refresh_token": original_refresh,
            "expires_in": 28800,
            "token_type": "Bearer",
            "scope": " ".join(original_scopes),
        },
        status_code=200,
    )

    result = refresh_access_token(original_refresh, client_id="ownerapi")

    assert "access_token" in result, "refresh response missing access_token"
    returned_scopes = set(_decode_scp(result["access_token"]))

    missing = set(original_scopes) - returned_scopes
    assert not missing, (
        f"Refreshed token is missing scopes that were present before: {missing}."
        f" scp claim must be a superset of the original."
    )
