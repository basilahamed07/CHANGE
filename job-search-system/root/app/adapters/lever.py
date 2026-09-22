"""M4: Lever ATS adapter (ported from ai-job-search, MIT — onto BaseScraper chassis).

API: GET https://api.lever.co/v0/postings/{board_token}?mode=json
Pagination: ?skip=N&limit=25 until an empty page.
"""

from __future__ import annotations

import logging

import httpx

from app.job_adapter import (
    AdapterResult,
    CanonicalJob,
    JobSourceAdapter,
    STOP_NO_MORE_RESULTS,
    STOP_RATE_LIMITED,
    STOP_SOURCE_FAILURE,
)
from app.scrapers.base import BaseScraper, validate_url

logger = logging.getLogger(__name__)

API_BASE = "https://api.lever.co/v0/postings/{token}?mode=json&skip={skip}&limit=100"
PAGE_LIMIT = 25          # pages per pass (25×100 = 2500 postings max/board)
DEFAULT_COMPANIES = [
    # Verified live Lever boards (2026-09-22): spotify + palantir return 200.
    # revolut/wise/nubank/stripe/netflix all 404 — kept short and REAL.
    "spotify", "palantir",
]


class LeverAdapter(JobSourceAdapter, BaseScraper):
    source_name = "lever"

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)
        self._board_tokens = self._get_tokens()

    def _get_tokens(self) -> list[str]:
        custom = (self.scraper_keys or {}).get("lever_companies")
        if custom:
            tokens = [c.strip() for c in custom.split(",")] if isinstance(custom, str) else list(custom)
            return [t for t in tokens if t]
        return list(DEFAULT_COMPANIES)

    async def health_check(self) -> dict:
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client, API_BASE.format(token=self._board_tokens[0], skip=0))
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        try:
            async with self.get_client() as client:
                for token in self._board_tokens:
                    for skip in range(0, PAGE_LIMIT * 100, 100):
                        try:
                            resp = await self.rate_limited_get(
                                client, API_BASE.format(token=token, skip=skip))
                            if resp.status_code == 429:
                                result.stop_reason = STOP_RATE_LIMITED
                                return result
                            resp.raise_for_status()
                            postings = resp.json()
                        except (httpx.HTTPStatusError, httpx.TimeoutException,
                                httpx.ConnectError) as e:
                            logger.warning("Lever %s page %s failed: %s", token, skip, e)
                            result.stop_reason = STOP_SOURCE_FAILURE
                            result.error = str(e)[:160]
                            break

                        if not postings:
                            break  # empty page = board exhausted
                        for job in postings:
                            if not self._matches_terms(job, role_terms):
                                continue
                            loc = ((job.get("categories") or {}).get("location") or "")
                            country_ok = True
                            if country is not None:
                                country_ok = self._in_country(loc, country)
                            if not country_ok:
                                continue
                            cats = job.get("categories") or {}
                            url = job.get("hostedUrl") or ""
                            if not validate_url(url):
                                continue
                            created = job.get("createdAt")
                            posted = None
                            if created:
                                from app.job_adapter import normalize_posted_date
                                posted = normalize_posted_date(int(created))
                            result.listings.append(CanonicalJob(
                                title=job.get("text") or "",
                                company=token.replace("-", " ").title(),
                                location=loc,
                                description=((job.get("descriptionPlain") or "") + " "
                                             + (job.get("additionalPlain") or "")).strip(),
                                url=url,
                                source=self.source_name,
                                source_job_id=str(job.get("id") or ""),
                                posted_date=posted,
                                work_type={"remote": "remote",
                                           "hybrid": "hybrid"}.get(
                                               (job.get("workplaceType") or "").lower(), "onsite"),
                            ))
                if result.stop_reason == STOP_NO_MORE_RESULTS:
                    result.stop_reason = STOP_NO_MORE_RESULTS
                return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("Lever adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result

    def _matches_terms(self, job: dict, role_terms: list[str]) -> bool:
        if not role_terms:
            return True
        title = (job.get("text") or "").lower()
        dept = ((job.get("categories") or {}).get("department") or "").lower()
        blob = title + " " + dept
        return any(t.lower() in blob for t in role_terms)

    def _in_country(self, location: str, country) -> bool:
        loc = (location or "").lower()
        names = {country.region.lower(), country.name.lower(), *country.aliases}
        for city in country.cities:
            if city and city in loc:
                return True
        return any(n and n in loc for n in names)
