"""Landing.jobs — keyless public JSON feed of European tech jobs.

Endpoint (verified live 2026-09-23): https://landing.jobs/api/v1/jobs?limit=N
Returns a JSON array. Supports `limit`, `page` and `offset` query params.

This source is EU-weighted (Portugal/Spain/Germany/NL/remote-EU), which fits
the country strategy for DE / IE / NL in config/countries/.

Filtering is local; the search-terms match runs over title + tags + role text.
"""

import logging

import httpx

from app.scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

API_URL = "https://landing.jobs/api/v1/jobs"
PAGE_SIZE = 100
MAX_PAGES = 3
MIN_WORD_MATCHES = 2
MAX_DESCRIPTION_CHARS = 6000


def _norm(text: str) -> str:
    """Fold hyphen/underscore spelling so "Backend" matches "Back-end"."""
    return text.replace("-", "").replace("_", "")


def _locations_text(item: dict) -> str:
    """Render the locations array into a readable string."""
    locs = item.get("locations")
    parts: list[str] = []
    if isinstance(locs, list):
        for loc in locs:
            if isinstance(loc, dict):
                city = loc.get("city") or ""
                country = loc.get("country_code") or ""
                label = ", ".join(p for p in (city, country) if p)
                if label and label not in parts:
                    parts.append(label)
            elif isinstance(loc, str) and loc and loc not in parts:
                parts.append(loc)
    text = "; ".join(parts)
    if item.get("remote") and "remote" not in text.lower():
        text = f"{text} (Remote)".strip() if text else "Remote"
    return text or "Remote"


def _int_or_none(value) -> int | None:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _company_from(item: dict, url: str) -> str:
    """Landing.jobs has no company field; the URL encodes it as /at/<slug>/."""
    company = item.get("company")
    if isinstance(company, dict) and company.get("name"):
        return str(company["name"])
    if isinstance(company, str) and company:
        return company
    try:
        parts = [p for p in url.split("/") if p]
        if "at" in parts:
            slug = parts[parts.index("at") + 1]
            return slug.replace("-", " ").title()
    except (IndexError, ValueError):
        pass
    return ""


class LandingJobsScraper(BaseScraper):
    source_name = "landingjobs"

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
                    logger.error(f"Landing.jobs scrape failed (page {page}): {e}")
                    break
                except ValueError as e:
                    logger.error(f"Landing.jobs returned invalid JSON: {e}")
                    break

                listings = data if isinstance(data, list) else data.get("jobs", [])
                if not listings:
                    break

                for item in listings:
                    if not isinstance(item, dict):
                        continue
                    title = (item.get("title") or "").strip()
                    if not title:
                        continue

                    url = item.get("url") or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    location = _locations_text(item)

                    tags = item.get("tags")
                    tag_list: list[str] = []
                    if isinstance(tags, list):
                        for t in tags:
                            if isinstance(t, dict):
                                label = t.get("name") or t.get("label")
                                if label:
                                    tag_list.append(str(label))
                            elif t:
                                tag_list.append(str(t))
                    elif isinstance(tags, str):
                        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

                    description = " ".join(
                        str(item.get(k) or "")
                        for k in ("role_description", "main_requirements", "nice_to_have")
                    )
                    searchable = f"{title} {description} {location} {' '.join(tag_list)}".lower()
                    if self.search_terms and not self._matches_search(searchable):
                        continue

                    published = item.get("published_at")
                    posted_date = str(published)[:10] if published else None

                    jobs.append(
                        JobListing(
                            title=title,
                            company=_company_from(item, url),
                            location=location,
                            description=description[:MAX_DESCRIPTION_CHARS],
                            url=url,
                            source=self.source_name,
                            salary_min=_int_or_none(item.get("gross_salary_low")),
                            salary_max=_int_or_none(item.get("gross_salary_high")),
                            posted_date=posted_date,
                            tags=tag_list[:12],
                        )
                    )

                if len(listings) < PAGE_SIZE:
                    break

        logger.info(f"Landing.jobs scraper found {len(jobs)} jobs")
        return jobs
