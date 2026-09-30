"""Central discovery SOURCE REGISTRY (Stage-1 DISCOVER upgrade).

One declarative place that says WHAT every discovery source is:

  * source_type   — GLOBAL_BOARD / LOCAL_BOARD / TECH_BOARD / GOVERNMENT /
                    ATS / REMOTE_BOARD / AGGREGATOR / COMPANY_CAREER /
                    SEARCH_DISCOVERY
  * tier          — 1 (direct/ATS/major local) > 2 (global/tech/gov) > 3
                    (aggregators/search) — orders the orchestrator so the
                    most authoritative sources run first (canonical-source
                    preference lives at the DB layer, §19 of the plan)
  * countries     — which country codes the source is RELEVANT for (["*"] =
                    global). Single-country sources get their code so the
                    orchestrator can skip them honestly elsewhere (same
                    behavior as the existing region_hint mechanism).
  * access        — API_KEY / PUBLIC / BLOCKED — how jobs are reachable
  * enabled       — kill-switch without deleting the registration

Design rules honored (task §13/§53):
  * EXTENDS the existing ALL_ADAPTERS list — no adapter code changes.
  * Registration names must equal adapter `source_name`s; the orchestrator
    validates this at startup (fail-loud, same discipline as country YAML).
  * Priority/tier is ORDINAL only — it never lowers the eligibility bar.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# Source types (task §13 — the taxonomy the reports are grouped by)
class SourceType:
    GLOBAL_BOARD = "GLOBAL_BOARD"
    LOCAL_BOARD = "LOCAL_BOARD"
    NICHE_BOARD = "NICHE_BOARD"
    TECH_BOARD = "TECH_BOARD"
    STARTUP_BOARD = "STARTUP_BOARD"
    GOVERNMENT = "GOVERNMENT"
    ATS = "ATS"
    COMPANY_CAREER = "COMPANY_CAREER"
    SEARCH_DISCOVERY = "SEARCH_DISCOVERY"
    REMOTE_BOARD = "REMOTE_BOARD"
    AGGREGATOR = "AGGREGATOR"


# Access classification (task §8 — honest about HOW a source is reachable)
class Access:
    PUBLIC = "PUBLIC"          # keyless API / public feed — works right now
    API_KEY = "API_KEY"        # implemented, waits on credentials →
                               # CONFIGURATION_REQUIRED until the key exists
    BLOCKED = "BLOCKED"        # automation-inappropriate (e.g. Indeed datacenter
                               # block) — documented, never fake-implemented


# Health statuses (task §21 — what one source run can honestly report)
HEALTH_PASS = "PASS"
HEALTH_PARTIAL = "PARTIAL"
HEALTH_NO_RESULTS = "NO_RESULTS"
HEALTH_CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
HEALTH_AUTH_REQUIRED = "AUTH_REQUIRED"
HEALTH_RATE_LIMITED = "RATE_LIMITED"
HEALTH_BLOCKED = "BLOCKED"
HEALTH_FAILED = "FAILED"
HEALTH_NOT_APPLICABLE = "NOT_APPLICABLE"
HEALTH_DISABLED = "DISABLED"

# Stop-reason → health mapping (one place, so telemetry and health agree)
_STOP_REASON_HEALTH = {
    "TARGET_REACHED": HEALTH_PASS,
    "NO_MORE_RESULTS": HEALTH_PASS,
    "SOURCES_EXHAUSTED": HEALTH_PASS,
    "RATE_LIMITED": HEALTH_RATE_LIMITED,
    "SOURCE_FAILURE": HEALTH_FAILED,
}


@dataclass(frozen=True)
class SourceSpec:
    """One discovery source's declarative metadata."""
    name: str                      # MUST equal the adapter's source_name
    source_type: str               # SourceType.*
    tier: int                      # 1 | 2 | 3 (1 = most authoritative)
    countries: tuple[str, ...]     # ISO codes or ("*",) for global
    access: str                    # Access.*
    enabled: bool = True
    priority: int = 0              # within-tier order (lower runs first)
    notes: str = ""


