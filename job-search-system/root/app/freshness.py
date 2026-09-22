"""M5: Freshness verification (Golden Rule 10).

Three states, evidence-first:
- VERIFIED_FRESH: posted_date known AND within max_job_age_days (default 7).
- STALE: posted_date known AND older than the limit.
- DATE_UNKNOWN: no reliable posted_date. NOT fresh — never upgraded to
  VERIFIED_FRESH (Critical Test #3), never counted toward the daily target.

The returned evidence dict is stored on the job (audit trail: what was known,
what was computed, when).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

FRESH = "VERIFIED_FRESH"
STALE = "STALE"
UNKNOWN = "DATE_UNKNOWN"

_MAX_AGE_DAYS_DEFAULT = 7  # Golden Rule 10


def _parse_date(value) -> date | None:
    """Parse a posted_date into a date. None if unknown/garbage."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if s.isdigit():
        try:
            n = int(s)
            ms = n > 1e11
            return datetime.fromtimestamp(
                n / 1000 if ms else n, tz=timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            return None
    return None


def assess_freshness(posted_date, now: datetime | None = None,
                     max_age_days: int = _MAX_AGE_DAYS_DEFAULT) -> dict:
    """Classify a job's freshness with a machine-readable evidence record.

    Returns:
        {
          "state": VERIFIED_FRESH | STALE | DATE_UNKNOWN,
          "posted_date": "YYYY-MM-DD" | None,   # what we could establish
          "age_days": int | None,
          "max_age_days": int,
          "reason": str,
          "checked_at": ISO timestamp,
        }
    """
    now = now or datetime.now(timezone.utc)
    parsed = _parse_date(posted_date)
    evidence = {
        "posted_date": parsed.isoformat() if parsed else None,
        "max_age_days": max_age_days,
        "checked_at": now.isoformat(),
    }
    if parsed is None:
        # Critical Test #3: DATE_UNKNOWN is NEVER fresh, no matter what.
        evidence.update({"state": UNKNOWN, "age_days": None,
                         "reason": "no reliable posted_date — never treated as fresh"})
        return evidence
    age_days = (now.date() - parsed).days
    evidence["age_days"] = age_days
    if age_days < 0:
        # Future date = source clock error; treat as unknown rather than "super fresh"
        evidence.update({"state": UNKNOWN, "age_days": None,
                         "reason": f"posted_date {parsed} is in the future — unreliable"})
        return evidence
    if age_days <= max_age_days:
        evidence.update({"state": FRESH,
                         "reason": f"posted {age_days}d ago (<= {max_age_days}d limit)"})
    else:
        evidence.update({"state": STALE,
                         "reason": f"posted {age_days}d ago (> {max_age_days}d limit)"})
    return evidence
