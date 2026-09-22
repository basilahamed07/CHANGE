"""M2 evidence system tests: store, checker, API, and the prepare-endpoint gate.

Critical Test #1 lives here: a candidate WITHOUT skill X + a JD requesting X
must NEVER produce a resume claiming X.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.database import Database
from app.evidence_store import EvidenceStore
from app.evidence_checker import EvidenceChecker, extract_numbers


# ---------------------------------------------------------------- store
def _write_profile(tmp_path, fname, claims):
    import yaml

    p = tmp_path / fname
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"claims": claims}), encoding="utf-8")
    return p


@pytest.fixture
def store(tmp_path):
    _write_profile(tmp_path, "skills.yaml", [
        {"id": "s1", "value": "Python", "status": "VERIFIED", "source": "project"},
        {"id": "s2", "value": "Kubernetes", "status": "UNVERIFIED"},
        {"id": "s3", "value": "TensorFlow", "status": "DO_NOT_USE"},
        {"id": "s4", "value": "Puppet", "status": "DISPUTED"},
    ])
    _write_profile(tmp_path, "achievements.yaml", [
        {"id": "a1", "value": "Cut ingestion time by 40% while processing 10000 documents", "status": "VERIFIED"},
    ])
    _write_profile(tmp_path, "experience.yaml", [
        {"id": "e1", "value": "AI Engineer at Acme (2023-2025) building RAG pipelines", "status": "VERIFIED"},
    ])
    _write_profile(tmp_path, "candidate.yaml", [
        {"id": "name", "value": "Basil Ahamed H", "status": "VERIFIED"},
    ])
    s = EvidenceStore(profile_dir=str(tmp_path))
    return s


def test_store_loads_and_classifies(store):
    assert len(store.claims) == 7
    assert len(store.verified_values()) == 4
    assert [c.value for c in store.by_status("DO_NOT_USE")] == ["TensorFlow"]


def test_unverified_never_served_as_verified(store):
    """UNVERIFIED claims must never render as VERIFIED."""
    verified = {c.value for c in store.verified_only()}
    assert "Kubernetes" not in verified
    assert "TensorFlow" not in verified  # DO_NOT_USE
    assert "Puppet" not in verified      # DISPUTED


def test_invalid_status_forced_to_unverified(tmp_path):
    _write_profile(tmp_path, "skills.yaml", [
        {"id": "bad", "value": "Foo", "status": "KIND_OF_TRUE"},
    ])
    s = EvidenceStore(profile_dir=str(tmp_path))
    assert s.claims["skills:bad"].status == "UNVERIFIED"


def test_db_sync_roundtrip(store, tmp_path):
    import asyncio

    async def run():
        db = Database(str(tmp_path / "db.db"))
        await db.init()
        n = await store.sync_to_db(db)
        rows = await db.get_candidate_evidence()
        await db.close()
        return n, rows

    n, rows = asyncio.run(run())
    assert n == len(store.claims)
    statuses = {r["value"]: r["status"] for r in rows}
    assert statuses["Python"] == "VERIFIED"
    assert statuses["Kubernetes"] == "UNVERIFIED"


# ---------------------------------------------------------------- checker
@pytest.fixture
def checker(store):
    return EvidenceChecker(store.verified_values())


def test_checker_passes_truthful_resume(checker):
    ok_text = (
        "Basil Ahamed H\n"
        "AI Engineer at Acme (2023-2025) building RAG pipelines\n"
        "Cut ingestion time by 40% while processing 10000 documents\n"
        "Skills: Python\n"
    )
    result = checker.check(ok_text)
    assert result.ok, result.failures


def test_checker_blocks_unverified_skill_critical(store, checker):
    """CRITICAL TEST #1: candidate without verified skill X + JD requesting X
    => generated resume claiming X must FAIL the gate."""
    # Candidate has NO verified Kubernetes anywhere; Kubernetes is UNVERIFIED.
    hallucinated = (
        "AI Engineer at Acme (2023-2025) building RAG pipelines\n"
        "Skills: Python, Kubernetes, Terraform\n"
    )
    result = checker.check(
        hallucinated,
        candidate_skill_values=store.skill_values_all_statuses(),
    )
    assert not result.ok
    types = {f["type"] for f in result.failures}
    assert "unsupported_skill" in types
    # 'Kubernetes' explicitly named as unsupported
    skill_failure = next(f for f in result.failures if f["type"] == "unsupported_skill")
    assert "Kubernetes" in skill_failure["items"]


def test_checker_blocks_fabricated_metric(checker):
    """A metric never seen in verified evidence is fabrication."""
    bad = (
        "AI Engineer at Acme (2023-2025) building RAG pipelines\n"
        "Improved throughput by 73% and saved 1.2M dollars\n"
        "Cut ingestion time by 40% while processing 10000 documents\n"
    )
    result = checker.check(bad)
    assert not result.ok
    num_fail = next(f for f in result.failures if f["type"] == "fabricated_number")
    assert "73" in num_fail["items"]
    assert "1.2" in num_fail["items"]  # '1.2M' tokenizes as 1.2 + suffix


def test_years_not_flagged_as_metrics(checker):
    """Employment dates must not be misread as invented metrics."""
    text = "AI Engineer at Acme (2023-2025) building RAG pipelines since 2021"
    result = checker.check(text)
    assert result.ok, result.failures


def test_similarity_floor_rejects_invented_bullet(checker):
    invented = (
        "AI Engineer at Acme (2023-2025) building RAG pipelines\n"
        "Spearheaded quantum blockchain synergy across global alliances\n"
    )
    result = checker.check(invented)
    assert not result.ok
    assert any(f["type"] == "unsupported_claim" for f in result.failures)


def test_extract_numbers_ignores_years():
    assert extract_numbers("from 2021 to 2023") == set()
    assert "40" in extract_numbers("improved by 40%")


# ---------------------------------------------------------------- API
@pytest.fixture
async def evidence_app(tmp_path, store):
    from app.main import create_app
    from app.evidence_checker import EvidenceChecker

    application = create_app(db_path=str(tmp_path / "ev.db"), testing=True)
    application.state.db = Database(str(tmp_path / "ev.db"))
    await application.state.db.init()
    application.state.evidence_store = store
    application.state.evidence_checker = EvidenceChecker(store.verified_values())
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, application
    await application.state.db.close()


async def test_api_evidence_list(evidence_app):
    ac, _ = evidence_app
    r = await ac.get("/api/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["VERIFIED"] == 4
    assert body["counts"]["DO_NOT_USE"] == 1


async def test_api_evidence_check_endpoint(evidence_app):
    ac, app = evidence_app
    r = await ac.post("/api/evidence/check", json={
        "text": "AI Engineer at Acme (2023-2025) building RAG pipelines\nSkills: Python",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    r = await ac.post("/api/evidence/check", json={
        "text": "Skills: Kubernetes, TensorFlow\nNovel idea never seen before",
    })
    body = r.json()
    assert body["ok"] is False


async def test_api_evidence_reload(evidence_app, tmp_path):
    ac, app = evidence_app
    r = await ac.post("/api/evidence/reload")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ------------------------------------------- gate integration (prepare endpoint)
@pytest.mark.asyncio
async def test_prepare_blocked_by_evidence_gate(tmp_path):
    """End-to-end: AI fabricates a skill => prepare endpoint 422s and saves NOTHING."""
    from unittest.mock import AsyncMock

    from app.main import create_app

    # Profile: Python verified; Kubernetes UNVERIFIED (JD will request it).
    _write_profile(tmp_path, "skills.yaml", [
        {"id": "s1", "value": "Python", "status": "VERIFIED"},
        {"id": "s2", "value": "Kubernetes", "status": "UNVERIFIED"},
    ])
    _write_profile(tmp_path, "experience.yaml", [
        {"id": "e1", "value": "AI Engineer at Acme (2023-2025) building RAG pipelines", "status": "VERIFIED"},
    ])
    store = EvidenceStore(profile_dir=str(tmp_path))
    checker = EvidenceChecker(store.verified_values())

    fabricated = (
        "AI Engineer at Acme (2023-2025) building RAG pipelines\n"
        "Skills: Python, Kubernetes\n"
    )
    application = create_app(db_path=str(tmp_path / "g.db"), testing=True)
    db = Database(str(tmp_path / "g.db"))
    await db.init()
    application.state.db = db
    application.state.evidence_store = store
    application.state.evidence_checker = checker
    application.state.tailor = None  # guard against accidental real calls
    job_id = await db.insert_job(
        title="AI Engineer", company="Globex", location="Singapore",
        salary_min=None, salary_max=None,
        description="AI Engineer role requiring Python and Kubernetes",
        url="https://example.com/jobs/1", posted_date=None,
        application_method="direct", contact_email=None,
    )
    await db.db.execute(
        "INSERT INTO job_scores (job_id, match_score, match_reasons, concerns, "
        "suggested_keywords, scored_at) VALUES (?, 90, '', '', 'kubernetes', '')",
        (job_id,),
    )
    await db.db.commit()

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Simulate the Tailor returning a resume with the unverified skill.
        # NOTE: do NOT patch the State class — Starlette State stores instance
        # attrs in _state, so a class-level patch would shadow the assignment.
        fake_tailor = type("T", (), {})()
        fake_tailor.prepare = AsyncMock(return_value={
            "tailored_resume": fabricated, "cover_letter": "",
        })
        application.state.tailor = fake_tailor

        r = await ac.post(f"/api/jobs/{job_id}/prepare")
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "evidence_check_failed"
    types = {f["type"] for f in body["detail"]["failures"]}
    assert "unsupported_skill" in types
    # Nothing saved:
    apps = await db.get_application(job_id)
    assert apps is None
    await db.close()
