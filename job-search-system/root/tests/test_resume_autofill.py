"""Resume-driven autofill: uploading a resume configures the workspace.

Covers the loop the product promises a NEW user:
    upload resume → search terms/titles/skills set → evidence profile becomes
    VERIFIED (source = the uploaded resume) → matching + generation work.

Safety assertions: DISPUTED/DO_NOT_USE claims are never touched, and an
existing explicit country choice is never overwritten.
"""

from __future__ import annotations

import io
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.evidence_autofill import extract_claims_from_resume

RESUME_TEXT = """BASIL AHAMED H
AI Engineer | basil@example.com | Berlin, Germany | github.com/basil

EXPERIENCE
Senior AI Engineer at Acme AI (2023 - Present)
Built RAG pipelines with LangChain and Azure OpenAI.

EDUCATION
MSc Computer Science - TU Berlin (2021)

SKILLS
Python, LangChain, RAG, Azure OpenAI, Docker
"""

ANALYSIS = {
    "search_terms": ["AI Engineer", "LLM Engineer"],
    "job_titles": ["AI Engineer"],
    "key_skills": ["Python", "LangChain", "RAG", "Azure OpenAI"],
    "seniority": "senior",
    "summary": "AI engineer focused on RAG systems.",
    "ats_score": 88,
    "ats_issues": [],
    "ats_tips": [],
}

PROFILE_DATA = {
    "personal": {"full_name": "Basil Ahamed H", "email": "basil@example.com",
                 "location": "Berlin, Germany", "github_url": "github.com/basil"},
    "work_history": [{"title": "Senior AI Engineer", "company": "Acme AI",
                      "start_date": "2023", "end_date": "", "current": True,
                      "description": "Built RAG pipelines with LangChain."}],
    "education": [{"degree": "MSc Computer Science", "institution": "TU Berlin",
                   "end_date": "2021"}],
    "certifications": [{"name": "Azure AI Engineer", "issuer": "Microsoft"}],
    "skills": [{"name": "Docker"}, {"name": "Python"}],
}


# ------------------------------------------------------------------ extractor

def test_extract_claims_maps_resume_sections():
    extracted = extract_claims_from_resume(ANALYSIS, PROFILE_DATA, "cv.docx")
    assert "Python" in [c["value"] for c in extracted["skills"]]
    assert "Docker" in [c["value"] for c in extracted["skills"]]
    # skills dedupe across analysis + parsed sections
    assert len([c for c in extracted["skills"] if c["value"] == "Python"]) == 1
    assert extracted["experience"][0]["value"].startswith("Senior AI Engineer at Acme AI")
    assert "TU Berlin" in extracted["education"][0]["value"]
    assert "Azure AI Engineer" in extracted["certifications"][0]["value"]
    assert any("basil@example.com" in c["value"] for c in extracted["candidate"])


def test_extract_claims_handles_empty_input():
    assert extract_claims_from_resume({}, {}, "empty.txt") == {}


# ------------------------------------------------------------------ merge

def test_merge_upgrades_unverified_and_adds_new(tmp_path):
    from app.evidence_store import EvidenceStore
    (tmp_path / "skills.yaml").write_text(
        "claims:\n"
        '  - { id: skill_python, value: "Python", status: UNVERIFIED, source: "" }\n'
        '  - { id: skill_cobol, value: "COBOL", status: DO_NOT_USE, source: "banned" }\n'
        '  - { id: skill_docker, value: "Docker", status: DISPUTED, source: "conflict" }\n'
    )
    store = EvidenceStore(profile_dir=str(tmp_path))
    counts = store.merge_extracted_claims(
        {"skills": [{"id": "skill_python", "value": "Python"},
                    {"id": "skill_rag", "value": "RAG"},
                    {"id": "skill_cobol", "value": "COBOL"},
                    {"id": "skill_docker", "value": "Docker"}]},
        "uploaded resume: cv.docx")

    assert counts["skills"] == {"added": 1, "upgraded": 1, "skipped": 2}
    by_id = {c.claim_id: c for c in store.all_claims()}
    assert by_id["skill_python"].status == "VERIFIED"
    assert by_id["skill_python"].source == "uploaded resume: cv.docx"
    assert by_id["skill_rag"].status == "VERIFIED"
    # banned + disputed claims are protected
    assert by_id["skill_cobol"].status == "DO_NOT_USE"
    assert by_id["skill_docker"].status == "DISPUTED"
    # file on disk was updated (and backed up)
    assert (tmp_path / "skills.yaml.bak").exists()
    assert "VERIFIED" in (tmp_path / "skills.yaml").read_text()


