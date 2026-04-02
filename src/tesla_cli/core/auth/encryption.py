"""Optional AES-256-GCM encryption for tokens stored on headless servers.

Usage:
    from tesla_cli.core.auth.encryption import encrypt_token, decrypt_token, is_encrypted

    ciphertext = encrypt_token("my-secret-token", password="s3cr3t")
    plaintext  = decrypt_token(ciphertext, password="s3cr3t")
"""

from __future__ import annotations

import base64
import os

_MARKER = "enc1:"  # prefix to identify encrypted tokens


def is_encrypted(value: str) -> bool:
    """Return True if value is an encrypted token (has enc1: prefix)."""
    return isinstance(value, str) and value.startswith(_MARKER)


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key from password using PBKDF2-HMAC-SHA256."""
    import hashlib

    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations=260_000, dklen=32)


def encrypt_token(plaintext: str, password: str) -> str:
    """Encrypt plaintext token with AES-256-GCM. Returns base64(salt+nonce+tag+ct) with enc1: prefix."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ImportError(
            "cryptography is required for token encryption.\n"
            "Install with: uv pip install cryptography"
        ) from exc

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)  # includes 16-byte tag appended
    blob = base64.b64encode(salt + nonce + ciphertext).decode()
    return _MARKER + blob


def decrypt_token(encrypted: str, password: str) -> str:
    """Decrypt an enc1:-prefixed token. Raises ValueError on wrong password or corrupted data."""
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ImportError(
            "cryptography is required for token decryption.\n"
            "Install with: uv pip install cryptography"
        ) from exc

    if not is_encrypted(encrypted):
        raise ValueError("Not an encrypted token (missing enc1: prefix)")

    try:
        raw = base64.b64decode(encrypted[len(_MARKER) :])
        salt, nonce, ct_tag = raw[:16], raw[16:28], raw[28:]
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct_tag, None).decode()
    except (InvalidTag, Exception) as exc:
        raise ValueError("Decryption failed — wrong password or corrupted token") from exc
