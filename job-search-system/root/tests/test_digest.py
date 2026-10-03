from datetime import datetime, timezone

import pytest
from app.database import Database
from app.digest import _render_html_digest, generate_digest


def _today() -> str:
    """UTC today — the same clock daily_outcome() reads. Never hardcode."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _eligible_job(db, score: int = 85, *, title="Senior Dev", company="Acme Corp",
                        created: str = "") -> int:
    """A scored job the gate has actually passed."""
    job_id = await db.insert_job(title, company, "Remote", 150000, 200000,
                                  "Build things", "http://acme.com/job/1", None, "url", None)
    await db.insert_score(job_id, score, ["good fit"], ["none"], ["python"])
    await db.db.execute(
        "UPDATE jobs SET eligibility_status = 'ELIGIBLE' WHERE id = ?", (job_id,))
    await db.db.commit()
    return job_id


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_generate_digest(db):
    await _eligible_job(db)

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 1
    assert "Senior Dev" in result["body"]
    assert "Acme Corp" in result["body"]
    assert result["jobs"][0]["match_score"] == 85


# ------------------------------------------------- G4: eligibility is rechecked

@pytest.mark.asyncio
async def test_an_ineligible_job_is_never_headlined(db):
    """G4: a score row outlives an eligibility flip — the digest must not lie."""
    job_id = await _eligible_job(db)
    await db.db.execute("UPDATE jobs SET eligibility_status = 'INELIGIBLE' WHERE id = ?",
                        (job_id,))
    await db.db.commit()

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 0
    assert "Senior Dev" not in result["body"]


@pytest.mark.asyncio
async def test_a_review_required_job_is_never_headlined(db):
    job_id = await _eligible_job(db)
    await db.db.execute("UPDATE jobs SET eligibility_status = 'REVIEW_REQUIRED' WHERE id = ?",
                        (job_id,))
    await db.db.commit()
    assert (await generate_digest(db, min_score=60, hours=24))["job_count"] == 0


@pytest.mark.asyncio
async def test_an_unevaluated_job_is_never_headlined(db):
    """Fail closed: unknown is not a match either."""
    job_id = await db.insert_job("Dev", "Co", "NYC", None, None, "desc",
                                  "http://x/1", None, "url", None)
    await db.insert_score(job_id, 90, ["ok"], [], [])
    assert (await generate_digest(db, min_score=60, hours=24))["job_count"] == 0


# ------------------------------------------------- G1: it is a RUN report, not a list

@pytest.mark.asyncio
async def test_digest_leads_with_the_outcome_not_a_job_count(db):
    """G1: a day that built nothing must never read as success."""
    await _eligible_job(db)

    result = await generate_digest(db, min_score=60, hours=24)

    assert "outcome" in result
    outcome = result["outcome"]
    assert outcome["daily_target"] == 5
    assert outcome["packages_created"] == 0
    assert outcome["target_met"] is False
    assert outcome["shortfall_reasons"]              # never a blank
    # The job count no longer leads — the packages-vs-target result does.
    assert "0/5 packages" in result["subject"]
    assert "packages built — TARGET MISSED" in result["body"]
    assert result["subject"].startswith("jobagent: 0/5 packages")


@pytest.mark.asyncio
async def test_shortfall_reasons_come_from_the_run_not_a_guess(db):
    await _eligible_job(db)
    await db.save_daily_run_state(_today(), {
        "run_date": _today(), "daily_target": 5, "packages_created": 1,
        "target_met": False,
        "shortfall_reasons": ["ALL_SCORED_BELOW_CUTOFF"],
        "stages": [],
    })

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["outcome"]["packages_created"] == 1
    assert result["outcome"]["shortfall_reasons"] == ["ALL_SCORED_BELOW_CUTOFF"]
    assert "ALL_SCORED_BELOW_CUTOFF" in result["subject"]
    assert "ALL_SCORED_BELOW_CUTOFF" in result["body"]


@pytest.mark.asyncio
async def test_a_met_target_reports_as_met(db):
    await _eligible_job(db)
    await db.save_daily_run_state(_today(), {
        "run_date": _today(), "daily_target": 5, "packages_created": 5,
        "target_met": True, "shortfall_reasons": ["TARGET_REACHED"],
        "stages": [],
    })

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["outcome"]["target_met"] is True
    assert result["outcome"]["shortfall_reasons"] == []
    assert "target met" in result["subject"]


def test_html_carries_the_outcome_banner():
    outcome = {"run_date": "2026-10-03", "daily_target": 5,
               "packages_created": 0, "target_met": False,
               "shortfall_reasons": ["NO_ELIGIBLE_JOBS"]}
    html = _render_html_digest([], 24, outcome)
    assert "0/5 packages built" in html
    assert "TARGET MISSED" in html
    assert "NO_ELIGIBLE_JOBS" in html
    assert "in the last 24 hours" in html          # original wording retained


def test_html_without_outcome_still_renders():
    html = _render_html_digest([], 24)
    assert "in the last 24 hours" in html
    assert "packages built" not in html


@pytest.mark.asyncio
async def test_generate_digest_empty(db):
    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 0
    assert result["jobs"] == []


@pytest.mark.asyncio
async def test_generate_digest_score_filter(db):
    job_id = await db.insert_job("Dev", "Co", "NYC", None, None,
                                  "desc", "http://x", None, "url", None)
    await db.insert_score(job_id, 40, ["ok"], [], [])

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 0  # score too low
