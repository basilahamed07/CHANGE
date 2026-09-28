"""Adzuna adapter — country-scoped search over Adzuna's per-country API (keyed).

Endpoint: GET https://api.adzuna.com/v1/api/jobs/{cc}/search/{page}
    params: app_id, app_key, what, results_per_page
    cc = 2-letter country code (us/gb/de/nl/ie/in/au/pl/ae/sg/…; ca via 'ca' too)

The legacy AdzunaScraper is US-hardcoded (API_URL pins /jobs/us/). This adapter
generalizes it: the M3 Country object's ISO `code` picks the Adzuna market, so
the same key serves discovery in Germany, India, Canada, Australia, Poland, …

Key handling: scraper_keys 'adzuna' (app_key) + 'adzuna-id' (app_id) — the same
entries the Settings UI already saves for the legacy scraper. Without keys:
honest no-op (SOURCE_FAILURE with a clear error).

Country scoping: the API does the geographic work; the shared _in_country
filter plus the orchestrator's region gate remain as backstops.
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

API_URL = "https://api.adzuna.com/v1/api/jobs/{cc}/search/{page}"
PAGE_SIZE = 50
MAX_PAGES = 2
# Country.region → Adzuna 2-letter market code (API supports ~20 markets).
REGION_CC = {
    "Germany": "de", "Netherlands": "nl", "Ireland": "ie", "UK": "gb",
    "India": "in", "Canada": "ca", "Australia": "au", "Poland": "pl",
    "UAE": "ae", "Singapore": "sg",
}


class AdzunaAdapter(JobSourceAdapter, BaseScraper):
    source_name = "adzuna"

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)

    def _credentials(self) -> tuple[str, str]:
        keys = self.scraper_keys or {}
        app_key = ""
        app_id = ""
        entry = keys.get("adzuna", {})
        if isinstance(entry, dict):
            app_key = (entry.get("api_key") or "").strip()
        id_entry = keys.get("adzuna-id", {})
        if isinstance(id_entry, dict):
            app_id = (id_entry.get("api_key") or "").strip()
        return app_id, app_key

    async def health_check(self) -> dict:
        app_id, app_key = self._credentials()
        if not app_id or not app_key:
            return {"source": self.source_name, "ok": False,
                    "error": "no API keys configured (scraper keys 'adzuna' + 'adzuna-id')"}
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client, API_URL.format(cc="gb", page=1),
                    params={"app_id": app_id, "app_key": app_key,
                            "what": "software engineer", "results_per_page": 1})
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        app_id, app_key = self._credentials()
        if not app_id or not app_key:
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = "adzuna keys not configured (scraper keys 'adzuna' + 'adzuna-id')"
            return result

        region = getattr(country, "region", None) or "UK"
        cc = REGION_CC.get(region)
        if cc is None:
            # No Adzuna market for this country — honest skip, not a failure.
            result.stop_reason = STOP_NO_MORE_RESULTS
            result.error = f"no adzuna market for region {region}"
            return result
        what = " ".join(role_terms[:2]) if role_terms else "software engineer"

        try:
            async with self.get_client() as client:
                seen_urls: set[str] = set()
                for page in range(1, MAX_PAGES + 1):
                    try:
                        resp = await self.rate_limited_get(
                            client, API_URL.format(cc=cc, page=page),
                            params={"app_id": app_id, "app_key": app_key,
                                    "what": what, "results_per_page": PAGE_SIZE})
                        if resp.status_code == 429:
                            result.stop_reason = STOP_RATE_LIMITED
                            return result
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPStatusError, httpx.TimeoutException,
                            httpx.ConnectError) as e:
                        logger.warning("Adzuna %s page %s failed: %s", cc, page, e)
                        result.stop_reason = STOP_SOURCE_FAILURE
                        result.error = str(e)[:160]
                        break

                    items = data.get("results", []) if isinstance(data, dict) else []
                    if not items:
                        break

                    for item in items:
                        title = (item.get("title") or "").strip()
                        company = (item.get("company") or {}).get("display_name", "")
                        loc = (item.get("location") or {}).get("display_name", "")
                        job_url = (item.get("redirect_url") or "").strip()
                        if not title or not job_url:
                            continue
                        if not validate_url(job_url):
                            continue
                        if job_url in seen_urls:   # pagination overlap guard
                            continue
                        seen_urls.add(job_url)
                        if country is not None and not in_country(loc, country):
                            continue
                        salary_min = item.get("salary_min")
                        salary_max = item.get("salary_max")
                        result.listings.append(CanonicalJob(
                            title=title,
                            company=(company or "").strip(),
                            location=(loc or "").strip(),
                            description=(item.get("description") or "").strip(),
                            url=job_url,
                            source=self.source_name,
                            salary_min=int(salary_min) if salary_min else None,
                            salary_max=int(salary_max) if salary_max else None,
                            posted_date=item.get("created"),
                        ))

                if result.stop_reason == STOP_NO_MORE_RESULTS:
                    result.stop_reason = STOP_NO_MORE_RESULTS
                return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("Adzuna adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result
