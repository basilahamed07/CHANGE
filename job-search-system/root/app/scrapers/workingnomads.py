"""Working Nomads — keyless public JSON feed of remote jobs.

Endpoint (verified live 2026-09-23): https://www.workingnomads.com/api/exposed_jobs/
Returns a flat JSON array; no pagination, no auth.

Filtering is local (the API has no query params for terms), so the scraper
matches search terms against title + tags + description and relies on the
scheduler's deterministic title gate for the rest.
"""

import html
import logging

import httpx

from app.scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

API_URL = "https://www.workingnomads.com/api/exposed_jobs/"
MIN_WORD_MATCHES = 2
MAX_DESCRIPTION_CHARS = 4000


def _norm(text: str) -> str:
    """Fold hyphen/underscore spelling so "Backend Engineer" matches
    "Senior Back-end Engineer" (a very common real-world mismatch)."""
    return text.replace("-", "").replace("_", "")


class WorkingNomadsScraper(BaseScraper):
    source_name = "workingnomads"

    def _matches_search(self, searchable: str) -> bool:
        """At least MIN_WORD_MATCHES words of a term must appear."""
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
            try:
                resp = await self.rate_limited_get(client, API_URL)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                logger.error(f"WorkingNomads scrape failed: {e}")
                return []
            except ValueError as e:  # non-JSON body
                logger.error(f"WorkingNomads returned invalid JSON: {e}")
                return []

            listings = data if isinstance(data, list) else data.get("jobs", [])
            for item in listings:
                title = html.unescape(str(item.get("title", ""))).strip()
                if not title:
                    continue

                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                tags = item.get("tags", "") or ""
                if isinstance(tags, list):
                    tags = ",".join(str(t) for t in tags)
                tag_list = [t.strip() for t in str(tags).split(",") if t.strip()]

                description = item.get("description", "") or ""
                searchable = f"{title} {tags} {description[:1500]}".lower()
                if self.search_terms and not self._matches_search(searchable):
                    continue

                jobs.append(
                    JobListing(
                        title=title,
                        company=html.unescape(str(item.get("company_name", ""))).strip(),
                        location=item.get("location") or "Remote",
                        description=description[:MAX_DESCRIPTION_CHARS],
                        url=url,
                        source=self.source_name,
                        posted_date=item.get("pub_date"),
                        tags=tag_list[:12],
                    )
                )

        logger.info(f"WorkingNomads scraper found {len(jobs)} jobs")
        return jobs
