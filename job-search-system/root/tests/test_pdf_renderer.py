"""PDF rendering: Markdown -> HTML -> PDF, plus the resume/cover-letter endpoints.

The Chromium path is the primary renderer; the PyMuPDF text renderer is the
fallback when no browser binary is present. Both must yield a valid PDF whose
text layer contains the resume content, so an ATS can read it either way.
"""
import json

import pytest

from app.ats_resume import resume_json_to_markdown
from app.pdf_renderer import (
    PLAYWRIGHT_AVAILABLE,
    browser_available,
    markdown_to_pdf,
)

STRUCTURED = {
    "basics": {
        "name": "Basil Ahamed H",
        "headline": "AI Engineer | LLM | RAG",
        "contact": {"location": "Chennai, India", "email": "basil@example.com"},
    },
    "summary": "AI/ML Engineer with 2+ years building RAG systems.",
    "skills": [{"group": "Programming and ML", "items": ["Python", "PyTorch"]}],
    "experience": [{
        "title": "AI Application Developer",
        "company": "Changepond Technologies",
        "dates": "May 2024 - Present",
        "bullets": ["Built a multi-agent NLP-to-SQL chatbot."],
    }],
}

MARKDOWN = resume_json_to_markdown(json.dumps(STRUCTURED))


def _pdf_text(pdf_bytes: bytes) -> str:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


# -------------------------------------------------------- unit (fallback)

async def test_markdown_to_pdf_always_produces_a_valid_pdf():
    """Both renderers must yield a real PDF — a missing browser cannot fail."""
    pdf, renderer = await markdown_to_pdf(MARKDOWN, title="Resume")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000
    assert renderer in {"chromium", "text"}


async def test_pdf_text_layer_contains_resume_content():
    """An ATS reads the text layer, so the content must survive rendering."""
    pdf, _ = await markdown_to_pdf(MARKDOWN, title="Resume")
    text = _pdf_text(pdf)
    assert "Basil Ahamed H" in text
    assert "Changepond" in text or "Changepond" in text
    assert "PROFESSIONAL EXPERIENCE" in text.upper()


async def test_pdf_is_a4_sized():
    """A4 is the Junian template's paper default (210x297mm = 595x842pt)."""
    pdf, _ = await markdown_to_pdf(MARKDOWN, title="Resume")
    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        width, height = doc[0].rect.width, doc[0].rect.height
    finally:
        doc.close()
    # A4 = 210x297mm = 595.3x841.9pt; Chromium emits 595.9x842.5, so allow a
    # point of slack rather than pinning an exact rounding.
    assert abs(width - 595.3) < 1.5 and abs(height - 841.9) < 1.5


async def test_pdf_renders_the_template_font():
    """The backbone CSS carries no font; the dynamic layer supplies Verdana."""
    pdf, _ = await markdown_to_pdf(MARKDOWN, title="Resume")
    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        fonts = {f[3] for page in doc for f in page.get_fonts()}
    finally:
        doc.close()
    assert any("Verdana" in f for f in fonts), fonts


async def test_contact_separators_survive_as_real_text():
    """Separators must be text, never CSS ::after content.

    A ``|`` that exists only in CSS is invisible to an ATS reading the text
    layer, so the generator writes them into the Markdown instead.
    """
    pdf, _ = await markdown_to_pdf(
        "# Jane Doe\n\nCity | jane@example.com | +1 555 0100\n\n## Work\n\n- Did work.\n",
        title="Resume")
    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        text = "".join(p.get_text() for p in doc)
    finally:
        doc.close()
    assert "City | jane@example.com | +1 555 0100" in text
    assert "||" not in text and "|  |" not in text


async def test_pdf_escapes_untrusted_markdown():
    """A job description is untrusted; it must not inject markup into the PDF."""
    pdf, _ = await markdown_to_pdf("# X\n\n<script>alert(1)</script>", title="X")
    assert pdf[:5] == b"%PDF-"
    assert "alert(1)" in _pdf_text(pdf)          # shown as text, not executed


async def test_browser_availability_is_a_boolean():
    assert isinstance(browser_available(), bool)
    assert isinstance(PLAYWRIGHT_AVAILABLE, bool)


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright extra not installed")
async def test_chromium_renderer_is_used_when_available():
    """When a browser is present the primary renderer must be the one chosen."""
    pdf, renderer = await markdown_to_pdf(MARKDOWN, title="Resume")
    if browser_available():
        assert renderer == "chromium"
    assert pdf[:5] == b"%PDF-"


# --------------------------------------------------------- API endpoints

@pytest.fixture
async def app(tmp_path):
    from app.database import Database
    from app.main import create_app
    application = create_app(db_path=str(tmp_path / "test.db"), testing=True)
    db = Database(str(tmp_path / "test.db"))
    await db.init()
    application.state.db = db
    yield application
    await db.close()


