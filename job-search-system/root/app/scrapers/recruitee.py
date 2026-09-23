"""Recruitee ATS — keyless per-company job JSON.

Endpoint (verified live 2026-09-23):
    https://{company}.recruitee.com/api/offers/   ->   {"offers": [...]}

Same shape as the Greenhouse scraper: a configurable company list with a
default set, per-company failure isolation, and local term matching.
Basil can override the list in Settings → scraper keys as
``recruitee_companies`` (comma-separated).
"""

import logging

import httpx

from app.scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

API_TEMPLATE = "https://{company}.recruitee.com/api/offers/"
MIN_WORD_MATCHES = 2
MAX_DESCRIPTION_CHARS = 4000

# Companies with public, live Recruitee boards (EU-heavy — good for the
# Germany/Netherlands/Ireland market Basil targets).
def _norm(text: str) -> str:
    """Fold hyphen/underscore spelling so "Backend Engineer" matches
    "Senior Back-end Engineer" (a very common real-world mismatch)."""
    return text.replace("-", "").replace("_", "")


DEFAULT_COMPANIES = [
    "channable",
    "sendcloud",
    "bunq",
    "picnic",
    "coolblue",
    "adyen",
    "mollie",
    "depaul",
    "bynder",
    "usabilla",
]


class RecruiteeScraper(BaseScraper):
    source_name = "recruitee"

    def _get_companies(self) -> list[str]:
        custom = self.scraper_keys.get("recruitee_companies")
        if custom:
            if isinstance(custom, str):
                return [c.strip() for c in custom.split(",") if c.strip()]
            return list(custom)
        return DEFAULT_COMPANIES

    def _matches_search(self, title: str, searchable: str) -> bool:
        haystack = _norm(searchable)
        title_norm = _norm(title.lower())
        for term in self.search_terms:
            words = [_norm(w) for w in term.lower().split()]
            if not words:
                continue
            if len(words) == 1:
                if words[0] in title_norm:
                    return True
            else:
                threshold = min(len(words), MIN_WORD_MATCHES)
                if sum(1 for w in words if w in haystack) >= threshold:
                    return True
        return False

    async def scrape(self) -> list[JobListing]:
        jobs: list[JobListing] = []
        seen_urls: set[str] = set()

        async with self.get_client() as client:
            for company in self._get_companies():
                url = API_TEMPLATE.format(company=company)
                try:
                    resp = await self.rate_limited_get(client, url)
                    if resp.status_code == 404:
                        logger.debug(f"Recruitee: board '{company}' not found (404)")
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.error(f"Recruitee scrape failed for {company}: {e}")
                    continue
                except ValueError as e:
                    logger.error(f"Recruitee returned invalid JSON for {company}: {e}")
                    continue

                offers = data.get("offers", []) if isinstance(data, dict) else []
                for item in offers:
                    title = (item.get("title") or "").strip()
                    if not title:
                        continue

                    job_url = item.get("careers_url") or item.get("careers_apply_url") or ""
                    if not job_url:
                        slug = item.get("slug", "")
                        if slug:
                            job_url = f"https://{company}.recruitee.com/o/{slug}"
                    if not job_url or job_url in seen_urls:
                        continue
                    seen_urls.add(job_url)

                    # Location: city/country, or explicit remote flag
                    parts = [p for p in (item.get("city"), item.get("state_name"),
                                         item.get("country")) if p]
                    location = ", ".join(parts)
                    if not location:
                        location = "Remote" if item.get("remote") else ""
                    if not location:
                        location = "Unknown"

                    description = (item.get("description") or "")[:MAX_DESCRIPTION_CHARS]
                    tags = item.get("tags") or []
                    if not isinstance(tags, list):
                        tags = [str(tags)]
                    department = item.get("department") or ""
                    searchable = f"{title} {department} {' '.join(str(t) for t in tags)} {description[:1200]}".lower()

                    if self.search_terms and not self._matches_search(title, searchable):
                        continue

                    jobs.append(
                        JobListing(
                            title=title,
                            company=item.get("company_name") or company.title(),
                            location=location,
                            description=description,
                            url=job_url,
                            source=self.source_name,
                            posted_date=item.get("published_at") or item.get("created_at"),
                            tags=[str(t) for t in tags][:12],
                        )
                    )

        logger.info(f"Recruitee scraper found {len(jobs)} jobs")
        return jobs
