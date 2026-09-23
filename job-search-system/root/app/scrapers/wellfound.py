import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, JobListing, validate_salary

logger = logging.getLogger(__name__)

# Wellfound (formerly AngelList Talent) aggressively blocks automated access.
# This scraper attempts to parse their pages but may get 403 responses.
# If Wellfound returns data, it typically uses Next.js with __NEXT_DATA__ or
# Apollo GraphQL state embedded in the page.

BASE_URL = "https://wellfound.com"

# Standard Wellfound role slugs — these are real paths on wellfound.com.
ROLE_SLUG_MAP = {
    "software": "/role/r/software-engineer",
    "backend": "/role/r/backend-engineer",
    "frontend": "/role/r/frontend-engineer",
    "full stack": "/role/r/full-stack-engineer",
    "fullstack": "/role/r/full-stack-engineer",
    "devops": "/role/r/devops-engineer",
    "sre": "/role/r/site-reliability-engineer",
    "site reliability": "/role/r/site-reliability-engineer",
    "infrastructure": "/role/r/infrastructure-engineer",
    "data engineer": "/role/r/data-engineer",
    "data scientist": "/role/r/data-scientist",
    "data": "/role/r/data-engineer",
    "machine learning": "/role/r/machine-learning-engineer",
    "ml": "/role/r/machine-learning-engineer",
    "ai": "/role/r/machine-learning-engineer",
    "mobile": "/role/r/mobile-engineer",
    "ios": "/role/r/ios-engineer",
    "android": "/role/r/android-engineer",
    "security": "/role/r/security-engineer",
    "cloud": "/role/r/cloud-engineer",
    "platform": "/role/r/platform-engineer",
    "qa": "/role/r/qa-engineer",
    "test": "/role/r/qa-engineer",
    "product manager": "/role/r/product-manager",
    "designer": "/role/r/product-designer",
    "ux": "/role/r/product-designer",
}

DEFAULT_ROLES = [
    "/role/r/software-engineer",
    "/role/r/backend-engineer",
    "/role/r/full-stack-engineer",
    "/role/r/devops-engineer",
    "/role/r/data-engineer",
]

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # NOTE: do NOT set Accept-Encoding manually — declaring "br" makes
    # Cloudflare serve a Brotli body that httpx will not auto-decompress
    # (manual headers disable its default negotiation), leaving the parser
    # with binary garbage. Let httpx advertise encodings it can decode.
    "Referer": "https://wellfound.com/",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}  # "Connection"/"Keep-Alive" are forbidden headers managed by httpcore


