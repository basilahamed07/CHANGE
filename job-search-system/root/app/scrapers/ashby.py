"""Ashby ATS — keyless public job-board API.

Endpoint (verified live 2026-09-23):
    https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeCompensation=true

One request per company; the response is a single non-paginated `jobs` array.
Every job carries structured compensation (`compensationTiers[].components[]`),
which we normalise into annual salary_min / salary_max.

Mirrors the existing Greenhouse scraper's company-list convention: a
comma-separated `ashby_companies` scraper key overrides DEFAULT_COMPANIES.
Only boards verified to return jobs are listed (probed live 2026-09-23).
"""

import logging

import httpx

from app.scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

API_BASE = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
MIN_WORD_MATCHES = 3
MAX_DESCRIPTION_CHARS = 6000

# Boards verified live on 2026-09-23 (name -> job count at probe time).
DEFAULT_COMPANIES = [
    "openai",
    "harvey",
    "sierra",
    "ramp",
    "cohere",
    "notion",
    "cursor",
    "vanta",
    "supabase",
    "synthesia",
    "qonto",
    "n8n",
    "sanity",
    "linear",
    "paddle",
    "gorgias",
    "ledger",
    "runway",
    "weaviate",
    "clerk",
]


def _norm(text: str) -> str:
    """Fold hyphen/underscore spelling so "Backend" matches "Back-end"."""
    return text.replace("-", "").replace("_", "")


def _annual_salary(compensation: dict | None) -> tuple[int | None, int | None]:
    """Pull the salary component out of Ashby's nested compensation block.

    Picks the Salary component whose interval is a year (or that has no
    interval), ignoring equity/bonus components.
    """
    if not isinstance(compensation, dict):
        return None, None
    tiers = compensation.get("compensationTiers")
    if not isinstance(tiers, list):
        return None, None
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        for comp in tier.get("components") or []:
            if not isinstance(comp, dict):
                continue
            if str(comp.get("compensationType", "")).lower() != "salary":
                continue
            interval = str(comp.get("interval") or "").upper()
            if interval and not interval.startswith("1 YEAR") and "YEAR" not in interval:
                continue
            low = comp.get("minValue")
            high = comp.get("maxValue")
            if isinstance(low, (int, float)) or isinstance(high, (int, float)):
                return (
                    int(low) if isinstance(low, (int, float)) else None,
                    int(high) if isinstance(high, (int, float)) else None,
                )
    return None, None


class AshbyScraper(BaseScraper):
    source_name = "ashby"

    def _get_companies(self) -> list[str]:
        custom = self.scraper_keys.get("ashby_companies")
        if custom:
            if isinstance(custom, str):
                return [c.strip() for c in custom.split(",") if c.strip()]
            return list(custom)
        return DEFAULT_COMPANIES

    def _matches_search(self, title: str, searchable: str) -> bool:
        for term in self.search_terms:
            words = [_norm(w) for w in term.lower().split()]
            if not words:
                continue
            if len(words) <= 1:
                if words[0] in _norm(title.lower()):
                    return True
            else:
                threshold = min(len(words), MIN_WORD_MATCHES)
                matched = sum(1 for w in words if w in _norm(searchable))
                if matched >= threshold:
                    return True
        return False

    async def scrape(self) -> list[JobListing]:
        jobs: list[JobListing] = []
        seen_urls: set[str] = set()

        async with self.get_client() as client:
            for company in self._get_companies():
                url = API_BASE.format(token=company)
                try:
                    resp = await self.rate_limited_get(client, url)
                    if resp.status_code == 404:
                        logger.debug(f"Ashby: board '{company}' not found (404)")
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.error(f"Ashby scrape failed for {company}: {e}")
                    continue
                except ValueError as e:
                    logger.error(f"Ashby returned invalid JSON for {company}: {e}")
                    continue

                for item in data.get("jobs", []) or []:
                    title = (item.get("title") or "").strip()
                    if not title:
                        continue

                    job_url = item.get("jobUrl") or item.get("applyUrl") or ""
                    if not job_url or job_url in seen_urls:
                        continue
                    seen_urls.add(job_url)

                    location = (item.get("location") or "").strip()
                    if item.get("isRemote"):
                        location = f"{location} (Remote)".strip() if location else "Remote"
                    if not location:
                        addr = item.get("address") or {}
                        postal = addr.get("postalAddress") if isinstance(addr, dict) else {}
                        if isinstance(postal, dict):
                            location = postal.get("addressLocality") or postal.get("addressCountry") or ""
                    if not location:
                        location = "Remote"

                    description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
                    searchable = f"{title} {description} {location}".lower()
                    if self.search_terms and not self._matches_search(title, searchable):
                        continue

                    salary_min, salary_max = _annual_salary(item.get("compensation"))

                    tags = []
                    for key in ("department", "team", "employmentType"):
                        value = item.get(key)
                        if value and str(value) not in tags:
                            tags.append(str(value))

                    posted_date = None
                    published = item.get("publishedAt")
                    if published:
                        posted_date = str(published)[:10]

                    jobs.append(
                        JobListing(
                            title=title,
                            company=company,
                            location=location,
                            description=description[:MAX_DESCRIPTION_CHARS],
                            url=job_url,
                            source=self.source_name,
                            salary_min=salary_min,
                            salary_max=salary_max,
                            posted_date=posted_date,
                            tags=tags,
                        )
                    )

        logger.info(f"Ashby scraper found {len(jobs)} jobs")
        return jobs
