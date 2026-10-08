"""Prune hygiene — the cleanup must be safe by construction.

Basil (2026-10-07): "that 1002 jobs are not worth it even scraping." Discovery
over-fetches, the eligibility gate discards most of it, and the dead backlog is
then re-read by every later stage.

These tests pin the four safety rules that make a prune acceptable: it never
deletes, never touches an applied-to job, never touches ELIGIBLE or
REVIEW_REQUIRED, and does nothing at all without `confirm=true`.
"""

from __future__ import annotations

import pytest

from app.database import Database
from app.routers.discovery import _prune_candidates, apply_prune


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "prune.db"))
    await database.init()
    yield database
    await database.close()


async def _job(db: Database, tag: str, status: str, *,
               dismissed: int = 0, reason: str = "stale") -> int:
    job_id = await db.insert_job(
        f"AI Engineer {tag}", f"Acme {tag}", "Remote", None, None,
        "Build RAG systems with Python.", f"https://example.com/jobs/{tag}",
        None, None, None,
    )
    await db.db.execute(
        "UPDATE jobs SET location_classified = 1, eligibility_status = ?, "
        "dismissed = ?, eligibility_reason = ?, eligibility_gate = ? "
        "WHERE id = ?", (status, dismissed, reason, "FRESHNESS", job_id))
    await db.db.commit()
    return job_id


async def _dismissed(db: Database, job_id: int) -> int:
    cursor = await db.db.execute("SELECT dismissed FROM jobs WHERE id = ?", (job_id,))
    return (await cursor.fetchone())[0]


# --------------------------- dry run --------------------------------------

async def test_dry_run_changes_nothing(db):
    ineligible = await _job(db, "a", "INELIGIBLE")
    await _job(db, "b", "INELIGIBLE")

    result = await apply_prune(db, confirm=False)

    assert result["dry_run"] is True
    assert result["would_dismiss"] == 2
    assert "dismissed" not in result
    assert await _dismissed(db, ineligible) == 0     # untouched
    assert len(await _prune_candidates(db)) == 2     # still all candidates


# --------------------------- safety rules ---------------------------------

async def test_confirm_dismisses_only_ineligible_unapplied_jobs(db):
    eligible = await _job(db, "eligible", "ELIGIBLE")
    review = await _job(db, "review", "REVIEW_REQUIRED")
    applied = await _job(db, "applied", "INELIGIBLE")
    already = await _job(db, "already", "INELIGIBLE", dismissed=1)
    dead_a = await _job(db, "dead-a", "INELIGIBLE")
    dead_b = await _job(db, "dead-b", "INELIGIBLE")
    await db.insert_application(applied, "prepared")

    result = await apply_prune(db, confirm=True)

    assert result["dry_run"] is False
    assert result["dismissed"] == 2
    assert sorted(result["job_ids"]) == sorted([dead_a, dead_b])

    # The two dead jobs are dismissed (flagged, not deleted).
    assert await _dismissed(db, dead_a) == 1
    assert await _dismissed(db, dead_b) == 1
    # Every protected job is untouched.
    assert await _dismissed(db, eligible) == 0
    assert await _dismissed(db, review) == 0
    assert await _dismissed(db, applied) == 0     # never prune an applied job
    # Already-dismissed stays dismissed and is not re-reported as pruned.
    assert await _dismissed(db, already) == 1
    assert already not in result["job_ids"]
    # And the rows still EXIST — dismissal is not deletion.
    assert await db.get_job(dead_a) is not None


async def test_an_applied_job_is_never_a_candidate(db):
    job_id = await _job(db, "applied", "INELIGIBLE")
    assert [r["id"] for r in await _prune_candidates(db)] == [job_id]

    await db.insert_application(job_id, "prepared")
    assert await _prune_candidates(db) == []


async def test_eligible_and_review_jobs_are_never_candidates(db):
    await _job(db, "eligible", "ELIGIBLE")
    await _job(db, "review", "REVIEW_REQUIRED")
    await _job(db, "unknown", "UNKNOWN")
    assert await _prune_candidates(db) == []


async def test_limit_caps_how_much_one_prune_touches(db):
    for i in range(5):
        await _job(db, f"dead-{i}", "INELIGIBLE")

    assert len(await _prune_candidates(db, limit=3)) == 3
    result = await apply_prune(db, limit=3, confirm=True)
    assert result["dismissed"] == 3
    assert len(await _prune_candidates(db)) == 2   # the rest remain


# --------------------------- reporting ------------------------------------

async def test_summary_groups_by_eligibility_reason(db):
    await _job(db, "stale-1", "INELIGIBLE", reason="stale")
    await _job(db, "stale-2", "INELIGIBLE", reason="stale")
    await _job(db, "region", "INELIGIBLE", reason="region-not-allowed")

    result = await apply_prune(db, confirm=False)

    assert result["by_reason"] == {"stale": 2, "region-not-allowed": 1}
    assert len(result["sample"]) == 3
    assert "never touched" in result["rule"]
