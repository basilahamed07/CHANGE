"""MyCareersFuture (Singapore) — public government job API.

Endpoint (verified live 2026-09-23):
    https://api.mycareersfuture.gov.sg/v2/jobs?search={term}&limit=&page=

No auth required. Only ``search`` proved stable; ``sortBy`` returns 404 on
this API version, so it is deliberately not sent.

Salary note: MCF publishes MONTHLY SGD figures. The pipeline stores annual
amounts and filters on an annual floor, so monthly values are multiplied by
12 here. Currency is not converted (the platform keeps everything in the
source currency, same as every other scraper).
"""

import logging

import httpx

from app.scrapers.base import BaseScraper, JobListing
from app.scrapers.defaults import SEARCH_TERMS as DEFAULT_SEARCH_TERMS

logger = logging.getLogger(__name__)

API_URL = "https://api.mycareersfuture.gov.sg/v2/jobs"
JOB_URL_TEMPLATE = "https://www.mycareersfuture.gov.sg/job/{uuid}"
PAGE_SIZE = 50
MAX_PAGES_PER_TERM = 2
MAX_TERMS = 6          # stay polite to a government API
MIN_WORD_MATCHES = 2
MAX_DESCRIPTION_CHARS = 4000
MONTHS_PER_YEAR = 12


def _norm(text: str) -> str:
    """Fold hyphen/underscore spelling so "Backend Engineer" matches
    "Senior Back-end Engineer" (a very common real-world mismatch)."""
    return text.replace("-", "").replace("_", "")


class MyCareersFutureScraper(BaseScraper):
    source_name = "mycareersfuture"

    def _matches_search(self, searchable: str) -> bool:
        haystack = _norm(searchable)
        for term in self.search_terms:
            words = [_norm(w) for w in term.lower().split()]
            if not words:
                continue
            threshold = min(len(words), MIN_WORD_MATCHES)
            if sum(1 for w in words if w in haystack) >= threshold:
                return True
        return False

    @staticmethod
    def _annual_salary(salary: dict | None) -> tuple[int | None, int | None]:
        """Monthly SGD figures → annual. Returns (min, max)."""
        if not isinstance(salary, dict):
            return None, None
        lo = salary.get("minimum")
        hi = salary.get("maximum")
        try:
            lo_annual = int(lo) * MONTHS_PER_YEAR if lo not in (None, 0) else None
        except (TypeError, ValueError):
            lo_annual = None
        try:
            hi_annual = int(hi) * MONTHS_PER_YEAR if hi not in (None, 0) else None
        except (TypeError, ValueError):
            hi_annual = None
        return lo_annual, hi_annual

    @staticmethod
    def _location(job: dict) -> str:
        if job.get("address") and job["address"].get("overseasCountry"):
            return str(job["address"]["overseasCountry"])
        # MCF is Singapore-only by definition
        return "Singapore"

    async def scrape(self) -> list[JobListing]:
        jobs: list[JobListing] = []
        seen_urls: set[str] = set()
        # The API requires a query term; fall back to the product defaults so
        # the scraper still contributes before a resume has been analyzed.
        terms = self.search_terms or DEFAULT_SEARCH_TERMS
        terms = terms[:MAX_TERMS]

        async with self.get_client() as client:
            for term in terms:
                for page in range(MAX_PAGES_PER_TERM):
                    try:
                        resp = await self.rate_limited_get(
                            client, API_URL,
                            params={"search": term, "limit": PAGE_SIZE, "page": page},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                        logger.error(f"MyCareersFuture scrape failed for '{term}': {e}")
                        break
                    except ValueError as e:
                        logger.error(f"MyCareersFuture returned invalid JSON for '{term}': {e}")
                        break

                    results = data.get("results", []) if isinstance(data, dict) else []
                    if not results:
                        break

                    for item in results:
                        uuid = item.get("uuid", "")
                        title = (item.get("title") or "").strip()
                        if not uuid or not title:
                            continue

                        job_url = JOB_URL_TEMPLATE.format(uuid=uuid)
                        if job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)

                        description = (item.get("description") or "")[:MAX_DESCRIPTION_CHARS]
                        skills = item.get("skills") or []
                        skill_names = [
                            s.get("skill", "") for s in skills if isinstance(s, dict)
                        ]
                        searchable = f"{title} {' '.join(skill_names)} {description[:1200]}".lower()
                        # Only apply local filtering when terms were explicit —
                        # with defaults the API query already scopes the results.
                        if self.search_terms and not self._matches_search(searchable):
                            continue

                        salary_min, salary_max = self._annual_salary(item.get("salary"))
                        company = (item.get("postedCompany") or {}).get("name", "") or \
                                  (item.get("hiringCompany") or {}).get("name", "")

                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location=self._location(item),
                                description=description,
                                url=job_url,
                                source=self.source_name,
                                salary_min=salary_min,
                                salary_max=salary_max,
                                posted_date=(item.get("metadata") or {}).get("newPostingDate"),
                                tags=[s for s in skill_names if s][:12],
                            )
                        )

                    if len(results) < PAGE_SIZE:
                        break

        logger.info(f"MyCareersFuture scraper found {len(jobs)} jobs")
        return jobs
