import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.ats_resume import is_structured
from app.tailoring import Tailor

SAMPLE_RESUME = "Senior Linux and Infrastructure Engineer with 20+ years..."

MOCK_TAILORED = {
    "tailored_resume": "Senior Infrastructure & AI Engineer with 20+ years...",
    "cover_letter": "Dear Hiring Manager,\n\nI am writing to express my interest in the Senior DevOps Engineer position...",
}


@pytest.mark.asyncio
async def test_tailor_generates_materials():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(MOCK_TAILORED))

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare(
        job_description="Senior DevOps role requiring AWS, K8s...",
        match_reasons=["Strong AWS match"],
        suggested_keywords=["kubernetes"],
    )
    assert "tailored_resume" in result
    assert "cover_letter" in result
    assert "resume_json" in result          # structured or "", never None
    assert "resume_markdown" in result
    assert result["resume_markdown"].startswith("#")
    assert len(result["cover_letter"]) > 0
    assert len(result["tailored_resume"]) > 0


@pytest.mark.asyncio
async def test_tailor_handles_error():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(side_effect=Exception("API error"))

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])
    assert result["tailored_resume"] == SAMPLE_RESUME
    assert result["cover_letter"] == ""


@pytest.mark.asyncio
async def test_tailor_handles_bad_json():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value="not valid json")

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])
    assert result["tailored_resume"] == SAMPLE_RESUME
    assert result["cover_letter"] == ""


@pytest.mark.asyncio
async def test_tailor_retries_empty_materials():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(side_effect=[
        json.dumps({"tailored_resume": "", "cover_letter": ""}),
        json.dumps(MOCK_TAILORED),
    ])

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])

    assert result["tailored_resume"] == MOCK_TAILORED["tailored_resume"]
    assert result["cover_letter"] == MOCK_TAILORED["cover_letter"]
    assert mock_client.chat.await_count == 2


STRUCTURED_TAILORED = {
    "resume_json": {
        "basics": {"name": "Jane Doe", "headline": "AI Engineer | RAG",
                   "contact": {"location": "London", "email": "j@x.com"}},
        "summary": "AI engineer with RAG experience.",
        "skills": [{"group": "ML", "items": ["Python"]}],
        "experience": [{"title": "Engineer", "company": "Acme", "dates": "2020 - 2024",
                        "bullets": ["Shipped things."]}],
    },
    "tailored_resume": "Jane Doe\nAI Engineer | RAG\nEXPERIENCE\nEngineer | Acme | 2020 - 2024\n- Shipped things.",
    "cover_letter": "Dear Hiring Manager,\n\nI am interested.",
}


def test_prompt_asks_for_the_structured_resume():
    """The structured schema is what drives the ATS Markdown/PDF renderers.

    Losing it from the prompt would silently downgrade every new resume to the
    legacy plain-text path, so pin it.
    """
    from app.tailoring import TAILORING_PROMPT
    for key in ('"resume_json"', '"resume_markdown"', '"basics"', '"experience"',
                '"skills"', '"education"', '"tailored_resume"', '"cover_letter"'):
        assert key in TAILORING_PROMPT, f"{key} missing from the tailoring prompt"
    assert "DO NOT" in TAILORING_PROMPT or "must NOT invent" in TAILORING_PROMPT
    assert "TARGET APPLICATION CONTACT / RELOCATION LINE" in TAILORING_PROMPT
    assert "TARGET COUNTRY RESUME STYLE" in TAILORING_PROMPT


@pytest.mark.asyncio
async def test_tailor_adds_country_guidance_to_prompt():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(STRUCTURED_TAILORED))
    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)

    await tailor.prepare(
        "job desc", [], [],
        target_contact_line="Chennai, India | Relocating to Singapore | j@x.com",
        target_country="Singapore",
    )

    prompt = mock_client.chat.await_args.args[0]
    assert "Singapore style" in prompt
    assert "UK English" in prompt
    assert "within two A4 pages" in prompt


def test_target_contact_line_uses_job_country():
    from app.routers.tailoring import _target_contact_line

    sg = _target_contact_line({"country_code": "SG", "location_region": "Singapore"})
    de = _target_contact_line({"country_code": "DE", "location_region": "Germany"})
    india = _target_contact_line({"country_code": "IN", "location_region": "India"})

    assert "Relocating to Singapore (work pass sponsorship required)" in sg
    assert "Relocating to Germany (work pass sponsorship required)" in de
    assert "Singapore" not in de
    assert "Open to hybrid/onsite roles in India" in india


@pytest.mark.asyncio
async def test_tailor_returns_structured_resume_when_the_model_obeys():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(STRUCTURED_TAILORED))
    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])

    assert is_structured(result["resume_json"]) is True
    assert result["resume_markdown"].startswith("# Jane Doe")
    stored = json.loads(result["resume_json"])
    assert stored["basics"]["name"] == "Jane Doe"
    assert stored["experience"][0]["company"] == "Acme"


@pytest.mark.asyncio
async def test_tailor_replaces_value_dump_markdown_with_resume_markdown():
    bad = dict(STRUCTURED_TAILORED)
    bad["resume_markdown"] = (
        "name: Jane Doe\n"
        "headline: AI Engineer\n"
        "company: Acme\n"
        "title: Engineer\n"
        "dates: 2020 - 2024\n"
    )
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(bad))
    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])

    assert result["resume_markdown"].startswith("# Jane Doe")
    assert "## Professional Experience" in result["resume_markdown"]
    assert "### Engineer \\| Acme" in result["resume_markdown"]
    assert "title:" not in result["resume_markdown"]


@pytest.mark.asyncio
async def test_tailor_forces_target_contact_line_in_markdown():
    payload = dict(STRUCTURED_TAILORED)
    payload["resume_markdown"] = (
        "# Jane Doe\n\n"
        "**AI Engineer | RAG**\n\n"
        "Chennai, India | Relocating to Singapore (work pass sponsorship required) | j@x.com\n\n"
        "## Professional Summary\n\n"
        "AI engineer with RAG experience.\n\n"
        "## Professional Experience\n\n"
        "### Engineer | Acme | 2020 - 2024\n\n"
        "- Shipped things.\n"
    )
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(payload))
    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare(
        "job desc", [], [],
        target_contact_line="Chennai, India | Relocating to Germany (work pass sponsorship required) | j@x.com",
    )

    assert "Relocating to Germany" in result["resume_markdown"]
    assert "Relocating to Singapore" not in result["resume_markdown"]


@pytest.mark.asyncio
async def test_tailor_leaves_resume_json_empty_when_the_model_gives_text_only():
    """A text-only response must not be faked into a structure.

    The structured column is then absent and the renderers fall back to the
    full plain text instead of emitting a summary-only resume.
    """
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(MOCK_TAILORED))
    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])

    assert result["resume_json"] == ""
    assert is_structured(result["resume_json"]) is False
    assert result["tailored_resume"] == MOCK_TAILORED["tailored_resume"]


@pytest.mark.asyncio
async def test_tailor_reports_empty_materials_after_retry():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps({
        "tailored_resume": "",
        "cover_letter": "",
    }))

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])

    assert result["tailored_resume"] == SAMPLE_RESUME
    assert result["cover_letter"] == ""
    assert "empty generated field" in result["error"]
