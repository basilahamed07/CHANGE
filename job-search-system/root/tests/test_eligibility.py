"""M5: Freshness + eligibility tests.

CRITICAL TEST #3 lives here: DATE_UNKNOWN never becomes VERIFIED_FRESH and
never enters the eligible pool. Plus the full reason-code matrix.
"""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.eligibility import (
    EligibilityEngine,
    G_ALREADY_APPLIED,
    G_DATA_SANITY,
    G_FRESHNESS,
    G_JOB_STATUS,
    G_LOCATION,
    R_ALREADY_APPLIED,
    R_COUNTRY_UNKNOWN,
    R_DATE_UNKNOWN,
    R_DISMISSED,
    R_INVALID_URL,
    R_JOB_CLOSED,
    R_LOW_CONFIDENCE,
    R_MISSING_COMPANY,
    R_MISSING_TITLE,
    R_NO_DESCRIPTION,
    R_NOT_CLASSIFIED,
    R_OK,
    R_REGION,
    R_REGION_REVIEW,
    R_STALE,
    R_STRATEGY_DISMISSED,
    R_WORK_TYPE,
    STATUS_ELIGIBLE,
    STATUS_INELIGIBLE,
    STATUS_REVIEW,
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
        "work_type": "", "posted_date": (date.today() - timedelta(days=2)).isoformat(),
        # ^ relative to today: freshness is judged against the real clock, so a
        # hardcoded date goes stale as the calendar moves (found 2026-09-27).
        "salary_min": None, "url": "https://example.com/job",
        "country_code": None, "supported_countries": None,
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
                                "x" * 100, "http://x/1",
                                (date.today() - timedelta(days=1)).isoformat(),
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


# ===================================================================
# Stage-3 gate chain: status / gate / reason + evidence (task §4–§21)
# ===================================================================

@pytest.mark.asyncio
async def test_status_gate_reason_on_happy_path():
    r = EligibilityEngine(allowed_regions=["Germany"]).check(_job())
    assert r.status == STATUS_ELIGIBLE and r.gate == "FINAL_ELIGIBILITY"
    assert r.reason == R_OK and r.eligible


@pytest.mark.asyncio
async def test_dismissed_reports_gate():
    r = EligibilityEngine(allowed_regions=["Germany"]).check(_job(dismissed=1))
    assert r.status == STATUS_INELIGIBLE and r.gate == "DISMISSED"
    assert r.reason == R_DISMISSED
    r2 = EligibilityEngine(allowed_regions=["Germany"]).check(
        _job(dismissed=1, strategy_dismissed=1))
    assert r2.reason == R_STRATEGY_DISMISSED


@pytest.mark.asyncio
async def test_already_applied_hard_gate():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    for status in ("applied", "interviewing", "offered", "rejected"):
        r = eng.check(_job(), application={"status": status, "id": 7})
        assert r.status == STATUS_INELIGIBLE and r.gate == G_ALREADY_APPLIED
        assert r.reason == R_ALREADY_APPLIED
        assert r.evidence.get("application_status") == status
    # saved-only should NOT block
    for status in ("interested", "prepared"):
        r = eng.check(_job(), application={"status": status, "id": 7})
        assert r.eligible, f"{status} must not block"


@pytest.mark.asyncio
async def test_job_closed_gate():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    r = eng.check(_job(job_status="closed"))
    assert r.status == STATUS_INELIGIBLE and r.gate == G_JOB_STATUS
    assert r.reason == R_JOB_CLOSED
    past = (date.today() - timedelta(days=1)).isoformat()
    r2 = eng.check(_job(closing_date=past))
    assert r2.reason == R_JOB_CLOSED
    future = (date.today() + timedelta(days=3)).isoformat()
    assert eng.check(_job(closing_date=future)).eligible


@pytest.mark.asyncio
async def test_unknown_country_is_review_not_fabricated():
    eng = EligibilityEngine(allowed_regions=["Germany"], allowed_countries={"DE"})
    r = eng.check(_job(location_region="UNKNOWN", country_code=None,
                       classification_confidence="UNKNOWN"))
    assert r.status == STATUS_REVIEW and r.gate == G_LOCATION
    assert r.reason == R_COUNTRY_UNKNOWN and not r.eligible


@pytest.mark.asyncio
async def test_low_confidence_location_is_review():
    eng = EligibilityEngine(allowed_regions=["Germany"], allowed_countries={"DE"})
    r = eng.check(_job(location_region="Singapore", country_code="SG",
                       classification_source="SOURCE_HINT",
                       classification_confidence="LOW"))
    assert r.status == STATUS_REVIEW and r.reason == R_LOW_CONFIDENCE


@pytest.mark.asyncio
async def test_target_country_via_stage2_code():
    eng = EligibilityEngine(allowed_regions=["Germany"], allowed_countries={"DE"})
    r = eng.check(_job(location_region="Germany", country_code="DE"))
    assert r.eligible
    r2 = eng.check(_job(location_region="Poland", country_code="PL"))
    assert r2.status == STATUS_INELIGIBLE and r2.reason == R_REGION


@pytest.mark.asyncio
async def test_remote_region_buckets():
    eng = EligibilityEngine(allowed_regions=["Singapore", "Remote"],
                            allowed_countries={"SG"})
    apac = eng.check(_job(location_region="APAC", country_code=None))
    assert apac.status == STATUS_REVIEW and apac.reason == R_REGION_REVIEW
    world = eng.check(_job(location_region="GLOBAL", country_code=None))
    assert world.eligible  # worldwide remote
    # EMEA not targeted by an SG-only user → hard reject
    emea = eng.check(_job(location_region="EMEA", country_code=None))
    assert emea.status == STATUS_INELIGIBLE and emea.reason == R_REGION


@pytest.mark.asyncio
async def test_multi_location_supported_country_matches():
    eng = EligibilityEngine(allowed_regions=["UK"], allowed_countries={"GB"})
    r = eng.check(_job(location_region="Singapore", country_code="SG",
                       supported_countries='["SG", "GB"]'))
    assert r.eligible and r.details.get("matched_supported_country")


@pytest.mark.asyncio
async def test_data_sanity_missing_identity_and_bad_url():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    assert eng.check(_job(title="")).reason == R_MISSING_TITLE
    assert eng.check(_job(company="")).reason == R_MISSING_COMPANY
    r = eng.check(_job(url=None))
    assert r.status == STATUS_REVIEW and r.reason == R_INVALID_URL


@pytest.mark.asyncio
async def test_no_work_authorization_fabrication():
    """Eligibility must NOT invent a visa/work-auth verdict (task §17)."""
    r = EligibilityEngine(allowed_regions=["Germany"]).check(_job())
    for reason in r.reasons:
        assert "VISA" not in reason and "WORK_AUTH" not in reason
        assert "SPONSOR" not in reason


@pytest.mark.asyncio
async def test_eligibility_is_idempotent():
    eng = EligibilityEngine(allowed_regions=["Germany"])
    a = eng.check(_job())
    b = eng.check(_job())
    assert (a.status, a.gate, a.reason) == (b.status, b.gate, b.reason)
    assert a.reasons == b.reasons


# ===================================================================
# Quality-audit regressions (2026-10-01)
# ===================================================================

def test_salary_floor_uses_dedicated_reason():
    """A salary-floor rejection must NOT claim a work type was evaluated."""
    from app.eligibility import R_SALARY_BELOW_FLOOR
    eng = EligibilityEngine(allowed_regions=["Singapore"],
                            allowed_countries={"SG"},
                            min_salary_by_region={"Singapore": 90000})
    r = eng.check(_job(location_region="Singapore", country_code="SG",
                       salary_min=42000))
    assert r.status == STATUS_INELIGIBLE
    assert r.reason == R_SALARY_BELOW_FLOOR
    assert R_WORK_TYPE not in r.reasons
    assert r.evidence["salary_floor"] == 90000
    assert r.evidence["salary_min"] == 42000
    # at-or-above the floor passes
    assert eng.check(_job(location_region="Singapore", country_code="SG",
                          salary_min=90000)).eligible


def test_date_unknown_is_review_not_rejection():
    """DATE_UNKNOWN must never be VERIFIED_FRESH, never eligible, AND must not
    be mislabelled as a proven rejection (task §10)."""
    from app.freshness import UNKNOWN
    eng = EligibilityEngine(allowed_regions=["Germany"],
                            allowed_countries={"DE"})
    r = eng.check(_job(posted_date=None, location_region="Germany",
                       country_code="DE"))
    assert r.status == STATUS_REVIEW
    assert r.reason == R_DATE_UNKNOWN
    assert r.gate == G_FRESHNESS
    assert not r.eligible
    assert r.evidence["date_status"] == UNKNOWN


def test_date_unknown_with_hard_reason_stays_ineligible():
    """If a hard gate also fires, REVIEW loses to INELIGIBLE."""
    eng = EligibilityEngine(allowed_regions=["Germany"],
                            allowed_countries={"DE"})
    r = eng.check(_job(posted_date=None, dismissed=1,
                       location_region="Germany", country_code="DE"))
    assert r.status == STATUS_INELIGIBLE and r.reason == R_DISMISSED


@pytest.mark.asyncio
async def test_date_unknown_never_enters_scoreable(tmp_path):
    """Critical Test #3 at the SCORE contract level after the REVIEW change."""
    from app.database import Database
    from app.scheduler import run_eligibility_pass
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])
    jid = await db.insert_job("AI", "Co", "Berlin", None, None, "x" * 100,
                              "https://x/1", None, "direct", None)
    await db.set_job_classification(jid, "Germany", "DE", "HIGH", "CITY_MAP", "c")
    await run_eligibility_pass(db, registry)
    row = await db.db.execute(
        "SELECT eligibility_status, eligibility_reason FROM jobs WHERE id = ?",
        (jid,))
    status, reason = await row.fetchone()
    assert status == STATUS_REVIEW and reason == R_DATE_UNKNOWN
    assert {j["id"] for j in await db.get_scoreable_jobs()} == set()
    await db.close()