# ------------------------------------------------------------------ endpoint

@pytest.fixture
async def resume_app(tmp_path, monkeypatch):
    """Real app (guard active) with mocked AI analysis for a deterministic upload."""
    from app.main import create_app

    async def fake_analyze(client, text):
        return dict(ANALYSIS)

    async def fake_parse(client, text):
        return json.loads(json.dumps(PROFILE_DATA))

    monkeypatch.setattr("app.resume_analyzer.analyze_resume", fake_analyze)
    monkeypatch.setattr("app.resume_analyzer.parse_resume_to_profile", fake_parse)

    application = create_app(db_path=str(tmp_path / "data" / "jobagent.db"),
                             testing=False)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=ASGITransport(app=application),
                               base_url="http://test", timeout=60) as c:
            r = await c.post("/api/auth/bootstrap",
                             json={"username": "basil", "password": "admin-pass-123"})
            assert r.status_code == 200, r.text
            # an AI client must exist for the upload path to attempt analysis
            application.state.ai_client = object()
            yield application, c


@pytest.mark.asyncio
async def test_upload_autofills_settings_and_evidence(resume_app):
    app, client = resume_app
    files = {"file": ("cv.txt", io.BytesIO(RESUME_TEXT.encode()), "text/plain")}
    r = await client.post("/api/resume/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["search_terms"] == ANALYSIS["search_terms"]
    assert body["evidence_autofill"], "evidence must be autofilled from the resume"
    # Template skills arrive UNVERIFIED and get UPGRADED by the resume; new ones
    # not present in the templates are ADDED. Either way claims become VERIFIED.
    skills_counts = body["evidence_autofill"]["skills"]
    assert skills_counts["added"] + skills_counts["upgraded"] > 0

    # search config is populated (settings update themselves)
    cfg = (await client.get("/api/search-config")).json()
    assert cfg["search_terms"] == ANALYSIS["search_terms"]
    assert cfg["key_skills"]
    assert cfg.get("ats_score") == 88

    # evidence is now VERIFIED with the resume as the source
    claims = (await client.get("/api/evidence")).json()
    verified = [c for c in claims["claims"] if c["status"] == "VERIFIED"]
    assert verified, "skills from the resume must become VERIFIED evidence"
    assert any("Python" == c["value"] for c in verified)
    assert all("uploaded resume" in (c["source"] or "") for c in verified)


@pytest.mark.asyncio
async def test_upload_seeds_countries_when_user_has_none(resume_app):
    app, client = resume_app
    files = {"file": ("cv.txt", io.BytesIO(RESUME_TEXT.encode()), "text/plain")}
    r = await client.post("/api/resume/upload", files=files)
    assert r.status_code == 200
    # "Berlin, Germany" appears in the resume → Germany is pre-selected.
    assert "Germany" in r.json()["countries_seeded"]
    cfg = (await client.get("/api/search-config")).json()
    assert "Germany" in (cfg.get("allowed_regions") or [])


@pytest.mark.asyncio
async def test_upload_does_not_overwrite_explicit_country_choice(resume_app):
    app, client = resume_app
    await client.post("/api/search-config/allowed-regions",
                      json={"allowed_regions": ["Ireland"]})
    files = {"file": ("cv.txt", io.BytesIO(RESUME_TEXT.encode()), "text/plain")}
    r = await client.post("/api/resume/upload", files=files)
    assert r.status_code == 200
    assert r.json()["countries_seeded"] == []
    cfg = (await client.get("/api/search-config")).json()
    assert cfg["allowed_regions"] == ["Ireland"]
