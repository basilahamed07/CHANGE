"""M5 / Stage-3: EligibilityEngine — DETERMINISTIC gate chain with evidence.

Answers exactly one question: **should this job be allowed to proceed to
SCORE?** It evaluates factual/gating conditions (dismissed, already applied,
closed, freshness, target country, required evidence). It never scores
relevance — skill/experience/title fit belong to Stage-4 SCORE / hybrid.

Golden Rule 4: eligibility is rules, never an LLM. Golden Rule 7: the bar is
never lowered to hit a daily target. Golden Rule 10: DATE_UNKNOWN is never
treated as fresh (Critical Test #3). Every decision carries a machine-readable
gate + reason + evidence so a developer can answer "why was this rejected?"
without reading code. NO AI call is ever spent on an ineligible job.

Gate order (task §4 — deterministic, first stop wins for `gate`/`reason`):

    1. DATA_SANITY      title/company present, an actionable URL
    2. DISMISSED        user or strategy dismissal
    3. ALREADY_APPLIED  an existing submitted application
    4. JOB_STATUS       closed/expired evidence (never inferred from a scrape miss)
    5. FRESHNESS        VERIFIED_FRESH / STALE / DATE_UNKNOWN
    6. LOCATION         Stage-2 country/region vs configured targets (remote/region aware)
    7. EVIDENCE         required description / evidence available
    8. FINAL_ELIGIBILITY

Statuses: ELIGIBLE / INELIGIBLE / REVIEW_REQUIRED / UNKNOWN. HARD reasons stop
the job (INELIGIBLE); REVIEW reasons route it to human review (REVIEW_REQUIRED,
never auto-scored). UNKNOWN is reserved for a job we could not evaluate at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.freshness import FRESH, STALE, UNKNOWN

# ---------------------------------------------------------------- statuses
STATUS_ELIGIBLE = "ELIGIBLE"
STATUS_INELIGIBLE = "INELIGIBLE"
STATUS_REVIEW = "REVIEW_REQUIRED"
STATUS_UNKNOWN = "UNKNOWN"

# ---------------------------------------------------------------- gates
G_DATA_SANITY = "DATA_SANITY"
G_DISMISSED = "DISMISSED"
G_ALREADY_APPLIED = "ALREADY_APPLIED"
G_JOB_STATUS = "JOB_STATUS"
G_FRESHNESS = "FRESHNESS"
G_LOCATION = "LOCATION"
G_EVIDENCE = "EVIDENCE"
G_FINAL = "FINAL_ELIGIBILITY"
GATE_ORDER = [G_DATA_SANITY, G_DISMISSED, G_ALREADY_APPLIED, G_JOB_STATUS,
              G_FRESHNESS, G_LOCATION, G_EVIDENCE, G_FINAL]

# ---------------------------------------------------------------- reason codes
# Existing values are PRESERVED — analytics/dashboards depend on the strings.
R_OK = "OK"
R_DISMISSED = "DISMISSED"
R_STRATEGY_DISMISSED = "DISMISSED_BY_COUNTRY_STRATEGY"
R_NOT_CLASSIFIED = "LOCATION_NOT_CLASSIFIED"
R_REGION = "REGION_NOT_ALLOWED"
R_WORK_TYPE = "WORK_TYPE_NOT_ALLOWED"
R_STALE = "STALE_POSTED_DATE"
R_DATE_UNKNOWN = "POSTED_DATE_UNKNOWN"
R_NO_DESCRIPTION = "MISSING_DESCRIPTION"
R_DUPLICATE = "DUPLICATE"
# Stage-3 new codes (task §21)
R_MISSING_TITLE = "MISSING_TITLE"
R_MISSING_COMPANY = "MISSING_COMPANY"
R_INVALID_URL = "INVALID_APPLY_URL"
R_ALREADY_APPLIED = "ALREADY_APPLIED"
R_JOB_CLOSED = "JOB_CLOSED"
R_COUNTRY_UNKNOWN = "COUNTRY_UNKNOWN"
R_REGION_REVIEW = "REMOTE_REGION_REVIEW"
R_LOW_CONFIDENCE = "LOCATION_LOW_CONFIDENCE"
R_MISSING_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
R_REVIEW = "REVIEW_REQUIRED"
# Audit fix: the salary-floor gate used to report R_WORK_TYPE (a factually
# wrong reason — no work type was evaluated). A salary rejection now says so.
R_SALARY_BELOW_FLOOR = "SALARY_BELOW_FLOOR"

# reason -> gate (drives eligibility_gate + status)
REASON_GATE = {
    R_MISSING_TITLE: G_DATA_SANITY, R_MISSING_COMPANY: G_DATA_SANITY,
    R_INVALID_URL: G_DATA_SANITY,
    R_DISMISSED: G_DISMISSED, R_STRATEGY_DISMISSED: G_DISMISSED,
    R_ALREADY_APPLIED: G_ALREADY_APPLIED,
    R_JOB_CLOSED: G_JOB_STATUS,
    R_STALE: G_FRESHNESS, R_DATE_UNKNOWN: G_FRESHNESS,
    R_NOT_CLASSIFIED: G_LOCATION, R_REGION: G_LOCATION,
    R_WORK_TYPE: G_LOCATION, R_SALARY_BELOW_FLOOR: G_LOCATION,
    R_COUNTRY_UNKNOWN: G_LOCATION, R_REGION_REVIEW: G_LOCATION,
    R_LOW_CONFIDENCE: G_LOCATION,
    R_NO_DESCRIPTION: G_EVIDENCE, R_MISSING_EVIDENCE: G_EVIDENCE,
    R_OK: G_FINAL,
}

# HARD reasons → INELIGIBLE. Everything else is a REVIEW reason.
HARD_REASONS = {
    R_DISMISSED, R_STRATEGY_DISMISSED, R_ALREADY_APPLIED, R_JOB_CLOSED,
    R_STALE, R_NOT_CLASSIFIED, R_REGION, R_WORK_TYPE, R_SALARY_BELOW_FLOOR,
    R_NO_DESCRIPTION, R_MISSING_TITLE, R_MISSING_COMPANY,
}
# REVIEW reasons → REVIEW_REQUIRED (never auto-scored, never auto-rejected).
REVIEW_REASONS = {
    # DATE_UNKNOWN is deliberately REVIEW, not HARD: "we don't know the date"
    # is uncertainty, not proof of a bad job (task §10). It still never becomes
    # VERIFIED_FRESH and never enters the eligible pool (Critical Test #3).
    R_DATE_UNKNOWN, R_COUNTRY_UNKNOWN, R_REGION_REVIEW, R_LOW_CONFIDENCE,
    R_INVALID_URL, R_MISSING_EVIDENCE, R_REVIEW,
}

# Application statuses that mean "already submitted" (do not re-apply). A bare
# 'interested' save or a built-but-unsent 'prepared' package does NOT block.
APPLIED_STATUSES = {
    "applied", "interviewing", "offered", "accepted", "declined",
    "rejected", "withdrawn", "closed", "ghosted",
}
CLOSED_JOB_STATUSES = {"closed", "expired", "inactive", "filled", "removed"}

# Region buckets a remote-only job may name. A bucket a user targets in part is
# REVIEW_REQUIRED (human decides), never silently accepted or rejected.
REGION_BUCKETS = {"APAC", "EMEA", "EUROPE", "LATAM", "MENA", "NORTH_AMERICA"}
GLOBAL_REGIONS = {"GLOBAL", "WORLDWIDE", "ANYWHERE", "REMOTE"}
COUNTRY_BUCKET = {
    "SG": "APAC", "IN": "APAC", "AU": "APAC",
    "AE": "MENA",
    "DE": "EUROPE", "NL": "EUROPE", "IE": "EUROPE", "GB": "EUROPE",
    "PL": "EUROPE",
    "CA": "NORTH_AMERICA",
}
_LOW_CONFIDENCE = {"LOW", "UNKNOWN"}


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    status: str = STATUS_INELIGIBLE
    gate: str = G_FINAL
    reason: str = R_OK
    evidence: dict = field(default_factory=dict)

    @property
    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else R_OK

    @property
    def is_hard(self) -> bool:
        return self.status == STATUS_INELIGIBLE

    def to_evidence_json(self) -> str:
        return json.dumps(self.evidence, default=str)


def _today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).date()


def _is_http_url(value) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith(
        ("http://", "https://"))


def _parse_date_loose(value) -> date | None:
    from app.freshness import _parse_date
    return _parse_date(value)


class EligibilityEngine:
    """Deterministic eligibility gate chain over a canonical job row (dict).

    Country strategy (M3) is injected at construction: allowed region strings +
    allowed country ISO codes + per-region salary floors. Freshness limit
    defaults to Golden Rule 10's 7 days.
    """

    def __init__(self, allowed_regions: list[str] | None = None,
                 max_age_days: int = 7,
                 min_salary_by_region: dict[str, int] | None = None,
                 require_description: bool = True,
                 allowed_countries: set[str] | None = None):
        self.allowed_regions = {r for r in (allowed_regions or []) if r}
        self.max_age_days = max_age_days
        self.min_salary_by_region = min_salary_by_region or {}
        self.require_description = require_description
        self.allowed_countries = {c.upper() for c in (allowed_countries or set())}

    # ------------------------------------------------------------------ core
    def check(self, job: dict, freshness: dict | None = None,
              application: dict | None = None,
              now: datetime | None = None) -> EligibilityResult:
        """Evaluate one job. Pure + deterministic (given the same inputs)."""
        hard: list[str] = []       # -> INELIGIBLE
        review: list[str] = []     # -> REVIEW_REQUIRED
        details: dict = {}
        evidence: dict = {}

        # 2. DISMISSED (user intent is final; strategy dismissals reversible)
        if job.get("dismissed"):
            code = (R_STRATEGY_DISMISSED if job.get("strategy_dismissed")
                    else R_DISMISSED)
            hard.append(code)

        # 3. ALREADY_APPLIED — an existing submitted application for this job.
        app = application
        if app is None and job.get("application_status"):
            app = {"status": job.get("application_status"),
                   "id": job.get("application_id")}
        app_status = (app or {}).get("status")
        if app_status and app_status in APPLIED_STATUSES:
            hard.append(R_ALREADY_APPLIED)
            evidence["application_status"] = app_status
            if (app or {}).get("id") is not None:
                evidence["application_id"] = (app or {}).get("id")

        # 1. DATA_SANITY — actionable identity + URL. URL problems are REVIEW
        #    (fixable / may be filled later), missing identity is HARD.
        if not str(job.get("title") or "").strip():
            hard.append(R_MISSING_TITLE)
        if not str(job.get("company") or "").strip():
            hard.append(R_MISSING_COMPANY)
        raw_url = job.get("apply_url") or job.get("url")
        if not _is_http_url(raw_url):
            review.append(R_INVALID_URL)
            evidence["url"] = raw_url

        # 4. JOB_STATUS — only with positive closure evidence (never inferred
        #    from a scraper returning no results).
        status = str(job.get("job_status") or "").strip().lower()
        if status in CLOSED_JOB_STATUSES or job.get("is_closed"):
            hard.append(R_JOB_CLOSED)
            evidence["job_status"] = status or "is_closed"
        closing = _parse_date_loose(job.get("closing_date"))
        if closing is not None and closing < _today(now):
            hard.append(R_JOB_CLOSED)
            evidence["closing_date"] = closing.isoformat()

        # 5. FRESHNESS — pre-computed (engine stays pure) or computed here.
        if freshness is None:
            from app.freshness import assess_freshness
            freshness = assess_freshness(job.get("posted_date"),
                                         max_age_days=self.max_age_days)
        details["freshness"] = freshness
        evidence["posted_date"] = freshness.get("posted_date")
        evidence["date_status"] = freshness.get("state")
        state = freshness.get("state")
        if state == STALE:
            hard.append(R_STALE)
        elif state == UNKNOWN:
            # Critical Test #3: DATE_UNKNOWN is never fresh, never eligible —
            # and never FABRICATED into a rejection: uncertainty is reported as
            # REVIEW, not as proof the job is bad (task §10).
            review.append(R_DATE_UNKNOWN)

        # 6. LOCATION / COUNTRY — consume Stage-2 evidence, never re-classify.
        self._evaluate_location(job, hard, review, details, evidence)

        # 7. EVIDENCE — description (or other required evidence)
        self._evaluate_evidence(job, hard, review, evidence)

        # ---------------------------------------------------------- resolve
        if hard:
            status = STATUS_INELIGIBLE
            ordered = hard + review
        elif review:
            status = STATUS_REVIEW
            ordered = review
        else:
            status = STATUS_ELIGIBLE
            ordered = [R_OK]

        # The reported reason/gate is the one from the EARLIEST gate in the
        # documented order, so "why was this rejected?" reflects the first stop
        # (independent of the order reasons happened to be appended).
        reason = min(ordered, key=lambda r: GATE_ORDER.index(
            REASON_GATE.get(r, G_FINAL)))
        gate = REASON_GATE.get(reason, G_FINAL)
        details["hard_reasons"] = hard
        details["review_reasons"] = review
        return EligibilityResult(
            eligible=(status == STATUS_ELIGIBLE),
            reasons=ordered, details=details, status=status, gate=gate,
            reason=reason, evidence=evidence)

    # -------------------------------------------------------------- location
    def _evaluate_location(self, job, hard, review, details, evidence):
        if not job.get("location_classified"):
            hard.append(R_NOT_CLASSIFIED)
            return
        region = (job.get("location_region") or "").strip()
        details["region"] = region
        evidence["region"] = region
        country = job.get("country_code")
        if country:
            evidence["country_code"] = country
        confidence = (job.get("classification_confidence") or "").upper()
        source = (job.get("classification_source") or "").upper()
        supported = job.get("supported_countries")
        if isinstance(supported, str):
            try:
                supported = json.loads(supported)
            except (ValueError, TypeError):
                supported = None
        if supported:
            evidence["supported_countries"] = supported

        up_region = region.upper()

        # Salary floor policy (country config) — applies regardless of match.
        floor = self.min_salary_by_region.get(region)
        sal = job.get("salary_min")
        if sal and floor and sal < floor:
            hard.append(R_SALARY_BELOW_FLOOR)
            evidence["salary_floor"] = floor
            evidence["salary_min"] = sal

        # a) Target region / country exact match.
        if region and region in self.allowed_regions:
            return
        if country and country in self.allowed_countries:
            return
        # b) Multi-location: any supported country targeted?
        if supported and any(c in self.allowed_countries for c in supported):
            details["matched_supported_country"] = True
            return

        # c) Remote region bucket (APAC / EMEA / …): human decides when the
        #    user targets ANY country inside that bucket, else not targeted.
        if up_region in REGION_BUCKETS:
            targets_bucket = any(COUNTRY_BUCKET.get(c) == up_region
                                 for c in self.allowed_countries)
            if targets_bucket:
                review.append(R_REGION_REVIEW)
            else:
                hard.append(R_REGION)
            return
        # d) Worldwide / global remote → passes the country gate.
        if up_region in GLOBAL_REGIONS:
            return
        # e) Country genuinely unknown / low-confidence hint → REVIEW, never
        #    fabricate a country and never silently accept.
        if not region or up_region in ("UNKNOWN", "UNSPECIFIED"):
            review.append(R_COUNTRY_UNKNOWN)
            return
        # f) A low-confidence location that is nonetheless a configured region
        #    → REVIEW (SourceHint-only); a confident untargeted country → HARD.
        if source == "SOURCE_HINT" or confidence in _LOW_CONFIDENCE:
            review.append(R_LOW_CONFIDENCE)
            return
        hard.append(R_REGION)

    # -------------------------------------------------------------- evidence
    def _evaluate_evidence(self, job, hard, review, evidence):
        desc = (job.get("description") or "").strip()
        if self.require_description and len(desc) < 80:
            hard.append(R_NO_DESCRIPTION)
            evidence["description_length"] = len(desc)


async def build_eligibility_engine(db, registry=None,
                                   max_age_days: int = 7) -> EligibilityEngine:
    """Build an engine from live per-workspace config (allowed regions +
    registry floors / country codes). Safe when the registry is unavailable."""
    allowed = await db.get_allowed_regions()
    floors: dict = {}
    allowed_codes: set[str] = set()
    if registry is not None:
        try:
            for c in registry.enabled_countries():
                if c.region in allowed:
                    allowed_codes.add(c.code)
                if getattr(c, "salary_min", None):
                    floors[c.region] = c.salary_min
        except Exception:  # noqa: BLE001 — registry shape drift must not break gating
            pass
    return EligibilityEngine(allowed_regions=allowed, max_age_days=max_age_days,
                             min_salary_by_region=floors,
                             allowed_countries=allowed_codes)