# ---------------------------------------------------------------------------
# THE REGISTRY — every name here must match an adapter source_name.
# ---------------------------------------------------------------------------
SOURCES: dict[str, SourceSpec] = {s.name: s for s in [
    # --- TIER 1: employer ATS (direct employer truth, best apply URLs) -----
    SourceSpec("greenhouse", SourceType.ATS, 1, ("*",), Access.PUBLIC,
               priority=10, notes="4 ATS boards, keyless public APIs"),
    SourceSpec("lever", SourceType.ATS, 1, ("*",), Access.PUBLIC,
               priority=11, notes="verified-live boards (spotify, palantir)"),
    SourceSpec("ashby", SourceType.ATS, 1, ("*",), Access.PUBLIC,
               priority=12, notes="linear/ramp/deel/openai boards"),
    SourceSpec("smartrecruiters", SourceType.ATS, 1, ("*",), Access.PUBLIC,
               priority=13, notes="visa/audi/bosch/siemens/sap boards"),
    SourceSpec("recruitee", SourceType.ATS, 1, ("*",), Access.PUBLIC,
               priority=14, notes="EU-heavy per-company boards"),
    # TIER 1 country majors (single-country boards with structured APIs)
    SourceSpec("mycareersfuture", SourceType.GOVERNMENT, 1, ("SG",), Access.PUBLIC,
               priority=20, notes="Singapore govt jobs portal (official)"),
    SourceSpec("arbeitnow", SourceType.LOCAL_BOARD, 1, ("DE",), Access.PUBLIC,
               priority=21, notes="Germany-native board, keyless API, 3 pages"),
    SourceSpec("reed", SourceType.LOCAL_BOARD, 1, ("GB",), Access.API_KEY,
               priority=22, notes="UK's largest board; official API — key pending"),

    # --- TIER 2: global boards, keyed metasearch, remote boards ------------
    SourceSpec("jooble", SourceType.AGGREGATOR, 2, ("*",), Access.API_KEY,
               priority=30, notes="localized boards in all 10 configured "
                                  "countries — highest-leverage keyed source"),
    SourceSpec("adzuna", SourceType.GLOBAL_BOARD, 2, ("*",), Access.API_KEY,
               priority=31, notes="per-country markets (de/nl/ie/gb/in/ca/au/pl/ae/sg)"),
    SourceSpec("wellfound", SourceType.STARTUP_BOARD, 2, ("*",), Access.PUBLIC,
               priority=32, notes="startup/AI roles (AngelList)"),
    SourceSpec("remotive", SourceType.REMOTE_BOARD, 2, ("*",), Access.PUBLIC,
               priority=33, notes="remote w/ per-country location strings"),
    SourceSpec("jobicy", SourceType.REMOTE_BOARD, 2, ("*",), Access.PUBLIC,
               priority=34, notes="remote w/ jobGeo strings"),
    SourceSpec("himalayas", SourceType.REMOTE_BOARD, 2, ("*",), Access.PUBLIC,
               priority=35, notes="remote, country-requirement field"),
    SourceSpec("workingnomads", SourceType.REMOTE_BOARD, 2, ("*",), Access.PUBLIC,
               priority=36, notes="remote API feed"),
    SourceSpec("landingjobs", SourceType.TECH_BOARD, 2, ("*",), Access.PUBLIC,
               priority=37, notes="EU tech jobs"),
    SourceSpec("builtin", SourceType.TECH_BOARD, 2, ("*",), Access.PUBLIC,
               priority=38, notes="US/Canada tech-city boards"),

    # --- TIER 3: long-tail remote/aggregator feeds -------------------------
    SourceSpec("weworkremotely", SourceType.REMOTE_BOARD, 3, ("*",), Access.PUBLIC,
               priority=40, notes="RSS; weakest geo signal"),
    SourceSpec("remoteok", SourceType.REMOTE_BOARD, 3, ("*",), Access.PUBLIC,
               priority=41, notes="remote API feed"),
    # adapter source_name is '4dayweek' (no 'four'); registry must match it.
    SourceSpec("4dayweek", SourceType.REMOTE_BOARD, 3, ("*",), Access.PUBLIC,
               priority=42, notes="4-day-week remote roles"),
]}

# Registration sanity: names here must match the orchestrator's adapter
# source_names. app.adapters imports nothing from this module (no import
# cycle); the orchestrator cross-checks both directions via validate_against.