@pytest.fixture
async def client(app):
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _job_with_resume(db, *, resume_json: str, tailored_resume: str):
    job_id = await db.insert_job(
        title="AI Engineer", company="TestCo", location="Remote",
        salary_min=None, salary_max=None, description="Build LLM products.",
        url="https://example.com/job/1", posted_date=None,
        application_method="url", contact_email=None,
    )
    await db.insert_application(job_id)
    row = await db.get_application(job_id)
    await db.update_application(
        row["id"], tailored_resume=tailored_resume,
        cover_letter="Dear Hiring Manager,\n\nHello.\n\nSincerely,\nBasil",
        resume_json=resume_json,
    )
    return job_id


async def test_resume_md_endpoint_uses_the_structured_resume(client, app):
    job_id = await _job_with_resume(
        app.state.db, resume_json=json.dumps(STRUCTURED),
        tailored_resume="LEGACY TEXT THAT SHOULD NOT WIN",
    )
    resp = await client.get(f"/api/jobs/{job_id}/resume.md")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert resp.text.startswith("# Basil Ahamed H")
    assert "## Technical Skills" in resp.text
    assert "LEGACY TEXT" not in resp.text


async def test_resume_md_endpoint_falls_back_for_legacy_rows(client, app):
    job_id = await _job_with_resume(
        app.state.db, resume_json="",
        tailored_resume="JANE DOE\nPROFESSIONAL SUMMARY\nDid things.",
    )
    resp = await client.get(f"/api/jobs/{job_id}/resume.md")
    assert resp.status_code == 200
    assert resp.text.startswith("# Jane Doe")
    assert "## Professional Summary" in resp.text


async def test_resume_pdf_endpoint_returns_a_pdf(client, app):
    job_id = await _job_with_resume(
        app.state.db, resume_json=json.dumps(STRUCTURED),
        tailored_resume="LEGACY TEXT",
    )
    resp = await client.get(f"/api/jobs/{job_id}/resume.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert "Basil Ahamed H" in _pdf_text(resp.content)


async def test_resume_pdf_endpoint_404s_without_a_resume(client, app):
    job_id = await app.state.db.insert_job(
        title="AI Engineer", company="TestCo", location="Remote",
        salary_min=None, salary_max=None, description="A job.",
        url="https://example.com/job/2", posted_date=None,
        application_method="url", contact_email=None,
    )
    resp = await client.get(f"/api/jobs/{job_id}/resume.pdf")
    assert resp.status_code == 404


# --------------------------------------------------------- evidence gate

async def test_prepare_rejects_a_structure_with_unverified_claims(client, app, tmp_path):
    """The gate must cover resume_json, not just tailored_resume.

    A claim living only in the structure would otherwise ship unverified
    straight into resume.md/PDF/DOCX — a hole in Golden Rule 5.
    """
    from unittest.mock import AsyncMock, MagicMock

    from app.evidence_checker import EvidenceChecker
    from app.evidence_store import EvidenceStore

    job_id = await app.state.db.insert_job(
        title="AI Engineer", company="TestCo", location="Remote",
        salary_min=None, salary_max=None, description="Build LLM products.",
        url="https://example.com/job/3", posted_date=None,
        application_method="url", contact_email=None,
    )

    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "experience.yaml").write_text(
        "claims:\n"
        "  - id: r1\n"
        "    value: \"Tailored resume text\"\n"
        "    status: VERIFIED\n"
        "    source: test\n",
        encoding="utf-8",
    )
    app.state.evidence_store = EvidenceStore(profile_dir=str(profile_dir))
    app.state.evidence_checker = EvidenceChecker(
        app.state.evidence_store.verified_values()
    )

    # The plain text passes on its own; only the structure carries the claim
    # that is not in the verified corpus.
    mock_tailor = MagicMock()
    mock_tailor.prepare = AsyncMock(return_value={
        "tailored_resume": "Tailored resume text",
        "cover_letter": "Dear hiring manager",
        "resume_json": json.dumps({
            "basics": {"name": "Basil Ahamed H"},
            "summary": "Tailored resume text",
            "experience": [{
                "title": "AI Engineer",
                "company": "Madeup Corp",
                "bullets": ["Shipped an invented metric that no one verified."],
            }],
        }),
    })
    app.state.tailor = mock_tailor

    resp = await client.post(f"/api/jobs/{job_id}/prepare")
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "evidence_check_failed"

    # Nothing was saved — fail-closed, not partially applied.
    application = await app.state.db.get_application(job_id)
    assert application is None or not application.get("tailored_resume")