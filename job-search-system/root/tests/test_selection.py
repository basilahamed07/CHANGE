"""Stage-6 SELECT — the selection contract.

Two defects are pinned here:

- **S3 — selection must re-check eligibility.** A score row outlives an
  eligibility flip (nothing prunes `job_scores` when a job goes stale or leaves
  the target region), so the old query — which filtered only on `dismissed` —
  would happily select and package a job the gate had since rejected.
- **S2 — selection must be deterministic.** No tie-break meant two runs over
  unchanged data could select different sets.

Also pins the surrounding contract: packaged jobs are excluded, unknown/un-
evaluated jobs are never selected (fail closed), and the cutoff is honoured.
"""

from __future__ import annotations

import pytest

from app.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "select.db"))
    await database.init()
    yield database
    await database.close()


async def _job(db: Database, tag: str, url: str | None = None) -> int:
    return await db.insert_job(
        title=f"AI Engineer {tag}",
        company=f"Acme {tag}",
        location="Remote",
        salary_min=None,
        salary_max=None,
        description="Build RAG systems with Python.",
        url=url or f"https://example.com/jobs/{tag}",
        posted_date="2026-10-01",
        application_method="direct",
        contact_email=None,
    )


async def _scored_eligible(db: Database, tag: str, score: int) -> int:
    """A job with a score row and an explicit ELIGIBLE gate result."""
    job_id = await _job(db, tag)
    await db.insert_score(job_id, score, ["strong match"], [], ["rag"])
    await db.db.execute(
        "UPDATE jobs SET eligibility_status = 'ELIGIBLE' WHERE id = ?", (job_id,))
    await db.db.commit()
    return job_id


async def _set_eligibility(db: Database, job_id: int, status: str) -> None:
    await db.db.execute(
        "UPDATE jobs SET eligibility_status = ? WHERE id = ?", (status, job_id))
    await db.db.commit()


# ------------------------------------------------------------------- S3


async def test_a_job_that_became_ineligible_is_never_selected(db):
    """THE S3 regression: a surviving score row must not outrank the gate."""
    job_id = await _scored_eligible(db, "kept", 85)
    assert [r["job_id"] for r in await db.get_top_unpackaged_jobs()] == [job_id]

    # The gate re-runs and rejects it (went stale / left the region).
    await _set_eligibility(db, job_id, "INELIGIBLE")

    assert await db.get_top_unpackaged_jobs() == []


async def test_review_required_is_never_selected(db):
    """Uncertainty is not eligibility — REVIEW_REQUIRED must not ship."""
    job_id = await _scored_eligible(db, "review", 95)
    await _set_eligibility(db, job_id, "REVIEW_REQUIRED")
    assert await db.get_top_unpackaged_jobs() == []


async def test_a_job_that_was_never_evaluated_is_never_selected(db):
    """Fail closed: eligibility_status NULL means unknown, not eligible."""
    job_id = await _job(db, "unevaluated")
    await db.insert_score(job_id, 99, ["strong match"], [], ["rag"])
    assert await db.get_top_unpackaged_jobs() == []
    await _set_eligibility(db, job_id, "ELIGIBLE")
    assert [r["job_id"] for r in await db.get_top_unpackaged_jobs()] == [job_id]


async def test_selection_mixes_statuses_by_the_gate_only(db):
    """Only the ELIGIBLE one of three scored jobs comes back."""
    eligible = await _scored_eligible(db, "yes", 70)
    ineligible = await _scored_eligible(db, "no", 99)
    await _set_eligibility(db, ineligible, "INELIGIBLE")
    late = await _job(db, "late")
    await db.insert_score(late, 99, ["strong match"], [], ["rag"])   # never evaluated

    assert [r["job_id"] for r in await db.get_top_unpackaged_jobs()] == [eligible]


# ------------------------------------------------------------------- S2


async def test_ties_break_deterministically_on_job_id(db):
    """S2: two runs over unchanged data return the identical order."""
    a = await _scored_eligible(db, "tie-a", 80)
    b = await _scored_eligible(db, "tie-b", 80)
    c = await _scored_eligible(db, "tie-c", 80)

    first = [r["job_id"] for r in await db.get_top_unpackaged_jobs(limit=10)]
    second = [r["job_id"] for r in await db.get_top_unpackaged_jobs(limit=10)]
    third = [r["job_id"] for r in await db.get_top_unpackaged_jobs(limit=10)]

    assert first == second == third
    assert first == sorted(first)          # ascending job_id within a tied score


async def test_highest_score_wins_regardless_of_id(db):
    low = await _scored_eligible(db, "low", 61)
    high = await _scored_eligible(db, "high", 92)
    assert [r["job_id"] for r in await db.get_top_unpackaged_jobs()] == [high, low]


# ----------------------------------------------------------------- framing


async def test_already_packaged_jobs_are_excluded(db):
    job_id = await _scored_eligible(db, "done", 90)
    app_id = await db.insert_application(job_id, "prepared")
    await db.set_package_meta(app_id, "/tmp/0001-acme", "fp-1", "ready_for_review")
    assert await db.get_top_unpackaged_jobs() == []


async def test_dismissed_and_strategy_dismissed_are_excluded(db):
    a = await _scored_eligible(db, "live", 70)
    b = await _scored_eligible(db, "gone", 99)
    c = await _scored_eligible(db, "strategy", 99)
    await db.db.execute("UPDATE jobs SET dismissed = 1 WHERE id = ?", (b,))
    await db.db.execute("UPDATE jobs SET strategy_dismissed = 1 WHERE id = ?", (c,))
    await db.db.commit()
    assert [r["job_id"] for r in await db.get_top_unpackaged_jobs()] == [a]


async def test_cutoff_is_respected(db):
    above = await _scored_eligible(db, "above", 60)
    await _scored_eligible(db, "below", 59)
    assert [r["job_id"] for r in await db.get_top_unpackaged_jobs(cutoff=60)] == [above]


async def test_limit_is_respected(db):
    for i in range(5):
        await _scored_eligible(db, f"n{i}", 60 + i)
    rows = await db.get_top_unpackaged_jobs(limit=2)
    assert len(rows) == 2
    assert rows[0]["match_score"] >= rows[1]["match_score"]