# ===================================================================
# Stage-4 SCORE contract + metrics + multi-user isolation (task §24/§28/§35)
# ===================================================================

@pytest.mark.asyncio
async def test_stage4_score_contract_blocks_ineligible(tmp_path):
    from app.database import Database
    from app.scheduler import run_eligibility_pass
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])
    fresh = (date.today() - timedelta(days=1)).isoformat()

    j_ok = await db.insert_job("AI Engineer", "Co", "Berlin, Germany", None,
                               None, "x" * 100, "https://x/1", fresh, "direct", None)
    await db.set_job_classification(j_ok, "Germany", "DE", "HIGH", "CITY_MAP", "c")
    j_stale = await db.insert_job("AI Engineer", "Co", "Berlin, Germany", None,
                                  None, "x" * 100, "https://x/2", "2020-01-01",
                                  "direct", None)
    await db.set_job_classification(j_stale, "Germany", "DE", "HIGH", "CITY_MAP", "c")
    j_us = await db.insert_job("AI Engineer", "Co", "Austin, US", None, None,
                               "x" * 100, "https://x/3", fresh, "direct", None)
    await db.set_job_classification(j_us, "US", None, "HIGH", "TEXT_LOCATION", "c")
    j_unk = await db.insert_job("AI Engineer", "Co", "?", None, None,
                                "x" * 100, "https://x/4", fresh, "direct", None)
    await db.set_job_classification(j_unk, "UNKNOWN", None, "UNKNOWN", "UNKNOWN", "e")

    evaluated = await run_eligibility_pass(db, registry)
    assert evaluated >= 4

    scoreable = {j["id"] for j in await db.get_scoreable_jobs()}
    assert j_ok in scoreable, "eligible job MUST enter SCORE"
    for jid in (j_stale, j_us, j_unk):
        assert jid not in scoreable, f"job {jid} must NOT enter SCORE"

    for jid, expected in ((j_ok, "ELIGIBLE"), (j_stale, "INELIGIBLE"),
                          (j_us, "INELIGIBLE"), (j_unk, "REVIEW_REQUIRED")):
        row = await db.db.execute(
            "SELECT eligibility_status FROM jobs WHERE id = ?", (jid,))
        assert (await row.fetchone())[0] == expected

    row = await db.db.execute("SELECT eligibility_metrics FROM search_config")
    m = json.loads((await row.fetchone())[0])
    assert m["eligible"] >= 1
    assert m["ineligible"] >= 2
    assert m["review_required"] >= 1
    assert m["by_reason"]
    await db.close()


