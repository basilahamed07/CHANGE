"""DIRECT COMPANY CAREER DISCOVERY (task §10) + JobPosting JSON-LD parsing.

The system must not depend entirely on job boards. This module discovers jobs
from the company's own careers pages:

    Company → find career page → detect ATS?
        ├─ YES → route to the existing ATS adapter (app.ats_detect.adapter_for)
        └─ NO  → parse JobPosting JSON-LD from the page (schema.org)
                 └─ none → give up honestly (health status, no fabrication)

JSON-LD JobPosting is the structured-data standard Google reads careers pages
with — it carries title, datePosted, hiringOrganization, jobLocation and a
direct apply URL WITHOUT any scraping heuristics. It is the sanctioned,
public, structured path (task §24) — no CAPTCHA evasion, no stealth browsers.

Company/career-URL metadata is CACHED in the existing `companies` table
(new careers_ats + careers_checked_at columns) so the same company is not
re-crawled every run (task §31). Everything normalizes into the EXISTING
CanonicalJob — no parallel job model (task §16).
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.adapters.country_facade import in_country
from app.ats_detect import adapter_for, detect_ats
from app.job_adapter import (
    AdapterResult,
    CanonicalJob,
    JobSourceAdapter,
    STOP_NO_MORE_RESULTS,
    STOP_SOURCE_FAILURE,
)
from app.scrapers.base import validate_url
from app.source_registry import Access

logger = logging.getLogger(__name__)

SOURCE_NAME = "company_careers"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36")
REQUEST_TIMEOUT = 12.0
MAX_COMPANIES_PER_PASS = 25          # bounded passes (task §30)
JSON_LD_MAX_BYTES = 2_000_000        # do not parse absurd pages

# Common careers-page paths tried when only a domain is known.
CAREER_PATHS = ("/careers", "/jobs", "/company/careers", "/about/careers")

# <script type="application/ld+json"> ... </script> — DotAll for multiline blobs.
_LD_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# JSON-LD JobPosting extraction (pure functions — unit-testable, no HTTP)
# ---------------------------------------------------------------------------

def extract_jsonld_blocks(html: str) -> list:
    """All JSON-LD objects found in a page, flattening @graph lists."""
    blocks: list = []
    for raw in _LD_SCRIPT_RE.findall(html or ""):
        raw = raw.strip()
        if not raw or len(raw) > JSON_LD_MAX_BYTES:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue  # malformed blob is skipped, not fatal
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                blocks.extend(d for d in graph if isinstance(d, dict))
            else:
                blocks.append(data)
    return blocks


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _location_text(node: dict) -> str:
    """jobLocation → 'City, Country' text from the common shapes."""
    parts: list[str] = []
    for loc in _as_list(node.get("jobLocation")):
        if isinstance(loc, str):
            parts.append(loc)
            continue
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address") or {}
        if isinstance(addr, list):
            addr = addr[0] if addr else {}
        if not isinstance(addr, dict):
            continue
        city = addr.get("addressLocality") or ""
        country = addr.get("addressCountry") or ""
        if isinstance(country, dict):
            country = country.get("name") or ""
        combo = ", ".join(p for p in (str(city).strip(), str(country).strip()) if p)
        if combo:
            parts.append(combo)
    # applicantLocationRequirements (remote roles) as a fallback signal
    if not parts:
        for req in _as_list(node.get("applicantLocationRequirements")):
            if isinstance(req, dict):
                name = req.get("name") or ""
                if name:
                    parts.append(str(name))
    return parts[0] if parts else ""


def _apply_url(node: dict, page_url: str) -> str:
    url = ""
    apply_action = node.get("directApply")
    if isinstance(apply_action, dict):
        target = apply_action.get("url") or ""
        url = target.get("url") if isinstance(target, dict) else str(target or "")
    if not url:
        url = str(node.get("url") or node.get("@id") or "")
    if not url:
        same_as = node.get("sameAs")
        if isinstance(same_as, str):
            url = same_as
    if not url:
        url = page_url  # the careers page itself is where the posting lives
    if url.startswith("/"):
        base = page_url.rsplit("/", 3)[0] if page_url.count("/") > 3 else page_url
        url = base.rstrip("/") + url
    return url if validate_url(url) else (page_url if validate_url(page_url) else "")


def _salary(node: dict) -> tuple[int | None, int | None, str]:
    base = node.get("baseSalary") or {}
    if isinstance(base, list):
        base = base[0] if base else {}
    value = base.get("value") or {}
    if isinstance(value, list):
        value = value[0] if value else {}
    lo = value.get("minValue")
    hi = value.get("maxValue")
    currency = base.get("currency") or value.get("currency") or ""
    def _num(v):
        try:
            n = int(float(v))
            return n if 10_000 <= n <= 2_000_000 else None
        except (TypeError, ValueError):
            return None
    return _num(lo), _num(hi), str(currency or "")


def jsonld_to_canonical(node: dict, company: str, page_url: str) -> CanonicalJob | None:
    """One schema.org JobPosting → CanonicalJob (None when not a JobPosting)."""
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    if not any(t in ("JobPosting", "http://schema.org/JobPosting",
                     "https://schema.org/JobPosting") for t in types):
        return None
    title = str(node.get("title") or node.get("name") or "").strip()
    if not title:
        return None
    org = node.get("hiringOrganization") or {}
    if isinstance(org, list):
        org = org[0] if org else {}
    company_name = str(org.get("name") or company or "").strip()
    location = _location_text(node)
    salary_min, salary_max, currency = _salary(node)
    emp = str(node.get("employmentType") or "").strip()
    posted = str(node.get("datePosted") or "").strip() or None
    url = _apply_url(node, page_url)
    if not url:
        return None
    remote_flag = "remote" in title.lower() or "remote" in location.lower()
    return CanonicalJob(
        title=title, company=company_name or company,
        location=location or ("Remote" if remote_flag else ""),
        description=str(node.get("description") or "")[:6000],
        url=url, source=SOURCE_NAME,
        source_job_id=str(node.get("identifier") or node.get("@id") or ""),
        salary_min=salary_min, salary_max=salary_max,
        salary_currency=currency, posted_date=posted,
        employment_type=emp.lower().replace("-", "_"),
        work_type="remote" if remote_flag else "",
        tags=["direct-career", "jsonld"],
    )


def parse_job_postings(html: str, company: str, page_url: str) -> list[CanonicalJob]:
    """All valid CanonicalJobs from a careers page's JSON-LD, deduped by URL."""
    jobs: list[CanonicalJob] = []
    seen: set[str] = set()
    for node in extract_jsonld_blocks(html):
        job = jsonld_to_canonical(node, company, page_url)
        if job and job.url not in seen:
            seen.add(job.url)
            jobs.append(job)
    return jobs


