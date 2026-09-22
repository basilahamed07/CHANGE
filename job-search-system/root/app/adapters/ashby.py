"""M4: Ashby ATS adapter (ported from ai-job-search, MIT — onto BaseScraper chassis).

API: GET https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeCompensation=true
Non-paginated single response.
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

API_BASE = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
DEFAULT_COMPANIES = ["linear", "ramp", "deel", "walkaway", "openai"]


class AshbyAdapter(JobSourceAdapter, BaseScraper):
    source_name = "ashby"

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)
        self._board_tokens = self._get_tokens()

    def _get_tokens(self) -> list[str]:
        custom = (self.scraper_keys or {}).get("ashby_companies")
        if custom:
            tokens = [c.strip() for c in custom.split(",")] if isinstance(custom, str) else list(custom)
            return [t for t in tokens if t]
        return list(DEFAULT_COMPANIES)

    async def health_check(self) -> dict:
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client, API_BASE.format(token=self._board_tokens[0]))
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        try:
            async with self.get_client() as client:
                for token in self._board_tokens:
                    try:
                        resp = await self.rate_limited_get(
                            client, API_BASE.format(token=token))
                        if resp.status_code == 429:
                            result.stop_reason = STOP_RATE_LIMITED
                            return result
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPStatusError, httpx.TimeoutException,
                            httpx.ConnectError) as e:
                        logger.warning("Ashby %s failed: %s", token, e)
                        result.stop_reason = STOP_SOURCE_FAILURE
                        result.error = str(e)[:160]
                        continue

                    jobs = data.get("jobs") or []
                    for job in jobs:
                        title = job.get("title") or ""
                        if role_terms and not any(t.lower() in title.lower() for t in role_terms):
                            continue
                        loc = job.get("location") or ""
                        if country is not None and not self._in_country(loc, country):
                            continue
                        url = job.get("jobUrl") or job.get("applyUrl") or ""
                        if not validate_url(url):
                            continue
                        comp = (job.get("compensation") or {})
                        salary_components = comp.get("compensationTierSummary") or {}
                        result.listings.append(CanonicalJob(
                            title=title,
                            company=token.replace("-", " ").title(),
                            location=loc,
                            description=(job.get("descriptionPlain") or ""),
                            url=url,
                            source=self.source_name,
                            source_job_id=str(job.get("id") or ""),
                            posted_date=job.get("publishedAt"),
                            employment_type=(comp.get("employmentType") or "").lower(),
                            work_type=(job.get("isRemote") and "remote") or "",
                        ))
                return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("Ashby adapter crashed")
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