class WellfoundScraper(BaseScraper):
    source_name = "wellfound"

    def _get_role_paths(self) -> list[str]:
        if not self.search_terms:
            return DEFAULT_ROLES

        paths = []
        seen = set()
        for term in self.search_terms:
            term_lower = term.lower().strip()
            matched = False
            # Try exact match first, then substring match
            for keyword, path in ROLE_SLUG_MAP.items():
                if keyword in term_lower or term_lower in keyword:
                    if path not in seen:
                        paths.append(path)
                        seen.add(path)
                    matched = True
                    break
            if not matched:
                # Fall back to slugifying single/double word terms that look
                # like they could be a Wellfound role slug
                slug = re.sub(r"[^a-z0-9]+", "-", term_lower).strip("-")
                path = f"/role/r/{slug}"
                if path not in seen:
                    paths.append(path)
                    seen.add(path)

        # Also include default roles to broaden coverage
        for path in DEFAULT_ROLES:
            if path not in seen:
                paths.append(path)
                seen.add(path)

        return paths[:10]

    def _matches_search_terms(self, searchable: str) -> bool:
        """Check if searchable text matches any search term.

        Splits each search term into words and requires at least 2 words
        (or all words if the term has fewer than 2) to appear in the text.
        """
        for term in self.search_terms:
            words = term.lower().split()
            if not words:
                continue
            threshold = min(2, len(words))
            matched = sum(1 for w in words if w in searchable)
            if matched >= threshold:
                return True
        return False

    def _parse_next_data(self, html: str) -> list[dict]:
        """Extract job data from __NEXT_DATA__ script tag (Next.js SSR)."""
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        payload = script.string if script else None
        if not payload:
            # Wellfound emits <script id="__NEXT_DATA__" type="application/json"
            # crossorigin="anonymous"> — BeautifulSoup may not expose .string
            # when the tag has extra attributes, so fall back to regex.
            match = re.search(
                r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            )
            payload = match.group(1) if match else None
        if not payload:
            return []

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []

        return self._extract_jobs_from_next_data(data)

    def _extract_jobs_from_next_data(self, data: dict) -> list[dict]:
        """Walk the __NEXT_DATA__ structure to find job listings."""
        jobs = []
        props = data.get("props", {}).get("pageProps", {})

        # Try common patterns for job data in Next.js apps
        for key in ["jobs", "jobListings", "listings", "results", "data"]:
            items = props.get(key)
            if isinstance(items, list):
                jobs.extend(items)
                break

        # Try nested Apollo state (__APOLLO_STATE__ embedded in pageProps)
        apollo_state = props.get("apolloState") or props.get("__APOLLO_STATE__")
        if apollo_state and isinstance(apollo_state, dict):
            jobs.extend(self._extract_jobs_from_apollo_state(apollo_state))

        return jobs

    def _extract_jobs_from_apollo_state(self, apollo_state: dict) -> list[dict]:
        """Extract jobs from an Apollo cache map (normalised GraphQL entities).

        Wellfound's current SEO pages store results as
        ``JobListingSearchResult:<id>`` entities under ``apolloState.data``
        (legacy ``JobListing``/``StartupJobListing``/``Job`` typenames are
        also accepted). Company info lives on sibling ``StartupResult``
        entities; matching is done by the ``StartupResult:<id>`` reference
        found inside ``ROOT_QUERY.talent.seoLandingPageJobSearchResults(...)``,
        which lists startups in the same order as their highlighted jobs.
        """
        data_map = apollo_state.get("data") if isinstance(apollo_state.get("data"), dict) else apollo_state

        job_entities: dict[str, dict] = {}
        startup_entities: list[dict] = []
        for key, value in data_map.items():
            if not isinstance(value, dict):
                continue
            typename = value.get("__typename")
            if typename in ("JobListing", "StartupJobListing", "Job", "JobListingSearchResult"):
                job_entities[key] = value
            elif typename == "StartupResult":
                startup_entities.append(value)

        jobs: list[dict] = []
        if job_entities:
            # Attach company names by resolving __ref links where possible.
            startup_names: dict[str, str] = {}
            for startup in startup_entities:
                sid = str(startup.get("id", ""))
                if sid:
                    startup_names[sid] = startup.get("name", "")

            for entity_key, job in job_entities.items():
                enriched = dict(job)
                if not enriched.get("startup") and not enriched.get("company"):
                    # Try to recover the company from the entity key prefix
                    # (e.g. "JobListingSearchResult:3392132" carries no ref).
                    # StartupResult entities expose highlightedJobListings
                    # refs — prefer those, then fall back to page order.
                    for startup in startup_entities:
                        refs = startup.get("highlightedJobListings") or []
                        for ref in refs:
                            if isinstance(ref, dict) and ref.get("__ref") == entity_key:
                                enriched["startup"] = {"name": startup.get("name", "")}
                                break
                        if enriched.get("startup"):
                            break
                jobs.append(enriched)

        return jobs

    def _parse_apollo_state(self, html: str) -> list[dict]:
        """Extract job data from Apollo GraphQL state embedded in HTML."""
        jobs = []
        match = re.search(
            r'window\.__APOLLO_STATE__\s*=\s*({.*?});?\s*</script>',
            html,
            re.DOTALL,
        )
        if not match:
            return []

        try:
            state = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        for key, value in state.items():
            if isinstance(value, dict) and value.get("__typename") in (
                "JobListing", "StartupJobListing", "Job",
            ):
                jobs.append(value)

        return jobs

    def _parse_jsonld(self, html: str) -> list[dict]:
        """Extract job data from JSON-LD structured data."""
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "JobPosting":
                        jobs.append(item)
            elif data.get("@type") == "JobPosting":
                jobs.append(data)

        return jobs

    def _job_from_raw(self, item: dict) -> JobListing | None:
        """Convert a raw job dict (from any source) to a JobListing."""
        # Handle JSON-LD JobPosting format
        if item.get("@type") == "JobPosting":
            org = item.get("hiringOrganization", {})
            company = org.get("name", "") if isinstance(org, dict) else ""
            location_data = item.get("jobLocation", {})
            address = location_data.get("address", {}) if isinstance(location_data, dict) else {}
            location = address.get("addressLocality", "Remote") or "Remote"

            salary = item.get("baseSalary", {})
            salary_val = salary.get("value", {}) if isinstance(salary, dict) else {}
            salary_min = salary_val.get("minValue") if isinstance(salary_val, dict) else None
            salary_max = salary_val.get("maxValue") if isinstance(salary_val, dict) else None

            return JobListing(
                title=item.get("title", ""),
                company=company,
                location=location,
                description=item.get("description", ""),
                url=item.get("url", ""),
                source=self.source_name,
                salary_min=_parse_int(salary_min),
                salary_max=_parse_int(salary_max),
                posted_date=item.get("datePosted"),
            )

        # Handle Wellfound's internal data format (Apollo/Next.js)
        title = item.get("title") or item.get("name", "")
        if not title:
            return None

        company = ""
        startup = item.get("startup") or item.get("company")
        if isinstance(startup, dict):
            company = startup.get("name", "")
        elif isinstance(startup, str):
            company = startup

        location = ""
        raw_location = item.get("location")
        if isinstance(raw_location, dict):
            location = raw_location.get("name", "")
        elif isinstance(raw_location, str):
            location = raw_location
        if not location:
            # JobListingSearchResult format: locationNames[] + remote flag
            location_names = item.get("locationNames") or item.get("acceptedRemoteLocationNames") or []
            if location_names and isinstance(location_names, list):
                location = ", ".join(str(n) for n in location_names[:3])
            elif item.get("remote") is True:
                location = "Remote"
        if not location:
            location = "Remote"

        slug = item.get("slug", "")
        job_id = item.get("id", "")
        url = item.get("url", "")
        if not url and slug and job_id:
            # Current Wellfound job URLs are /jobs/<id>-<slug>
            url = f"{BASE_URL}/jobs/{job_id}-{slug}"
        elif not url and slug:
            url = f"{BASE_URL}/jobs/{slug}"
        elif not url and job_id:
            url = f"{BASE_URL}/jobs/{job_id}"

        salary_min = item.get("salaryMin") or item.get("salary_min")
        salary_max = item.get("salaryMax") or item.get("salary_max")
        if salary_min is None or salary_max is None:
            # JobListingSearchResult format: compensation is a string like
            # "$150k – $280k" or "$90k".
            comp_min, comp_max = _parse_compensation(item.get("compensation"))
            salary_min = salary_min if salary_min is not None else comp_min
            salary_max = salary_max if salary_max is not None else comp_max

        tags = item.get("tags", [])
        if isinstance(tags, list) and tags and isinstance(tags[0], dict):
            tags = [t.get("name", "") for t in tags if t.get("name")]

        return JobListing(
            title=title,
            company=company,
            location=location,
            description=item.get("description", ""),
            url=url,
            source=self.source_name,
            salary_min=_parse_int(salary_min),
            salary_max=_parse_int(salary_max),
            posted_date=item.get("postedAt") or item.get("posted_at"),
            tags=tags if isinstance(tags, list) else [],
        )

    async def scrape(self) -> list[JobListing]:
        paths = self._get_role_paths()
        jobs = []
        seen_urls = set()

        async with self.get_client() as client:
            for path in paths:
                url = f"{BASE_URL}{path}"
                try:
                    resp = await self.rate_limited_get(
                        client, url, headers=BROWSER_HEADERS,
                    )
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in (403, 429):
                        logger.warning(f"Wellfound blocked ({status}) for {path}")
                    else:
                        logger.error(f"Wellfound HTTP {status} for {path}")
                    continue
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.error(f"Wellfound fetch failed for {path}: {e}")
                    continue

                html = resp.text

                # Try multiple extraction strategies
                raw_jobs = self._parse_next_data(html)
                if not raw_jobs:
                    raw_jobs = self._parse_apollo_state(html)
                if not raw_jobs:
                    raw_jobs = self._parse_jsonld(html)

                logger.info(f"Wellfound: {path} returned {len(raw_jobs)} jobs")

                for item in raw_jobs:
                    job = self._job_from_raw(item)
                    if not job or not job.title:
                        continue

                    if job.url in seen_urls:
                        continue
                    seen_urls.add(job.url)

                    if self.search_terms:
                        searchable = f"{job.title} {job.description} {' '.join(job.tags)}".lower()
                        if not self._matches_search_terms(searchable):
                            continue

                    jobs.append(job)

        logger.info(f"Wellfound scraper found {len(jobs)} jobs")
        return jobs


def _parse_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_compensation(value) -> tuple[int | None, int | None]:
    """Parse Wellfound's compensation string into (min, max) annual salary.

    Handles formats like "$150k – $280k", "$90k", "€60k - €80k".
    """
    if not value or not isinstance(value, str):
        return None, None
    matches = re.findall(r"[$€£]?\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmM]?)", value)
    amounts: list[int] = []
    for num, suffix in matches:
        try:
            amount = float(num)
        except ValueError:
            continue
        if suffix.lower() == "k":
            amount *= 1_000
        elif suffix.lower() == "m":
            amount *= 1_000_000
        amounts.append(int(amount))
    amounts = [a for a in amounts if validate_salary(a)]
    if not amounts:
        return None, None
    if len(amounts) == 1:
        return amounts[0], None
    return min(amounts), max(amounts)
