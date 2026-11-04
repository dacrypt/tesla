"""Helpers for URLs that carry secrets or that the server will call.

- :func:`mask_secret_url` hides tokens/passwords embedded in notification URLs
  (Apprise URLs such as ``tgram://<bot-token>/<chat>``) before they are shown.
- :func:`check_outbound_url` limits automation webhooks to plain HTTP(S) and
  refuses link-local / cloud-metadata targets (SSRF). Private LAN addresses
  stay allowed: posting to Home Assistant on ``192.168.x.x`` is a core
  self-hosted use case.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata", "instance-data"})


def mask_secret_url(url: str) -> str:
    """Return ``scheme://host…`` with credentials, path and query masked.

    ``tgram://123:ABC/456`` → ``tgram://***``;
    ``https://user:pw@hooks.example/abc?t=1`` → ``https://hooks.example/***``.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "***"
    scheme = parts.scheme or "?"
    if scheme in ("http", "https", "json", "jsons", "form", "forms", "xml", "xmls"):
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        rest = "/***" if (parts.path not in ("", "/") or parts.query) else ""
        return f"{scheme}://{host}{rest}"
    # Most Apprise schemes put the secret in the "host" (bot tokens, keys).
    return f"{scheme}://***"


class UnsafeUrlError(ValueError):
    """Raised when an outbound URL is not allowed."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved


def check_outbound_url(url: str, *, resolve: bool = True) -> str:
    """Validate a webhook URL; return it unchanged or raise :class:`UnsafeUrlError`."""
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise UnsafeUrlError("Malformed URL.") from exc
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrlError("Webhook URL must use http:// or https://.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeUrlError("Webhook URL has no host.")
    if host in _METADATA_HOSTS:
        raise UnsafeUrlError("Webhook URL targets a cloud metadata endpoint.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked_ip(literal):
            raise UnsafeUrlError("Webhook URL targets a link-local or reserved address.")
        return url
    if resolve:
        try:
            infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
        except OSError:
            return url  # unresolvable now; the request itself will fail
        for info in infos:
            try:
                ip = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if _is_blocked_ip(ip):
                raise UnsafeUrlError("Webhook URL resolves to a link-local or reserved address.")
    return url
