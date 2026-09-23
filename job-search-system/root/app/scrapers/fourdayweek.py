"""4dayweek.io — keyless public JSON feed of remote, flexible-schedule jobs.

Endpoint (verified live 2026-09-23):
    https://4dayweek.io/api/jobs?limit=N&page=P
Response shape: {"jobs": [...], "total": N, "page": P, "has_more": bool}

Covers companies that offer a 4-day week, flexible hours or full remote work —
a useful complement to the general-purpose remote boards. Salaries arrive in
minor units (cents) so they are divided down to annual figures before handing
them to JobListing, whose sanity bounds reject the raw values.

Filtering is local; the match runs over title + category + level + location.
"""

import logging
from datetime import datetime, timezone

import httpx

from app.scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

API_URL = "https://4dayweek.io/api/jobs"
PAGE_SIZE = 100
MAX_PAGES = 3
MIN_WORD_MATCHES = 2
JOB_URL = "https://4dayweek.io/job/{slug}"


def _norm(text: str) -> str:
    """Fold hyphen/underscore spelling so "Backend" matches "Back-end"."""
    return text.replace("-", "").replace("_", "")


def _locations_text(item: dict) -> str:
    """Render the locations array (or work_arrangement) into a readable string."""
    parts: list[str] = []
    locs = item.get("locations")
    if isinstance(locs, list):
        for loc in locs:
            if isinstance(loc, dict):
                label = loc.get("country") or loc.get("continent") or ""
                if label and label not in parts:
                    parts.append(label)
            elif isinstance(loc, str) and loc and loc not in parts:
                parts.append(loc)
    text = "; ".join(parts)
    arrangement = item.get("work_arrangement")
    if arrangement and str(arrangement).lower() not in text.lower():
        pretty = str(arrangement).replace("_", " ").title()
        text = f"{text} ({pretty})".strip() if text else pretty
    return text or "Remote"


def _annual_salary(item: dict) -> tuple[int | None, int | None]:
    """Convert 4dayweek's minor-unit salaries into annual figures.

    `salary_lower`/`salary_upper` are in cents per `salary_period`
    (7000000/year -> $70,000), so: cents -> dollars (÷100), then scale the
    pay period up to a year (×1 / ×12 / ×52 / ×260 / ×2080).
    """
    period = str(item.get("salary_period") or "year").lower()
    per_year = 1
    if period == "month":
        per_year = 12
    elif period in ("hour", "hourly", "hr"):
        per_year = 2080
    elif period == "week":
        per_year = 52
    elif period in ("day", "daily"):
        per_year = 260

    def convert(value):
        if not isinstance(value, (int, float)) or value <= 0:
            return None
        try:
            return int((value / 100) * per_year)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    return convert(item.get("salary_lower")), convert(item.get("salary_upper"))


class FourDayWeekScraper(BaseScraper):
    source_name = "4dayweek"

    def _matches_search(self, searchable: str) -> bool:
        haystack = _norm(searchable)
        for term in self.search_terms:
            words = [_norm(w) for w in term.lower().split()]
            if not words:
                continue
            threshold = min(len(words), MIN_WORD_MATCHES)
            matched = sum(1 for w in words if w in haystack)
            if matched >= threshold:
                return True
        return False

    async def scrape(self) -> list[JobListing]:
        jobs: list[JobListing] = []
        seen_urls: set[str] = set()

        async with self.get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                try:
                    resp = await self.rate_limited_get(
                        client, API_URL, params={"limit": PAGE_SIZE, "page": page}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.error(f"4dayweek scrape failed (page {page}): {e}")
                    break
                except ValueError as e:
                    logger.error(f"4dayweek returned invalid JSON: {e}")
                    break

                listings = data.get("jobs", []) if isinstance(data, dict) else []
                if not listings:
                    break

                for item in listings:
                    if not isinstance(item, dict) or item.get("is_expired"):
                        continue
                    title = (item.get("title") or "").strip()
                    if not title:
                        continue

                    slug = item.get("slug")
                    url = JOB_URL.format(slug=slug) if slug else ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    location = _locations_text(item)
                    tags = [str(t) for t in (item.get("category"), item.get("level"), item.get("schedule_type")) if t]

                    searchable = f"{title} {location} {' '.join(tags)}".lower()
                    if self.search_terms and not self._matches_search(searchable):
                        continue

                    posted_date = None
                    posted = item.get("posted")
                    if isinstance(posted, (int, float)) and posted > 0:
                        try:
                            posted_date = datetime.fromtimestamp(posted, tz=timezone.utc).strftime("%Y-%m-%d")
                        except (OverflowError, OSError, ValueError):
                            posted_date = None
                    if not posted_date:
                        inserted = item.get("inserted")
                        if inserted:
                            posted_date = str(inserted)[:10]

                    salary_min, salary_max = _annual_salary(item)
                    description = " ".join(
                        str(x) for x in (item.get("salary"), item.get("category"), item.get("level"), item.get("schedule_type"), item.get("work_life_score")) if x
                    )

                    jobs.append(
                        JobListing(
                            title=title,
                            company=(item.get("company_name") or "").strip(),
                            location=location,
                            description=description,
                            url=url,
                            source=self.source_name,
                            salary_min=salary_min,
                            salary_max=salary_max,
                            posted_date=posted_date,
                            tags=tags,
                        )
                    )

                if not (isinstance(data, dict) and data.get("has_more")):
                    break

        logger.info(f"4dayweek scraper found {len(jobs)} jobs")
        return jobs
