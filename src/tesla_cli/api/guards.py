"""Single-flight guard for expensive endpoints.

Login, portal scraping and dossier rebuilds spawn headless-browser
subprocesses that run for up to five minutes. Without a guard, a client (or a
buggy dashboard retry loop) can start dozens of them and exhaust a small
home server. Only one run per operation is allowed at a time; concurrent
callers get ``429 Too Many Requests``.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _registry_lock:
        return _locks.setdefault(name, threading.Lock())


@contextmanager
def single_flight(name: str) -> Iterator[None]:
    lock = _lock_for(name)
    if not lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail=f"A {name} run is already in progress. Try again when it finishes.",
            headers={"Retry-After": "30"},
        )
    try:
        yield
    finally:
        lock.release()


def guarded(name: str):
    """Decorator form of :func:`single_flight` for sync route handlers."""
    import functools

    def deco(fn):
        @functools.wraps(fn)  # keeps the signature FastAPI inspects
        def wrapper(*args, **kwargs):
            with single_flight(name):
                return fn(*args, **kwargs)

        return wrapper

    return deco
