"""Reed UK adapter — official Reed job board API (keyed; JOBAGENT_REED_API_KEY).

Endpoint (https://reed.co.uk developer portal — free key, instant email):
    GET https://www.reed.co.uk/api/1.0/search?keywords=…&locationName=…&resultsToTake=100
    auth: HTTP Basic with the API key as username, empty password
    → {"results": [{jobId, employerName, jobTitle, locationName, minimumSalary,
       maximumSalary, currency, date, jobUrl, jobDescription}], "totalResults"}

Reed is the UK's largest commercial board and its API is officially public —
the highest-value future adapter from the research doc (§11, priority #1):
one key unlocks UK discovery with structured salary + date data.

Country scoping: the API is UK-only by definition (region_hint='UK' skips
other countries honestly); the shared in_country filter + orchestrator region
gate remain as backstops.

Key handling (same discipline as Jooble/Adzuna): scraper key 'reed'; without
a key the adapter is an honest no-op (SOURCE_FAILURE, clear error).
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
from app.adapters.country_facade import in_country

logger = logging.getLogger(__name__)

API_URL = "https://www.reed.co.uk/api/1.0/search"
RESULTS_TO_TAKE = 100
MAX_PAGES = 2
REGION_HINT = "UK"


class ReedAdapter(JobSourceAdapter, BaseScraper):
    source_name = "reed"
    region_hint = REGION_HINT

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)

    def _api_key(self) -> str:
        keys = self.scraper_keys.get("reed", {})
        if isinstance(keys, dict):
            return (keys.get("api_key") or "").strip()
        return ""

    async def health_check(self) -> dict:
        key = self._api_key()
        if not key:
            return {"source": self.source_name, "ok": False,
                    "error": "no API key configured (Settings → scraper keys: 'reed')"}
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client, API_URL,
                    auth=(key, ""),
                    params={"keywords": "software engineer",
                            "resultsToTake": 1})
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        # UK-only API — another country gets an honest empty pass (no waste).
        if country is not None and getattr(country, "region", "") != REGION_HINT:
            result.error = f"reed covers {REGION_HINT} only"
            return result

        key = self._api_key()
        if not key:
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = "reed API key not configured (scraper key 'reed')"
            return result

        keywords = " ".join(role_terms[:2]) if role_terms else "software engineer"
        # London anchors the search; in_country keeps every UK city match.
        location = "London"

        try:
            async with self.get_client() as client:
                seen_urls: set[str] = set()
                for page in range(1, MAX_PAGES + 1):  # pages start at 1 for Reed
                    try:
                        resp = await self.rate_limited_get(
                            client, API_URL,
                            auth=(key, ""),
                            params={"keywords": keywords,
                                    "locationName": location,
                                    "resultsToTake": RESULTS_TO_TAKE,
                                    "resultsToSkip": (page - 1) * RESULTS_TO_TAKE})
                        if resp.status_code == 429:
                            result.stop_reason = STOP_RATE_LIMITED
                            return result
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPStatusError, httpx.TimeoutException,
                            httpx.ConnectError) as e:
                        logger.warning("Reed page %s failed: %s", page, e)
                        result.stop_reason = STOP_SOURCE_FAILURE
                        result.error = str(e)[:160]
                        break

                    items = data.get("results", []) if isinstance(data, dict) else []
                    if not items:
                        break

                    for item in items:
                        title = (item.get("jobTitle") or "").strip()
                        job_url = (item.get("jobUrl") or "").strip()
                        if not title or not job_url:
                            continue
                        if not validate_url(job_url):
                            continue
                        if job_url in seen_urls:  # pagination overlap guard
                            continue
                        seen_urls.add(job_url)
                        loc = (item.get("locationName") or "UK").strip()
                        if not in_country(loc, country):
                            continue
                        result.listings.append(CanonicalJob(
                            title=title,
                            company=(item.get("employerName") or "").strip(),
                            location=loc,
                            description=(item.get("jobDescription") or "").strip(),
                            url=job_url,
                            source=self.source_name,
                            source_job_id=str(item.get("jobId") or ""),
                            salary_min=item.get("minimumSalary"),
                            salary_max=item.get("maximumSalary"),
                            salary_currency=(item.get("currency") or "GBP"),
                            posted_date=item.get("date"),
                        ))

                if result.stop_reason == STOP_NO_MORE_RESULTS:
                    result.stop_reason = STOP_NO_MORE_RESULTS
                return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("Reed adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result
