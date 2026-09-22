"""M4: Greenhouse adapter — facade over the existing GreenhouseScraper.

The scraper already runs on BaseScraper and returns JobListing objects;
the facade normalizes them into CanonicalJob so the orchestrator can treat
every source identically (Greenhouse first, per the M4 plan).
"""

from __future__ import annotations

import logging

from app.job_adapter import (
    AdapterResult,
    CanonicalJob,
    JobSourceAdapter,
    STOP_NO_MORE_RESULTS,
    STOP_SOURCE_FAILURE,
)
from app.scrapers.greenhouse import GreenhouseScraper

logger = logging.getLogger(__name__)


class GreenhouseAdapter(JobSourceAdapter):
    source_name = "greenhouse"

    def __init__(self, search_terms=None, scraper_keys=None):
        self._scraper = GreenhouseScraper(
            search_terms=search_terms, scraper_keys=scraper_keys)

    async def health_check(self) -> dict:
        try:
            async with self._scraper.get_client() as client:
                resp = await self._scraper.rate_limited_get(
                    client, "https://boards-api.greenhouse.io/v1/boards/vercel/jobs")
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        try:
            self._scraper.search_terms = list(role_terms or self._scraper.search_terms or [])
            listings = await self._scraper.scrape()
            for li in listings:
                if country is not None and not self._in_country(li.location, country):
                    continue
                result.listings.append(CanonicalJob(
                    title=li.title, company=li.company, location=li.location,
                    description=li.description, url=li.url,
                    source=self.source_name,
                    salary_min=li.salary_min, salary_max=li.salary_max,
                    posted_date=li.posted_date,
                    contact_email=li.contact_email, tags=list(li.tags),
                ))
            return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("Greenhouse adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result

    def _in_country(self, location: str, country) -> bool:
        loc = (location or "").lower()
        names = {country.region.lower(), country.name.lower(), *country.aliases}
        for city in country.cities:
            if city and city in loc:
                return True
        return any(n and n in loc for n in names)