@pytest.mark.asyncio
async def test_eligibility_pass_is_idempotent(tmp_path):
    from app.database import Database
    from app.scheduler import run_eligibility_pass
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])
    fresh = (date.today() - timedelta(days=1)).isoformat()
    jid = await db.insert_job("AI", "Co", "Berlin", None, None, "x" * 100,
                              "https://x/1", fresh, "direct", None)
    await db.set_job_classification(jid, "Germany", "DE", "HIGH", "CITY_MAP", "c")
    first = await run_eligibility_pass(db, registry)
    second = await run_eligibility_pass(db, registry)
    assert first == 1 and second == 0  # nothing re-evaluated
    await db.close()


@pytest.mark.asyncio
async def test_multiuser_eligibility_isolation(tmp_path):
    """User A's dismissal/application must not affect User B (Critical #4)."""
    from app.database import Database
    from app.scheduler import run_eligibility_pass
    from app.country_registry import CountryRegistry

    registry = CountryRegistry("config/countries").load()
    regs = registry.enabled_region_names() + ["Remote"]
    db_a = Database(str(tmp_path / "a.db"))
    db_b = Database(str(tmp_path / "b.db"))
    await db_a.init()
    await db_b.init()
    for db in (db_a, db_b):
        await db.update_allowed_regions(regs)
    fresh = (date.today() - timedelta(days=1)).isoformat()
    a = await db_a.insert_job("AI", "Co", "Berlin", None, None, "x" * 100,
                              "https://x/a", fresh, "direct", None)
    b = await db_b.insert_job("AI", "Co", "Berlin", None, None, "x" * 100,
                              "https://x/b", fresh, "direct", None)
    for db, jid in ((db_a, a), (db_b, b)):
        await db.set_job_classification(jid, "Germany", "DE", "HIGH", "CITY_MAP", "c")
    await db_a.dismiss_job(a)
    await db_a.insert_application(a, status="applied")
    await run_eligibility_pass(db_a, registry)
    await run_eligibility_pass(db_b, registry)
    assert (await db_a.get_job(a))["eligibility_status"] == "INELIGIBLE"
    assert (await db_b.get_job(b))["eligibility_status"] == "ELIGIBLE"
    await db_a.close()
    await db_b.close()
