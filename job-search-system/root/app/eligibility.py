"""M5: EligibilityEngine — DETERMINISTIC gate with reason codes.

Golden Rule 4: eligibility is rules, never an LLM. Golden Rule 7: the bar is
never lowered to hit a daily target. Every rejection carries a machine-readable
reason code (analytics + debugging), and NO AI call is ever spent on an
ineligible job (cost control).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.freshness import FRESH, STALE, UNKNOWN

# Reason codes (stable strings — analytics depends on them)
R_OK = "OK"
R_DISMISSED = "DISMISSED"
R_NOT_CLASSIFIED = "LOCATION_NOT_CLASSIFIED"
R_REGION = "REGION_NOT_ALLOWED"
R_WORK_TYPE = "WORK_TYPE_NOT_ALLOWED"
R_STALE = "STALE_POSTED_DATE"
R_DATE_UNKNOWN = "POSTED_DATE_UNKNOWN"
R_NO_DESCRIPTION = "MISSING_DESCRIPTION"
R_DUPLICATE = "DUPLICATE"
R_STRATEGY_DISMISSED = "DISMISSED_BY_COUNTRY_STRATEGY"


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else R_OK


class EligibilityEngine:
    """Deterministic eligibility gate over a canonical job row (dict).

    Country strategy (M3) is injected at construction: allowed regions +
    per-country work types + salary floors. Freshness limit defaults to
    Golden Rule 10's 7 days.
    """

    def __init__(self, allowed_regions: list[str] | None = None,
                 max_age_days: int = 7,
                 min_salary_by_region: dict[str, int] | None = None,
                 require_description: bool = True):
        self.allowed_regions = {r for r in (allowed_regions or []) if r}
        self.max_age_days = max_age_days
        self.min_salary_by_region = min_salary_by_region or {}
        self.require_description = require_description

    def check(self, job: dict, freshness: dict | None = None) -> EligibilityResult:
        reasons: list[str] = []
        details: dict = {}

        if job.get("dismissed"):
            # Distinguish who dismissed: strategy auto-dismissals are reported
            # separately from user dismissals (user intent is final either way).
            code = R_STRATEGY_DISMISSED if job.get("strategy_dismissed") else R_DISMISSED
            reasons.append(code)

        if not job.get("location_classified"):
            reasons.append(R_NOT_CLASSIFIED)
        else:
            region = job.get("location_region") or ""
            details["region"] = region
            if self.allowed_regions and region not in self.allowed_regions \
                    and region != "Unknown":
                reasons.append(R_REGION)

        wt = (job.get("work_type") or "").lower()
        if wt:
            details["work_type"] = wt
            country = None
            if job.get("location_region"):
                country = self.min_salary_by_region.get(job["location_region"])
            # Country YAML may restrict work types; default allows all.
            if country and isinstance(country, dict):
                allowed_wt = country.get("work_types") or {}
                if wt in ("remote", "hybrid", "onsite") and allowed_wt.get(wt) is False:
                    reasons.append(R_WORK_TYPE)

        # Freshness — passed in pre-computed (engine stays pure) or computed here.
        if freshness is None:
            from app.freshness import assess_freshness
            freshness = assess_freshness(job.get("posted_date"),
                                         max_age_days=self.max_age_days)
        details["freshness"] = freshness
        state = freshness.get("state")
        if state == STALE:
            reasons.append(R_STALE)
        elif state == UNKNOWN:
            # DATE_UNKNOWN is never eligible for the daily target (Critical Test #3)
            reasons.append(R_DATE_UNKNOWN)

        if self.require_description and len((job.get("description") or "").strip()) < 80:
            reasons.append(R_NO_DESCRIPTION)

        sal = job.get("salary_min")
        region_key = job.get("location_region")
        floor = self.min_salary_by_region.get(region_key)
        if sal and floor and sal < floor:
            reasons.append(R_WORK_TYPE)  # salary below country floor
            details["salary_floor"] = floor

        return EligibilityResult(
            eligible=not reasons,
            reasons=reasons or [R_OK],
            details=details,
        )
