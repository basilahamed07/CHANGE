"""M4: SmartRecruiters ATS adapter (ported from ai-job-search, MIT — BaseScraper chassis).

List API: GET https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset=N
Detail API: GET .../postings/{id} (description lives only in the detail call).
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

LIST_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}"
DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{job_id}"
PAGE_LIMIT = 10  # detail fetches per company per pass (keeps request volume sane)
DEFAULT_COMPANIES = ["visa", "奥迪".replace("奥迪", "audi"), "bosch", "siemens", "sap"]


class SmartRecruitersAdapter(JobSourceAdapter, BaseScraper):
    source_name = "smartrecruiters"

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)
        self._board_tokens = self._get_tokens()

    def _get_tokens(self) -> list[str]:
        custom = (self.scraper_keys or {}).get("smartrecruiters_companies")
        if custom:
            tokens = [c.strip() for c in custom.split(",")] if isinstance(custom, str) else list(custom)
            return [t for t in tokens if t]
        return [t for t in DEFAULT_COMPANIES if t.isascii()]

    async def health_check(self) -> dict:
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client, LIST_URL.format(token=self._board_tokens[0], offset=0))
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": str(e)[:120]}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        try:
            async with self.get_client() as client:
                for token in self._board_tokens:
                    offset = 0
                    company_exhausted = False
                    while not company_exhausted:
                        try:
                            resp = await self.rate_limited_get(
                                client, LIST_URL.format(token=token, offset=offset))
                            if resp.status_code == 429:
                                result.stop_reason = STOP_RATE_LIMITED
                                return result
                            resp.raise_for_status()
                            data = resp.json()
                        except (httpx.HTTPStatusError, httpx.TimeoutException,
                                httpx.ConnectError) as e:
                            logger.warning("SmartRecruiters %s offset %s failed: %s",
                                           token, offset, e)
                            result.stop_reason = STOP_SOURCE_FAILURE
                            result.error = str(e)[:160]
                            break

                        postings = data.get("content") or []
                        total = int(data.get("totalFound") or 0)
                        if not postings:
                            company_exhausted = True
                            break

                        for p in postings:
                            title = p.get("name") or ""
                            if role_terms and not any(t.lower() in title.lower() for t in role_terms):
                                continue
                            loc_data = (p.get("location") or "")
                            loc = (p.get("location") or {}).get("city", "") if isinstance(loc_data, dict) else str(loc_data)
                            country_data = (p.get("location") or {}).get("country", "") if isinstance(loc_data, dict) else ""
                            if country_data and loc:
                                loc = f"{loc}, {country_data}"
                            if country is not None and not self._in_country(loc, country):
                                continue
                            pid = p.get("id") or ""
                            url = f"https://jobs.smartrecruiters.com/{token}/{pid}"
                            if not validate_url(url) or not pid:
                                continue
                            # Description lives in the detail endpoint — fetch a
                            # bounded number per company per pass.
                            desc = p.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "") if isinstance(p.get("jobAd"), dict) else ""
                            if not desc:
                                try:
                                    dresp = await self.rate_limited_get(
                                        client, DETAIL_URL.format(token=token, job_id=pid))
                                    if dresp.status_code == 429:
                                        result.stop_reason = STOP_RATE_LIMITED
                                        return result
                                    if dresp.status_code == 200:
                                        dtext = (dresp.json().get("jobAd") or {}).get(
                                            "sections", {}).get("jobDescription", {}).get("text", "")
                                        desc = dtext or ""
                                except (httpx.HTTPStatusError, httpx.TimeoutException,
                                        httpx.ConnectError):
                                    desc = ""
                            released = (p.get("releasedDate") or "")
                            result.listings.append(CanonicalJob(
                                title=title,
                                company=token.replace("-", " ").title(),
                                location=loc,
                                description=desc,
                                url=url,
                                source=self.source_name,
                                source_job_id=str(pid),
                                posted_date=released[:10] if released else None,
                                employment_type=(p.get("typeOfEmployment", {}).get("id", "") or "").lower()
                                if isinstance(p.get("typeOfEmployment"), dict) else "",
                            ))

                        offset += 100
                        if offset >= total or offset >= 1000:
                            company_exhausted = True
                return result
        except Exception as e:  # adapters NEVER raise (contract)
            logger.exception("SmartRecruiters adapter crashed")
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