def validate_against(adapter_names: set[str], strict: bool = True) -> None:
    """Registry consistency check (M4 discipline), tuned for real drift.

    STRICT mode (default — app startup with the FULL ALL_ADAPTERS list):
    RAISES when a registered source has no adapter — that is silent loss of
    a discovery source and must never ship.

    NON-strict mode (the orchestrator, which legitimately receives FOCUSED
    adapter subsets in tests/bounded sweeps): adapterless entries only warn,
    and unregistered adapters (test stubs) are allowed — they run LAST
    (tier 9) with a warning, so ordering stays honest without blocking tests.
    """
    registered = set(SOURCES)
    adapterless = registered - adapter_names
    if adapterless:
        message = ("Source registry mismatch — registry entries without "
                   f"adapter: {sorted(adapterless)}")
        if strict:
            raise ValueError(message)
        logger.warning("%s (focused adapter subset — ok)", message)
    unregistered = adapter_names - registered
    if unregistered:
        logger.warning("Adapters without registry entry (running last, tier 9): %s",
                       sorted(unregistered))


def get(name: str) -> SourceSpec | None:
    return SOURCES.get(name)


# Canonical-source preference (task §19): lower value wins when two sources
# describe the same opportunity — direct career page > employer ATS >
# government/official > boards > aggregator copies.
_TIER_OF_TYPE = {
    SourceType.COMPANY_CAREER: 0,   # direct employer career page
    SourceType.ATS: 1,              # employer ATS
    SourceType.GOVERNMENT: 2,       # official/public body
    SourceType.LOCAL_BOARD: 3,
    SourceType.GLOBAL_BOARD: 4,
    SourceType.TECH_BOARD: 4,
    SourceType.STARTUP_BOARD: 4,
    SourceType.REMOTE_BOARD: 4,
    SourceType.NICHE_BOARD: 4,
    SourceType.AGGREGATOR: 5,       # metasearch copies
    SourceType.SEARCH_DISCOVERY: 5,
}


def canonical_rank(source_name: str) -> int:
    """Canonical-source priority for provenance stamping (lower wins)."""
    spec = SOURCES.get(source_name)
    if spec is None:
        return 9
    return _TIER_OF_TYPE.get(spec.source_type, 9)


def adapter_order() -> list[str]:
    """Source names ordered by (tier, priority) — the orchestrator's run order."""
    return [s.name for s in sorted(SOURCES.values(),
                                   key=lambda s: (s.tier, s.priority))]


def source_for_country(country_code: str) -> list[SourceSpec]:
    """Specs relevant to one country code (global "*" + exact code match)."""
    code = (country_code or "").upper()
    return [s for s in SOURCES.values()
            if s.enabled and ("*" in s.countries or code in s.countries)]


def relevant_for(spec: SourceSpec, country_code: str) -> bool:
    code = (country_code or "").upper()
    return "*" in spec.countries or code in spec.countries


def category_counts(country_code: str | None = None) -> dict[str, int]:
    """Discovery DIVERSITY metric (task §39): enabled specs grouped by type,
    optionally scoped to one country. NOT a raw source count."""
    code = (country_code or "").upper() if country_code else None
    counts: dict[str, int] = {}
    for s in SOURCES.values():
        if not s.enabled:
            continue
        if code and not relevant_for(s, code):
            continue
        counts[s.source_type] = counts.get(s.source_type, 0) + 1
    return dict(sorted(counts.items()))


def coverage_summary(country_code: str) -> dict:
    """Per-country coverage buckets for reports (task §39)."""
    code = (country_code or "").upper()
    buckets = {
        "GLOBAL": 0, "LOCAL": 0, "TECH_STARTUP": 0, "GOVERNMENT": 0,
        "ATS": 0, "REMOTE": 0, "AGGREGATOR": 0,
    }
    for s in source_for_country(code):
        t = s.source_type
        if t == SourceType.ATS:
            buckets["ATS"] += 1
        elif t == SourceType.GOVERNMENT:
            buckets["GOVERNMENT"] += 1
        elif t in (SourceType.LOCAL_BOARD,):
            buckets["LOCAL"] += 1
        elif t in (SourceType.GLOBAL_BOARD, SourceType.NICHE_BOARD):
            buckets["GLOBAL"] += 1
        elif t in (SourceType.TECH_BOARD, SourceType.STARTUP_BOARD):
            buckets["TECH_STARTUP"] += 1
        elif t == SourceType.REMOTE_BOARD:
            buckets["REMOTE"] += 1
        else:  # AGGREGATOR, SEARCH_DISCOVERY, COMPANY_CAREER, unknown
            buckets["AGGREGATOR"] += 1
    return buckets


