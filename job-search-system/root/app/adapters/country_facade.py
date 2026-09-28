"""Shared country-scoping facade for adapters that wrap existing BaseScrapers.

GreenhouseAdapter established the pattern: wrap a scraper, run one scrape pass,
filter listings to the target country, normalize into CanonicalJob. The legacy
scrapers (M-4 era) had that logic missing — they ingested into whatever region
the scheduler happened to allow. This facade gives every one of them honest
country scoping so the M4 discovery orchestrator can use them for ANY enabled
country (Germany, India, Canada, Australia, Poland, …).

Country filter contract (same as GreenhouseAdapter/LeverAdapter):
  location matches if it contains the country's region string, display name,
  any alias, or any city — case-insensitive substring on the lowercased
  location. A listing that fails the filter is DROPPED, not dismissed —
  the region gate in the orchestrator is the second line of defence.

Adapter contract (Golden Rule 9): search() NEVER raises; every failure is an
AdapterResult with stop_reason=SOURCE_FAILURE and an error string.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.job_adapter import (
    AdapterResult,
    CanonicalJob,
    JobSourceAdapter,
    STOP_NO_MORE_RESULTS,
    STOP_SOURCE_FAILURE,
)
from app.scrapers.base import BaseScraper, validate_url

logger = logging.getLogger(__name__)


def in_country(location: str, country) -> bool:
    """Shared country-scoping rule (identical to the ATS adapters' rule)."""
    loc = (location or "").lower()
    names = {country.region.lower(), country.name.lower(), *country.aliases}
    for city in country.cities:
        if city and city in loc:
            return True
    return any(n and n in loc for n in names)


def epoch_to_date(value) -> str | None:
    """Epoch seconds → ISO date (None on garbage)."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


class CountryScopedAdapter(JobSourceAdapter):
    """Base for adapters that wrap one legacy BaseScraper subclass.

    Subclasses set `scraper_cls` (and optionally override health_check).
    `region_hint`: single-country sources (MyCareersFuture→Singapore,
    Reed→UK) short-circuit other countries with an honest empty pass —
    saving 9 wasted scrape passes per cycle while keeping telemetry clean.
    """

    scraper_cls: type[BaseScraper] | None = None
    region_hint: str | None = None

    def __init__(self, search_terms=None, scraper_keys=None):
        self._search_terms = list(search_terms or [])
        self._scraper_keys = dict(scraper_keys or {})

    def _build_scraper(self) -> BaseScraper:
        return self.scraper_cls(search_terms=self._search_terms,
                                scraper_keys=self._scraper_keys)

    async def health_check(self) -> dict:
        """Default: run a tiny scrape pass — ok if it returns without crashing.

        Per-adapter overrides give a cheaper probe where one exists.
        """
        try:
            scraper = self._build_scraper()
            listings = await scraper.scrape()
            return {"source": self.source_name, "ok": True, "listings": len(listings)}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        # Single-country source pointed at another country: honest skip.
        if (self.region_hint and country is not None
                and getattr(country, "region", "") != self.region_hint):
            result.error = f"{self.source_name} covers {self.region_hint} only"
            return result
        try:
            scraper = self._build_scraper()
            scraper.search_terms = list(role_terms or self._search_terms or [])
            listings = await scraper.scrape()
            dropped = seen = 0
            seen_urls: set[str] = set()
            for li in listings:
                if country is not None and not in_country(li.location, country):
                    dropped += 1
                    continue
                if not validate_url(li.url):
                    continue
                # Pagination-overlap guard: some wrapped scrapers fetch multiple
                # pages without deduping; identical URLs must not double-count.
                if li.url in seen_urls:
                    seen += 1
                    continue
                seen_urls.add(li.url)
                result.listings.append(CanonicalJob(
                    title=li.title, company=li.company, location=li.location,
                    description=li.description, url=li.url,
                    source=self.source_name,
                    salary_min=li.salary_min, salary_max=li.salary_max,
                    posted_date=li.posted_date,
                    contact_email=li.contact_email, tags=list(li.tags),
                ))
            if dropped or seen:
                logger.debug("%s: dropped %d outside %s, %d repeat URLs",
                             self.source_name, dropped,
                             getattr(country, "region", "?"), seen)
            return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("%s adapter crashed", self.source_name)
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result
