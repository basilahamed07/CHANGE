"""M5: Freshness + eligibility tests.

CRITICAL TEST #3 lives here: DATE_UNKNOWN never becomes VERIFIED_FRESH and
never enters the eligible pool. Plus the full reason-code matrix.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.eligibility import (
    EligibilityEngine,
    R_DATE_UNKNOWN,
    R_DISMISSED,
    R_NO_DESCRIPTION,
    R_NOT_CLASSIFIED,
    R_OK,
    R_REGION,
    R_STALE,
    R_STRATEGY_DISMISSED,
)
from app.freshness import (
    assess_freshness,
    FRESH,
    STALE,
    UNKNOWN,
)

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def _job(**over):
    base = {
        "title": "AI Engineer", "company": "Co", "location": "Berlin, Germany",
        "description": "x" * 100, "dismissed": 0, "strategy_dismissed": 0,
        "location_classified": 1, "location_region": "Germany",
        "work_type": "", "posted_date": "2026-09-19", "salary_min": None,
    }
    base.update(over)
    return base


# ---------------- freshness (Critical Test #3) ----------------

def test_fresh_within_7_days():
    ev = assess_freshness("2026-09-19", NOW)
    assert ev["state"] == FRESH and ev["age_days"] == 3


def test_stale_beyond_7_days():
    ev = assess_freshness("2026-09-12", NOW)
    assert ev["state"] == STALE


def test_critical_3_date_unknown_never_fresh():
    """THE Critical Test #3: no reliable date can NEVER be VERIFIED_FRESH."""
    for bad in (None, "", "whenever", "31/02/2026", "not a date"):
        ev = assess_freshness(bad, NOW)
        assert ev["state"] == UNKNOWN, f"{bad!r} must be DATE_UNKNOWN"
        assert ev["state"] != FRESH


def test_critical_3_future_date_not_fresh():
    """Future posted dates are unreliable → UNKNOWN, not fresh."""
    ev = assess_freshness("2026-10-01", NOW)
    assert ev["state"] == UNKNOWN


def test_critical_3_garbage_epoch_not_fresh():
    ev = assess_freshness(999999999999999, NOW)  # absurd epoch
    assert ev["state"] == UNKNOWN


def test_freshness_evidence_is_audit_ready():
    ev = assess_freshness("2026-09-19", NOW)
    assert ev["posted_date"] == "2026-09-19"
    assert ev["checked_at"].startswith("2026-09-22")
    assert "reason" in ev and "max_age_days" in ev


# ---------------- eligibility reason matrix ----------------

@pytest.mark.asyncio
async def test_eligible_job_passes():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job())
    assert r.eligible and r.reasons == [R_OK]


@pytest.mark.asyncio
async def test_reason_region():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job(location_region="US"))
    assert not r.eligible and R_REGION in r.reasons


@pytest.mark.asyncio
async def test_reason_not_classified():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job(location_classified=0))
    assert not r.eligible and R_NOT_CLASSIFIED in r.reasons


@pytest.mark.asyncio
async def test_reason_stale_and_unknown():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job(posted_date="2026-08-01"))
    assert not r.eligible and R_STALE in r.reasons
    r = eng.check(_job(posted_date=None))
    assert not r.eligible and R_DATE_UNKNOWN in r.reasons  # Critical Test #3 at gate level


@pytest.mark.asyncio
async def test_reason_dismissed_variants():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job(dismissed=1))
    assert R_DISMISSED in r.reasons
    r = eng.check(_job(dismissed=1, strategy_dismissed=1))
    assert R_STRATEGY_DISMISSED in r.reasons


@pytest.mark.asyncio
async def test_reason_short_description():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job(description="too short"))
    assert not r.eligible and R_NO_DESCRIPTION in r.reasons


# ---------------- DB layer: repost graph + eligible query ----------------

@pytest.mark.asyncio
async def test_repost_graph_idempotent(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    a = await db.insert_job("A", "B", "C", None, None, "d", "http://x/1",
                            "2026-09-20", "direct", None)
    b = await db.insert_job("A", "B", "C", None, None, "d", "http://y/2",
                            "2026-09-20", "direct", None)
    assert await db.add_duplicate_link(a, b, "cross-source:lever") is True
    assert await db.add_duplicate_link(a, b, "cross-source:lever") is False  # idempotent
    links = await db.get_duplicate_links(a)
    assert len(links) == 1
    await db.close()


@pytest.mark.asyncio
async def test_eligible_query_excludes_unknown_and_stale(tmp_path):
    """Critical Test #3 at the DB level: DATE_UNKNOWN never in eligible pool."""
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.update_allowed_regions(["Germany", "Remote"])

    fresh = await db.insert_job("F", "Co", "Berlin, Germany", None, None,
                                "x" * 100, "http://x/1", "2026-09-20",
                                "direct", None)
    await db.set_job_location_region(fresh, "Germany")

    no_date = await db.insert_job("N", "Co", "Berlin, Germany", None, None,
                                  "x" * 100, "http://x/2", None, "direct", None)
    await db.set_job_location_region(no_date, "Germany")

    stale = await db.insert_job("S", "Co", "Berlin, Germany", None, None,
                                "x" * 100, "http://x/3", "2026-08-01",
                                "direct", None)
    await db.set_job_location_region(stale, "Germany")

    eligible = {j["id"] for j in await db.get_eligible_jobs()}
    assert fresh in eligible
    assert no_date not in eligible  # Critical Test #3
    assert stale not in eligible
    await db.close()