# ---------------------------------------------------------------------------
# Career-page discovery helpers (pure — no network)
# ---------------------------------------------------------------------------

def candidate_career_urls(company_domain: str) -> list[str]:
    """URLs to probe for a company domain (career paths, best-guess order)."""
    domain = (company_domain or "").strip().strip("/").replace("https://", "").replace("http://", "")
    if not domain or "." not in domain:
        return []
    base = f"https://{domain}"
    return [base + p for p in CAREER_PATHS] + [f"https://careers.{domain}",
                                               f"https://jobs.{domain}"]


async def resolve_career_page(client: httpx.AsyncClient, company_domain: str) -> tuple[str, str]:
    """Probe candidate URLs; return (career_url, ats_provider|'')."""
    for url in candidate_career_urls(company_domain):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=REQUEST_TIMEOUT)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError):
            continue
        if resp.status_code != 200:
            continue
        ats = detect_ats(str(resp.url))
        if ats or _LD_SCRIPT_RE.search(resp.text):
            return str(resp.url), ats or ""
    return "", ""


# ---------------------------------------------------------------------------
# The adapter (JobSourceAdapter contract — never raises)
# ---------------------------------------------------------------------------

class CompanyCareersAdapter(JobSourceAdapter):
    """Discovers jobs straight from configured companies' own career pages.

    Configure target companies via scraper key 'career_companies'
    (comma-separated domains: 'openai.com,deeplearning.ai'). Companies whose
    career page sits on an ATS host are NOT fetched here — the orchestrator
    routes them to the existing ATS adapter instead (single parsing path).
    """

    source_name = SOURCE_NAME

    def __init__(self, search_terms=None, scraper_keys=None, companies=None):
        self._search_terms = list(search_terms or [])
        keys = dict(scraper_keys or {})
        raw = companies if companies is not None else keys.get("career_companies", "")
        if isinstance(raw, str):
            self._domains = [d.strip() for d in raw.split(",") if d.strip()]
        else:
            self._domains = [str(d).strip() for d in raw if str(d).strip()]
        self._domains = self._domains[:MAX_COMPANIES_PER_PASS]

    async def health_check(self) -> dict:
        return {"source": self.source_name, "ok": True, "listings": 0,
                "note": "on-demand adapter — runs only for configured companies"}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        if not self._domains:
            result.error = "no career_companies configured (scraper key 'career_companies')"
            result.stop_reason = STOP_NO_MORE_RESULTS
            return result
        try:
            async with httpx.AsyncClient(
                    headers={"User-Agent": USER_AGENT},
                    timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                for domain in self._domains:
                    try:
                        career_url, ats = await resolve_career_page(client, domain)
                        if not career_url:
                            continue
                        if ats and adapter_for(career_url):
                            # ATS-hosted: the right ATS adapter owns this parse.
                            result.error = (f"{domain} is on {ats} — route to its "
                                            "ATS adapter (dedup via canonical source)")
                            continue
                        resp = await client.get(career_url, timeout=REQUEST_TIMEOUT)
                        if resp.status_code != 200:
                            continue
                        for job in parse_job_postings(resp.text, domain, str(resp.url)):
                            if country is not None and job.location \
                                    and not in_country(job.location, country):
                                continue
                            result.listings.append(job)
                    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
                        logger.warning("career page %s failed: %s", domain, str(e)[:120])
                        continue
        except Exception as e:  # contract: NEVER raise
            logger.exception("company_careers adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result
        result.stop_reason = STOP_NO_MORE_RESULTS
        return result


def source_spec() -> dict:
    """Registry-style metadata for reports (access: PUBLIC, opt-in)."""
    return {
        "name": SOURCE_NAME, "source_type": "COMPANY_CAREER", "tier": 1,
        "countries": ["*"], "access": Access.PUBLIC, "enabled": True,
        "notes": "JSON-LD JobPosting from configured companies' own pages; "
                 "opt-in via scraper key 'career_companies'",
    }
