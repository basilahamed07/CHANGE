"""Jooble adapter — ONE API, 25+ countries (keyed; JOBAGENT_JOOBLE_API_KEY).

Endpoint (publicapi.dev/jooble-api, verified shape 2026-09-28):
    POST https://api.jooble.org/api/{api_key}
    body: {"keywords": "...", "location": "...", "page": 1}
    → {"jobs": [...], "totalCount": N}

Jooble is a metasearch engine operating localized boards in ~25 countries —
including ALL sponsor-heavy targets: ca, au, pl, in, de, nl, ie, uk, ae, sg,
and more. This is the single highest-leverage keyed source for the expanded
country list: one key unlocks localized discovery everywhere.

Key handling (same discipline as AdzunaScraper): read from scraper_keys under
"jooble"; without a key the adapter is a silent, honest no-op (SOURCE_FAILURE
with a clear error) so the pipeline completes keyless and lights up the moment
Basil saves his key in Settings → scraper keys.

Country scoping: Jooble's API is location-driven — we pass the country's
region/city as the location parameter AND keep the shared _in_country filter
on results (a listing Jooble returns for 'Canada' that is actually in the US
must not enter the pool).
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

API_URL = "https://api.jooble.org/api/{api_key}"
PAGE_SIZE = 50
MAX_PAGES = 2  # 2 pages × 50 = up to 100 jobs per pass per country

# Jooble location string per Country.region (verified localized boards).
# Falls back to the region name itself for countries not listed here.
REGION_LOCATION = {
    "India": "India",
    "Canada": "Canada",
    "Australia": "Australia",
    "Poland": "Poland",
    "Germany": "Germany",
    "Netherlands": "Netherlands",
    "Ireland": "Ireland",
    "UK": "United Kingdom",
    "Singapore": "Singapore",
    "UAE": "United Arab Emirates",
}


class JoobleAdapter(JobSourceAdapter, BaseScraper):
    source_name = "jooble"

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)

    def _api_key(self) -> str:
        keys = self.scraper_keys.get("jooble", {})
        if isinstance(keys, dict):
            return (keys.get("api_key") or "").strip()
        return ""

    async def health_check(self) -> dict:
        key = self._api_key()
        if not key:
            return {"source": self.source_name, "ok": False,
                    "error": "no API key configured (Settings → scraper keys: 'jooble')"}
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client, API_URL.format(api_key=key),
                    method="POST", json={"keywords": "software engineer",
                                         "location": "Canada", "page": 1})
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        key = self._api_key()
        if not key:
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = "jooble API key not configured (scraper key 'jooble')"
            return result

        region = getattr(country, "region", None) or "Canada"
        location = REGION_LOCATION.get(region, region)
        keywords = " ".join(role_terms[:2]) if role_terms else "software engineer"

        try:
            async with self.get_client() as client:
                seen_urls: set[str] = set()
                for page in range(1, MAX_PAGES + 1):
                    try:
                        resp = await self.rate_limited_get(
                            client, API_URL.format(api_key=key),
                            method="POST",
                            json={"keywords": keywords, "location": location,
                                  "page": page})
                        if resp.status_code == 429:
                            result.stop_reason = STOP_RATE_LIMITED
                            return result
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPStatusError, httpx.TimeoutException,
                            httpx.ConnectError) as e:
                        logger.warning("Jooble %s page %s failed: %s", location, page, e)
                        result.stop_reason = STOP_SOURCE_FAILURE
                        result.error = str(e)[:160]
                        break

                    jobs = data.get("jobs", []) if isinstance(data, dict) else []
                    if not jobs:
                        break

                    for job in jobs:
                        title = (job.get("title") or "").strip()
                        company = (job.get("company") or "").strip()
                        snippet = (job.get("snippet") or job.get("summary") or "").strip()
                        job_url = (job.get("link") or "").strip()
                        loc = (job.get("location") or location).strip()
                        if not title or not job_url:
                            continue
                        if not validate_url(job_url):
                            continue
                        if job_url in seen_urls:   # pagination overlap guard
                            continue
                        seen_urls.add(job_url)
                        # Hard country filter — Jooble's location search can
                        # leak cross-border listings; the orchestrator's region
                        # gate is the backstop, this is the first line.
                        if country is not None and not in_country(loc, country):
                            continue
                        result.listings.append(CanonicalJob(
                            title=title, company=company, location=loc,
                            description=snippet, url=job_url,
                            source=self.source_name,
                            source_job_id=str(job.get("id") or ""),
                            salary_min=job.get("salary_min"),
                            salary_max=job.get("salary_max"),
                            posted_date=job.get("updated") or job.get("date"),
                        ))

                if result.stop_reason == STOP_NO_MORE_RESULTS:
                    result.stop_reason = STOP_NO_MORE_RESULTS
                return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("Jooble adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result
