"""Score ownership — AI and hybrid scores must never erase each other.

Regression cover for the P0 defect: a manual hybrid re-score used to
`INSERT OR REPLACE` the whole `job_scores` row, destroying the AI score, and
`get_scoreable_jobs` (which required `js.id IS NULL`) then locked that job out
of AI scoring forever.

Contract: each engine owns its own score column; the shared descriptive columns
follow whichever score is *effective* (AI if present, else hybrid).
"""

from __future__ import annotations

import json

import pytest

from app.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "scores.db"))
    await database.init()
    yield database
    await database.close()


async def _job(db: Database, tag: str = "1") -> int:
    return await db.insert_job(
        f"AI Engineer {tag}", f"Acme {tag}", "Remote", None, None,
        "Build RAG systems with Python.", f"https://example.com/jobs/{tag}",
        None, None, None,
    )


async def _make_eligible(db: Database, job_id: int) -> None:
    await db.db.execute(
        "UPDATE jobs SET location_classified = 1, eligibility_status = 'ELIGIBLE' "
        "WHERE id = ?", (job_id,))
    await db.db.commit()


# ------------------------------------------------------ hybrid does not clobber AI

async def test_hybrid_after_ai_preserves_the_ai_score(db):
    """The exact P0: score AI, then hybrid, and the AI score must survive."""
    job_id = await _job(db)
    await db.insert_score(job_id, 88, ["strong match"], [], ["rag"], role_match=True,
                          model="deepseek-flash")

    await db.upsert_hybrid_score(job_id, 41, ["deterministic"], ["missing kubernetes"],
                                 ["k8s"], role_match=True,
                                 component_scores={"skills": 40.0}, hard_blockers=[])

    row = await db.get_score(job_id)
    assert row["ai_score"] == 88
    assert row["ai_model"] == "deepseek-flash"
    assert row["hybrid_score"] == 41
    # AI wins while present -> the mirror and descriptive fields stay the AI's.
    assert row["match_score"] == 88
    assert row["match_reasons"] == ["strong match"]
    # the hybrid breakdown is still recorded
    assert row["component_scores"] == {"skills": 40.0}


async def test_manual_rescore_does_not_lock_the_job_out_of_ai_scoring(db):
    """After a hybrid re-score the job must still be AI-scoreable."""
    job_id = await _job(db)
    await _make_eligible(db, job_id)
    await db.insert_score(job_id, 75, [], [], [], role_match=True)

    assert await db.get_scoreable_jobs() == []          # AI already scored

    await db.upsert_hybrid_score(job_id, 30, [], [], [], True, {"skills": 30.0}, [])
    assert await db.get_scoreable_jobs() == []          # still has an AI score

    # Clearing the AI side (a failed/removed AI score) frees it again.
    await db.clear_all_scores()
    assert [j["id"] for j in await db.get_scoreable_jobs()] == [job_id]


async def test_hybrid_scored_job_is_still_ai_scoreable(db):
    """A hybrid-only job must be returned by get_scoreable_jobs."""
    job_id = await _job(db)
    await _make_eligible(db, job_id)
    await db.upsert_hybrid_score(job_id, 55, [], [], [], True, {"skills": 55.0}, [])

    assert [j["id"] for j in await db.get_scoreable_jobs()] == [job_id]


# ------------------------------------------------------ AI does not clobber hybrid

async def test_ai_after_hybrid_preserves_the_hybrid_score(db):
    job_id = await _job(db)
    await db.upsert_hybrid_score(job_id, 62, ["hybrid reason"], ["gap"], ["k8s"],
                                 role_match=False, component_scores={"skills": 62.0},
                                 hard_blockers=["visa"])

    await db.insert_score(job_id, 91, ["ai reason"], [], ["rag"], role_match=True)

    row = await db.get_score(job_id)
    assert row["hybrid_score"] == 62
    assert row["ai_score"] == 91
    # AI now present -> AI is effective.
    assert row["match_score"] == 91
    # hybrid-only breakdown survives
    assert row["component_scores"] == {"skills": 62.0}
    assert row["hard_blockers"] == ["visa"]


# ------------------------------------------------------------------- precedence

async def test_hybrid_is_effective_until_an_ai_score_exists(db):
    job_id = await _job(db)
    await db.upsert_hybrid_score(job_id, 47, ["hybrid"], [], [], True,
                                 {"skills": 47.0}, [])
    assert (await db.get_score(job_id))["match_score"] == 47

    await db.insert_score(job_id, 83, ["ai"], [], [], role_match=True)
    assert (await db.get_score(job_id))["match_score"] == 83


async def test_later_hybrid_run_updates_hybrid_score_but_not_the_mirror(db):
    """Re-running the hybrid engine must not move the effective (AI) score."""
    job_id = await _job(db)
    await db.insert_score(job_id, 70, ["ai"], [], [], role_match=True)
    await db.upsert_hybrid_score(job_id, 20, [], [], [], True, {"skills": 20.0}, [])
    await db.upsert_hybrid_score(job_id, 65, [], [], [], True, {"skills": 65.0}, [])

    row = await db.get_score(job_id)
    assert row["hybrid_score"] == 65     # latest hybrid run recorded
    assert row["ai_score"] == 70         # AI untouched
    assert row["match_score"] == 70      # effective score still the AI's


# ------------------------------------------------------------------- migration

async def test_migration_backfills_ownership_for_legacy_rows(db, tmp_path):
    """Rows written before the split get an owner column on the next init()."""
    legacy_ai = await _job(db, "legacy-ai")
    legacy_hybrid = await _job(db, "legacy-hybrid")
    now = "2026-01-01T00:00:00+00:00"
    # AI-style legacy row: no component_scores.
    await db.db.execute(
        """INSERT INTO job_scores (job_id, match_score, match_reasons, concerns,
           suggested_keywords, scored_at, role_match)
           VALUES (?, 80, '[]', '[]', '[]', ?, 1)""", (legacy_ai, now))
    # Hybrid-style legacy row: component_scores present.
    await db.db.execute(
        """INSERT INTO job_scores (job_id, match_score, match_reasons, concerns,
           suggested_keywords, scored_at, role_match, component_scores, hard_blockers)
           VALUES (?, 33, '[]', '[]', '[]', ?, 1, ?, '[]')""",
        (legacy_hybrid, now, json.dumps({"skills": 33.0})))
    await db.db.commit()

    await db.init()  # idempotent migrations + backfill run again

    ai_row = await db.get_score(legacy_ai)
    hy_row = await db.get_score(legacy_hybrid)
    assert ai_row["ai_score"] == 80 and ai_row["hybrid_score"] is None
    assert hy_row["hybrid_score"] == 33 and hy_row["ai_score"] is None


async def test_clear_failed_scores_keeps_a_hybrid_score_but_frees_the_job(db):
    job_id = await _job(db)
    await _make_eligible(db, job_id)
    await db.upsert_hybrid_score(job_id, 44, [], [], [], True, {"skills": 44.0}, [])
    # A transient AI failure wrote score 0 with an error concern.
    await db.insert_score(job_id, 0, [], ["provider unavailable"], [], role_match=True)

    cleared = await db.clear_failed_scores()
    assert cleared == 1
    row = await db.get_score(job_id)
    assert row["ai_score"] is None
    assert row["hybrid_score"] == 44          # hybrid survived
    assert row["match_score"] == 44           # falls back to the effective hybrid
    assert [j["id"] for j in await db.get_scoreable_jobs()] == [job_id]