def coverage_status(country_code: str) -> str:
    """Factual status label (task §40): FULL / GOOD / PARTIAL / WEAK.

    GOOD = ≥3 discovery categories represented AND ≥5 enabled relevant
    sources AND ATS present. Evidence-driven — never assigned by hand.
    """
    cats = category_counts(country_code)
    n_sources = sum(cats.values())
    if n_sources >= 8 and len(cats) >= 6 and cats.get("ATS", 0) >= 3:
        return "FULL"
    if n_sources >= 5 and len(cats) >= 3 and cats.get("ATS", 0) >= 1:
        return "GOOD"
    if n_sources >= 3:
        return "PARTIAL"
    return "WEAK"


def to_dict() -> list[dict]:
    return [vars(s) | {"countries": list(s.countries)}
            for s in sorted(SOURCES.values(),
                            key=lambda s: (s.tier, s.priority))]


# ---------------------------------------------------------------------------
# Per-run source health capture (task §21)
# ---------------------------------------------------------------------------
@dataclass
class SourceRunHealth:
    """What happened when one source ran for one country (one adapter-pass)."""
    country: str
    source: str
    source_type: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    raw_jobs: int = 0
    parsed_jobs: int = 0      # normalized CanonicalJobs
    valid_jobs: int = 0       # ingested new
    duplicates: int = 0
    errors: str = ""
    status: str = HEALTH_NO_RESULTS

    def to_dict(self) -> dict:
        return vars(self)


def status_from_result(stop_reason: str, found: int, spec: SourceSpec | None,
                       has_key: bool = True) -> str:
    """Map an AdapterResult stop-reason to an honest health status."""
    if spec is not None and spec.access == Access.API_KEY and not has_key:
        return HEALTH_CONFIGURATION_REQUIRED
    status = _STOP_REASON_HEALTH.get(stop_reason, HEALTH_FAILED)
    if status == HEALTH_PASS and found == 0:
        return HEALTH_NO_RESULTS   # reachable but returned nothing this pass
    return status


def new_run_health(country: str, source: str) -> SourceRunHealth:
    spec = SOURCES.get(source)
    return SourceRunHealth(
        country=(country or "").upper(), source=source,
        source_type=spec.source_type if spec else "",
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# Structured log lines (task §48) — machine-parseable, secret-free
def log_source_start(country: str, source: str) -> None:
    logger.info("[DISCOVERY][%s][%s] START", (country or "?").upper(), source)


def log_source_end(h: SourceRunHealth) -> None:
    logger.info("[DISCOVERY][%s][%s] raw=%d parsed=%d unique=%d duration=%.1fs %s",
                h.country, h.source, h.raw_jobs, h.parsed_jobs, h.valid_jobs,
                h.duration_ms / 1000, h.status)


def log_country_summary(country: str, runs: list[SourceRunHealth],
                        duration_s: float) -> dict:
    ok = [r for r in runs if r.status == HEALTH_PASS]
    unique = sum(r.valid_jobs for r in runs)
    raw = sum(r.raw_jobs for r in runs)
    summary = {
        "country": country, "sources_attempted": len(runs),
        "sources_successful": len(ok), "raw_jobs": raw, "unique_jobs": unique,
        "duration_s": round(duration_s, 1),
        "by_status": _count_by_status(runs),
    }
    logger.info("[DISCOVERY][%s] sources=%d successful=%d raw=%d unique=%d duration=%ss",
                country, len(runs), len(ok), raw, unique,
                summary["duration_s"])
    return summary


def log_global_summary(countries: list[str], runs: list[SourceRunHealth],
                       duration_s: float) -> dict:
    ok = [r for r in runs if r.status == HEALTH_PASS]
    summary = {
        "countries": countries, "sources_attempted": len(runs),
        "sources_successful": len(ok),
        "raw_jobs": sum(r.raw_jobs for r in runs),
        "normalized_jobs": sum(r.parsed_jobs for r in runs),
        "duplicates_removed": sum(r.duplicates for r in runs),
        "unique_jobs": sum(r.valid_jobs for r in runs),
        "duration_s": round(duration_s, 1),
        "by_status": _count_by_status(runs),
    }
    logger.info("[DISCOVERY][SUMMARY] countries=%d sources_attempted=%d "
                "sources_successful=%d raw_jobs=%d normalized_jobs=%d "
                "duplicates_removed=%d unique_jobs=%d duration=%ss",
                len(countries), summary["sources_attempted"],
                summary["sources_successful"], summary["raw_jobs"],
                summary["normalized_jobs"], summary["duplicates_removed"],
                summary["unique_jobs"], summary["duration_s"])
    return summary


def _count_by_status(runs: list[SourceRunHealth]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in runs:
        counts[r.status] = counts.get(r.status, 0) + 1
    return dict(sorted(counts.items()))
