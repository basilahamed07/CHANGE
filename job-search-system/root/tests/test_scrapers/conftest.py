"""Scraper test speed: bypass real wall-clock delays during mocked runs.

Product behaviour deliberately sleeps: per-domain token-bucket rate limits
(app/rate_limiter.py, e.g. LinkedIn 1 req / 3s), exponential retry backoff
(app/scrapers/base.py, 2s→4s→8s), and Indeed's anti-detection humanized
delays (app/scrapers/indeed.py). HTTP and the browser are mocked in these
tests, so those sleeps add minutes without testing anything; limiter/backoff
logic has its own unit tests elsewhere. This fixture:
  1. swaps the global domain limiter for an effectively unlimited one,
  2. shrinks BaseScraper backoff delays to near zero,
  3. no-ops asyncio.sleep so hard-coded humanized delays don't run.
Mocked 429/5xx/captcha status handling is still exercised end-to-end.
"""

import asyncio

import pytest

from app.rate_limiter import AsyncRateLimiter
from app.scrapers.base import BaseScraper


async def _instant_sleep(_seconds=None, *args, **kwargs):
    return None


@pytest.fixture(autouse=True)
def _fast_rate_limits_and_backoff(monkeypatch):
    limiter = AsyncRateLimiter(rate=10_000.0, per=1.0)
    monkeypatch.setattr(
        "app.scrapers.base.get_limiter_for_url", lambda url: limiter, raising=True
    )
    monkeypatch.setattr(BaseScraper, "initial_delay", 0.01, raising=True)
    monkeypatch.setattr(BaseScraper, "max_delay", 0.05, raising=True)
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
