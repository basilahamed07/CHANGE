"""M4: JobSourceAdapter interface + canonical Job normalization (D-adapters).

Golden Rule 9 (adapters over vendors): every job source implements ONE
interface. Golden Rule 8: country-aware discovery is data-driven (YAML), not
per-source code.

CanonicalJob is the Phase-8 canonical field set. `content_hash` is the
CROSS-SOURCE dedup key: normalized title + company + city-level location.
Two boards posting the same job produce different URLs but the SAME
content_hash — this is what makes Critical Test #2 pass deterministically
("same job via Greenhouse + another source must NOT create two applications").
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Stop-reason telemetry (Phase 6/7)
STOP_TARGET_REACHED = "TARGET_REACHED"
STOP_NO_MORE_RESULTS = "NO_MORE_RESULTS"
STOP_SOURCES_EXHAUSTED = "SOURCES_EXHAUSTED"
STOP_RATE_LIMITED = "RATE_LIMITED"
STOP_SOURCE_FAILURE = "SOURCE_FAILURE"


def _norm(text: str) -> str:
    # Collapse whitespace BEFORE stripping — 'Senior  AI  Engineer' and
    # 'Senior AI Engineer' must hash identically (smoke test caught this).
    collapsed = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return re.sub(r"[^a-z0-9 ]", "", collapsed).strip()


def _norm_company(name: str) -> str:
    """Company legal-suffix stripping — mirrors database._normalize_company."""
    name = (name or "").lower().strip()
    for suffix in [" inc.", " inc", " llc", " ltd", " ltd.", " corp", " corporation",
                   " co.", " co", " company", " group", " gmbh", " bv", " pte",
                   " technologies", " technology"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return _norm(name)


def _city_key(location: str) -> str:
    """City-level location key: 'Berlin, Germany' and 'Berlin' match."""
    parts = [p.strip() for p in (location or "").split(",")]
    return _norm(parts[0]) if parts else ""


def make_content_hash(title: str, company: str, location: str) -> str:
    """Deterministic cross-source identity for a job posting.

    URL is deliberately EXCLUDED — the same job on two boards has two URLs
    but one identity. Empty title/company can never hash-collide with real
    jobs (guarded with a literal sentinel).
    """
    key = "|".join([
        _norm(title) or "<no-title>",
        _norm_company(company) or "<no-company>",
        _city_key(location) or "<no-location>",
    ])
    return hashlib.sha256(key.encode()).hexdigest()


@dataclass
class CanonicalJob:
    """Phase-8 canonical job model — every adapter normalizes into this."""

    title: str
    company: str
    location: str
    description: str
    url: str
    source: str                      # source_name (greenhouse/lever/ashby/…)
    source_job_id: str = ""          # provider's own id (for stable telemetry)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = ""
    posted_date: str | None = None   # ISO date (YYYY-MM-DD) or None
    employment_type: str = ""        # full_time / part_time / contract / intern
    work_type: str = ""              # remote / hybrid / onsite
    contact_email: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.title = (self.title or "").strip()
        self.company = (self.company or "").strip()
        self.location = (self.location or "").strip()
        self.description = (self.description or "").strip()
        self.url = (self.url or "").strip()
        self.posted_date = normalize_posted_date(self.posted_date)

    @property
    def content_hash(self) -> str:
        return make_content_hash(self.title, self.company, self.location)

    def is_ingestible(self) -> bool:
        """Bare minimum to enter the pipeline (dedup + classification need these)."""
        return bool(self.title and self.company and self.url)


def normalize_posted_date(value) -> str | None:
    """ISO date string or None. Accepts ISO datetimes and epoch SECONDS/MS ints.

    DELIBERATELY returns None for garbage instead of guessing (Golden Rule:
    DATE_UNKNOWN is not fresh — M5 freshness will treat None accordingly).
    """
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            ms = value > 1e11          # epoch millis vs seconds heuristic
            dt = datetime.fromtimestamp(value / 1000 if ms else value, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def parse_salary(v) -> int | None:
    """Best-effort int extraction from provider salary shapes."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return int(v) if 10_000 <= v <= 2_000_000 else None
    m = re.search(r"(\d[\d,\.]{3,})", str(v).replace(" ", ""))
    if not m:
        return None
    try:
        n = int(float(m.group(1).replace(",", "")))
    except ValueError:
        return None
    return n if 10_000 <= n <= 2_000_000 else None


@dataclass
class AdapterResult:
    """One source × one search pass, with honest telemetry."""

    source: str
    listings: list[CanonicalJob] = field(default_factory=list)
    stop_reason: str = STOP_NO_MORE_RESULTS
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.stop_reason not in (STOP_SOURCE_FAILURE, STOP_RATE_LIMITED)


class JobSourceAdapter(ABC):
    """The ONE interface every job source implements (Golden Rule 9).

    Implementations run over BaseScraper's resilience chassis (rate limits,
    retries, UA rotation) and normalize everything into CanonicalJob.
    """

    source_name: str = ""

    @abstractmethod
    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        """One discovery pass for the given role terms, optionally scoped to a
        country strategy object (M3 Country: region/aliases used for filtering).
        Must NEVER raise — return AdapterResult(stop_reason=SOURCE_FAILURE, error=…).
        """

    @abstractmethod
    async def health_check(self) -> dict:
        """Cheap reachability probe for the source's API."""
