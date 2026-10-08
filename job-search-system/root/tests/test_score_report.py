"""Score report — the report must be checkable, not decorative.

Basil's requirement (2026-10-07): a report of all the job scores that can be
checked properly. These tests assert the two things that makes possible: the
coverage numbers are true, and the integrity checks actually FIRE on the
defects they claim to catch (a report whose checks can never fail is worthless).
"""

from __future__ import annotations

import json

import pytest

from app.database import Database
from app.score_report import build_score_report, render_markdown, write_score_report


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "report.db"))
    await database.init()
    yield database
    await database.close()


async def _job(db: Database, tag: str = "1") -> int:
    return await db.insert_job(
        f"AI Engineer {tag}", f"Acme {tag}", "Remote", None, None,
        "Build RAG systems with Python.", f"https://example.com/jobs/{tag}",
        None, None, None,
    )


async def _set_status(db: Database, job_id: int, status: str) -> None:
    await db.db.execute(
        "UPDATE jobs SET location_classified = 1, eligibility_status = ? "
        "WHERE id = ?", (status, job_id))
    await db.db.commit()


def _check(report: dict, name: str) -> dict:
    return next(c for c in report["checks"] if c["name"] == name)


# --------------------------- coverage ------------------------------------

async def test_coverage_counts_and_decided_by_are_true(db):
    hybrid = await _job(db, "hybrid")
    both = await _job(db, "both")
    bare = await _job(db, "bare")
    outside = await _job(db, "outside")
    for jid in (hybrid, both, bare):
        await _set_status(db, jid, "ELIGIBLE")
    await _set_status(db, outside, "INELIGIBLE")

    await db.upsert_hybrid_score(hybrid, 55, [], [], [], True, {"skills": 55.0}, [])
    await db.upsert_hybrid_score(both, 60, [], [], [], True, {"skills": 60.0}, [])
    await db.insert_score(both, 88, ["strong"], [], ["python"], role_match=True)

    report = await build_score_report(db)
    cov = report["coverage"]

    assert cov["jobs_total"] == 4
    assert cov["eligible"] == 3
    assert cov["ineligible_or_review"] == 1
    assert cov["ai_scored"] == 1
    assert cov["hybrid_scored"] == 2
    assert cov["scored_any"] == 2
    # `unscored` counts EVERY job with no score, including the INELIGIBLE one —
    # it is a whole-workspace measure, not an eligible-only one.
    assert cov["unscored"] == 2
    assert cov["decided_by"] == {"ai": 1, "hybrid": 1, "unscored": 2}

    by_id = {r["job_id"]: r for r in report["jobs"]}
    # The AI score is the effective one when present.
    assert by_id[both]["decided_by"] == "ai"
    assert by_id[both]["effective_score"] == 88
    assert by_id[both]["hybrid_score"] == 60      # both kept, side by side
    assert by_id[hybrid]["decided_by"] == "hybrid"
    assert by_id[hybrid]["effective_score"] == 55
    assert by_id[bare]["decided_by"] == "unscored"
    assert by_id[bare]["effective_score"] is None


# --------------------------- integrity checks -----------------------------

async def test_eligibility_containment_fires_on_a_leaked_score(db):
    """An INELIGIBLE job carrying a score is a Stage-3 breach and must show."""
    job_id = await _job(db)
    await _set_status(db, job_id, "INELIGIBLE")
    await db.insert_score(job_id, 70, [], [], [], role_match=True)

    report = await build_score_report(db)
    leak = _check(report, "eligibility_containment")
    assert leak["ok"] is False
    assert leak["count"] == 1
    assert leak["job_ids"] == [job_id]
    assert report["all_checks_pass"] is False


async def test_hybrid_coverage_fires_when_the_free_layer_never_ran(db):
    """The exact live symptom: eligible + AI-scored, but `hybrid_score` NULL."""
    job_id = await _job(db)
    await _set_status(db, job_id, "ELIGIBLE")
    await db.insert_score(job_id, 72, [], [], [], role_match=True)

    report = await build_score_report(db)
    assert _check(report, "hybrid_coverage")["ok"] is False
    assert _check(report, "hybrid_coverage")["job_ids"] == [job_id]


async def test_no_fabricated_zeros_fires_on_a_zero_ai_score(db):
    """A stored 0 is the D1 artifact class — visible, not silently trusted."""
    job_id = await _job(db)
    await _set_status(db, job_id, "ELIGIBLE")
    await db.insert_score(job_id, 0, [], ["Missing from batch response"], [],
                          role_match=True)

    report = await build_score_report(db)
    fabricated = _check(report, "no_fabricated_zeros")
    assert fabricated["ok"] is False
    assert fabricated["job_ids"] == [job_id]


async def test_role_match_cap_fires_above_the_cap(db):
    """role_match=false with an AI score above 50 breaks the enforced cap."""
    job_id = await _job(db)
    await _set_status(db, job_id, "ELIGIBLE")
    await db.insert_score(job_id, 90, [], [], [], role_match=False)

    report = await build_score_report(db)
    assert _check(report, "role_match_cap")["ok"] is False

    # At or below the cap it must NOT fire — the check has to be precise.
    good = await _job(db, "good")
    await _set_status(db, good, "ELIGIBLE")
    await db.insert_score(good, 50, [], [], [], role_match=False)
    report2 = await build_score_report(db)
    assert _check(report2, "role_match_cap")["job_ids"] == [job_id]


async def test_a_clean_workspace_passes_every_check(db):
    """All eligible jobs hybrid-scored, nothing leaked, no zeros."""
    job_id = await _job(db)
    await _set_status(db, job_id, "ELIGIBLE")
    await db.upsert_hybrid_score(job_id, 64, ["match"], [], ["python"], True,
                                 {"skills": 64.0}, [])

    report = await build_score_report(db)
    assert report["all_checks_pass"] is True, [
        c["name"] for c in report["checks"] if not c["ok"]]


# --------------------------- artifacts ------------------------------------

async def test_markdown_and_json_artifacts_are_written(db, tmp_path):
    job_id = await _job(db)
    await _set_status(db, job_id, "ELIGIBLE")
    await db.upsert_hybrid_score(job_id, 64, ["match"], [], ["python"], True,
                                 {"skills": 64.0}, [])

    report = await build_score_report(db)
    md = render_markdown(report)
    assert "## Coverage" in md
    assert "## Integrity checks" in md
    assert "## Per-job scores" in md
    assert "`hybrid_coverage`" in md

    paths = write_score_report(report, tmp_path)
    md_file = tmp_path / "docs" / "score" / f"SCORE_REPORT_{report['generated_at'][:10]}.md"
    json_file = tmp_path / "docs" / "score" / "results" / "score_report.json"
    assert md_file.exists() and json_file.exists()
    assert paths["markdown"] == str(md_file)

    on_disk = json.loads(json_file.read_text(encoding="utf-8"))
    assert on_disk["coverage"]["eligible"] == 1
    assert on_disk["all_checks_pass"] is True


async def test_report_is_read_only(db):
    """Building the report must not create, change or clear a single score."""
    job_id = await _job(db)
    await _set_status(db, job_id, "ELIGIBLE")
    await db.upsert_hybrid_score(job_id, 41, [], [], [], True, {"skills": 41.0}, [])

    before = dict(await db.get_score(job_id))
    await build_score_report(db)
    after = dict(await db.get_score(job_id))
    assert before == after
