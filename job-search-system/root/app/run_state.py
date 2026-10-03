"""Per-user background run state (N3).

Discovery / scrape / scoring progress used to live in single **process-global**
``app.state`` slots. That meant user A starting a run made user B's request
return ``already_running`` / **409**, and B's progress bar showed *A's* numbers.

This registry keys every run by user id. An unauthenticated or testing caller
(the pre-M15c path) uses the ``ANON`` key, so old behaviour is unchanged when
there is no workspace.

A per-IP advisory counter bounds concurrent *scrapes* from one host so a single
machine cannot launch N concurrent scrape storms; a caller over the cap gets a
clear 429 rather than a silent no-op.
"""

from __future__ import annotations

import asyncio

ANON = "anon"
MAX_CONCURRENT_SCRAPES_PER_IP = 3


def user_key(request) -> str:
    """Stable run-state key for a request — the user id, or ANON."""
    user = getattr(request.state, "user", None)
    if user and user.get("id") is not None:
        return str(user["id"])
    return ANON


class RunRegistry:
    """Process-wide registry of per-user background runs."""

    def __init__(self) -> None:
        self._slots: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._ip_active: dict[str, int] = {}

    def slot(self, key: str) -> dict:
        return self._slots.setdefault(key, {
            "discovery_running": False,
            "discovery_progress": {},
            "discovery_telemetry": None,
            "scrape_progress": None,
            "scrape_task": None,
            "scoring_progress": None,
        })

    def lock(self, key: str) -> asyncio.Lock:
        """Per-user scoring lock — one user's scoring never blocks another's."""
        return self._locks.setdefault(key, asyncio.Lock())

    # -- per-IP advisory scrape cap --------------------------------------
    def ip_active(self, ip: str | None) -> int:
        return self._ip_active.get(ip, 0) if ip else 0

    def ip_enter(self, ip: str | None) -> None:
        if ip:
            self._ip_active[ip] = self._ip_active.get(ip, 0) + 1

    def ip_exit(self, ip: str | None) -> None:
        if not ip:
            return
        remaining = self._ip_active.get(ip, 0) - 1
        if remaining <= 0:
            self._ip_active.pop(ip, None)
        else:
            self._ip_active[ip] = remaining


def run_slot(request) -> dict:
    """The requesting user's run-state slot."""
    return request.app.state.run_registry.slot(user_key(request))
