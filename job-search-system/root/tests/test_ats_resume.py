"""ATS resume pipeline: structured schema -> Markdown -> HTML.

Covers the guarantees the resume flow depends on:
  - a structured resume renders stable, ATS-shaped Markdown
  - every rendered value is HTML-escaped (resume text is AI output, the JD is
    untrusted, so the renderer must never emit raw markup)
  - legacy plain-text resumes still render (backward compatibility)
  - the Markdown is the single source the other formats derive from
"""
import json

import pytest

from app.ats_resume import (
    build_resume_markdown,
    clean_text,
    coerce_resume_json,
    is_structured,
    parse_resume_json,
    resume_json_to_markdown,
    resume_json_to_text,
    resume_text_to_markdown,
    text_forms_for_evidence_check,
)
from app.html_renderer import markdown_to_html, render_markdown_body


STRUCTURED = {
    "basics": {
        "name": "Basil Ahamed H",
        "headline": "AI Engineer | LLM | RAG",
        "contact": {
            "location": "Chennai, India",
            "email": "basil@example.com",
            "phone": "+91 73970 61751",
            "github": "github.com/basilahamed07",
        },
    },
    "summary": "AI/ML Engineer with 2+ years building RAG systems.",
    "skills": [
        {"group": "Programming and ML", "items": ["Python", "PyTorch"]},
        {"group": "Generative AI and LLMs", "items": ["LangChain", "LangGraph"]},
    ],
    "experience": [
        {
            "title": "AI Application Developer",
            "company": "Changepond Technologies",
            "location": "Chennai",
            "dates": "May 2024 - Present",
            "bullets": ["Built a multi-agent NLP-to-SQL chatbot."],
        }
    ],
    "projects": [
        {"name": "Bug Tracking System", "stack": "Flask, JWT", "bullets": ["Solo Flask app."]}
    ],
    "education": [
        {
            "degree": "B.E. Computer Science",
            "institution": "E.G.S. Pillay Engineering College",
            "dates": "2020 - 2023",
        }
    ],
    "certifications": ["Azure AI Engineer Associate"],
    "languages": ["English", "Tamil"],
}


# ------------------------------------------------------------- parsing

def test_parse_accepts_dict_and_json_text():
    assert parse_resume_json(STRUCTURED)["basics"]["name"] == "Basil Ahamed H"
    assert parse_resume_json(json.dumps(STRUCTURED))["summary"].startswith("AI/ML")


def test_parse_recovers_fenced_json():
    raw = "```json\n" + json.dumps(STRUCTURED) + "\n```"
    assert parse_resume_json(raw)["basics"]["name"] == "Basil Ahamed H"


def test_parse_recovers_json_with_surrounding_prose():
    raw = "Here is the resume:\n" + json.dumps(STRUCTURED) + "\nHope that helps!"
    assert parse_resume_json(raw)["basics"]["name"] == "Basil Ahamed H"


def test_parse_returns_none_for_plain_text():
    assert parse_resume_json("BASIL AHAMED H\nAI Engineer") is None
    assert parse_resume_json("") is None
    assert parse_resume_json(None) is None


def test_coerce_returns_empty_for_plain_text():
    """Plain text must not be faked into a structure.

    Wrapping it would let a text-only AI response claim to be structured and
    render as a summary-only resume, silently losing every section.
    """
    assert coerce_resume_json("BASIL AHAMED H\nAI Engineer") == ""
    assert is_structured(coerce_resume_json("BASIL AHAMED H\nAI Engineer")) is False
    # The text itself still renders through the legacy path (which title-cases
    # the name line, as it always did).
    assert "# Basil Ahamed H" in build_resume_markdown("BASIL AHAMED H\nAI Engineer")


def test_text_only_ai_response_never_loses_sections():
    """Regression: a text-only payload must render the FULL resume.

    tailoring.coerce's earlier wrapper form was treated as structured, which
    emitted a resume containing only a summary.
    """
    text = ("BASIL AHAMED H\nPROFESSIONAL SUMMARY\nDid things.\n"
            "PROFESSIONAL EXPERIENCE\nEngineer | Acme | 2024\n- Shipped it.")
    coerced = coerce_resume_json(text)          # "" — not structured
    rendered = build_resume_markdown(coerced or text)
    assert "## Professional Experience" in rendered
    assert "- Shipped it." in rendered


def test_coerce_drops_provider_reasoning_noise():
    stored = coerce_resume_json({
        "basics": {"name": "Jane"}, "summary": "Real.",
        "experience": [{"title": "Dev", "bullets": ["Did things."]}],
        "reasoning_content": "thinking...",
    })
    assert "reasoning_content" not in json.loads(stored)


def test_is_structured_distinguishes_shapes():
    assert is_structured(json.dumps(STRUCTURED)) is True
    assert is_structured("plain resume text") is False


# ------------------------------------------------------------ markdown

def test_markdown_has_expected_ats_shape():
    md = resume_json_to_markdown(json.dumps(STRUCTURED))
    assert md.startswith("# Basil Ahamed H\n")
    for heading in ("## Professional Summary", "## Technical Skills",
                    "## Professional Experience", "## Projects", "## Education",
                    "## Certifications", "## Languages"):
        assert heading in md
    # Sub-headings carry the role/company line; bullets are real bullets.
    assert "### AI Application Developer \\| Changepond Technologies" in md
    assert "- Built a multi-agent NLP-to-SQL chatbot." in md


def test_markdown_is_deterministic():
    a = resume_json_to_markdown(json.dumps(STRUCTURED))
    b = resume_json_to_markdown(json.dumps(STRUCTURED))
    assert a == b


def test_markdown_front_matter_is_opt_in():
    without = resume_json_to_markdown(json.dumps(STRUCTURED))
    with_fm = resume_json_to_markdown(json.dumps(STRUCTURED), front_matter=True)
    assert "= yaml =|---" not in without
    assert with_fm.startswith("= yaml =|---\n")
    assert "name: Basil Ahamed H" in with_fm


def test_markdown_escapes_structural_characters():
    md = resume_json_to_markdown(json.dumps({
        "basics": {"name": "# Not A Heading"},
        "experience": [{"title": "Dev", "company": "A|B", "bullets": []}],
    }))
    # The name is escaped so it cannot open a heading, and the pipe in the
    # company name cannot break the role line apart.
    assert md.startswith("# \\# Not A Heading")
    assert "\\|" in md


def test_markdown_omits_empty_sections():
    md = resume_json_to_markdown(json.dumps({"basics": {"name": "Jane"}}))
    assert "## Projects" not in md
    assert "## Certifications" not in md


def test_markdown_repairs_mojibake():
    md = resume_json_to_markdown(json.dumps({
        "basics": {"name": "Jane"},
        "experience": [{"bullets": ["â€¢ Fixed things"]}],
    }))
    assert "â€¢" not in md
    assert "- Fixed things" in md


# ----------------------------------------------------------- plain text

def test_plain_text_has_no_markdown_markers():
    text = resume_json_to_text(json.dumps(STRUCTURED))
    assert "#" not in text
    assert "**" not in text
    assert "PROFESSIONAL EXPERIENCE" in text
    assert "Basil Ahamed H | AI Engineer | LLM | RAG" in text


def test_plain_text_skips_absent_sections():
    text = resume_json_to_text(json.dumps({"basics": {"name": "Jane"}}))
    assert "PROJECTS" not in text


# ------------------------------------------------------------- legacy

def test_legacy_plain_text_still_renders():
    legacy = ("BASIL AHAMED H\nAI ENGINEER | PYTHON\nPROFESSIONAL SUMMARY\n"
              "AI Engineer with RAG experience.\nTECHNICAL SKILLS\nPython, LangGraph\n"
              "- â€¢ built RAG pipelines\n")
    md = resume_text_to_markdown(legacy)
    assert md.startswith("# Basil Ahamed H")
    assert "## Professional Summary" in md
    assert "## Technical Skills" in md
    assert "â€¢" not in md
    # A mojibake bullet inside a real bullet must not render as "- - item".
    assert "- - " not in md
    assert "- built RAG pipelines" in md


def test_build_resume_markdown_picks_the_right_path():
    structured_md = build_resume_markdown(json.dumps(STRUCTURED))
    legacy_md = build_resume_markdown("JANE DOE\nSUMMARY\nDid things.")
    assert "## Technical Skills" in structured_md
    assert "## Technical Skills" not in legacy_md
    assert legacy_md.startswith("# Jane Doe")


def test_build_resume_markdown_handles_empty():
    assert build_resume_markdown("") == ""
    assert build_resume_markdown(None) == ""


def test_clean_text_never_returns_the_string_none():
    assert clean_text(None) == ""
    assert clean_text(123) == "123"


# --------------------------------------------------------- evidence gate

def test_evidence_forms_cover_the_structured_render():
    """The gate must see the text the package renders from, not only the blob.

    Otherwise a claim that exists only in resume_json would ship unverified.
    """
    forms = text_forms_for_evidence_check("Tailored resume text",
                                          json.dumps(STRUCTURED))
    assert "Tailored resume text" in forms
    assert any("Changepond Technologies" in f for f in forms)


def test_evidence_forms_dedupe_when_the_text_matches_the_structure():
    flat = resume_json_to_text(json.dumps(STRUCTURED))
    forms = text_forms_for_evidence_check(flat, json.dumps(STRUCTURED))
    assert forms == [flat]


def test_evidence_forms_ignore_unstructured_resume_json():
    forms = text_forms_for_evidence_check("Some text", "not json at all")
    assert forms == ["Some text"]


def test_evidence_forms_return_empty_when_there_is_nothing():
    assert text_forms_for_evidence_check("", "") == []


# -------------------------------------------------------------- html

def test_html_escapes_untrusted_text():
    html = render_markdown_body("# X\n\n<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_escapes_script_inside_a_bullet():
    html = render_markdown_body("# X\n\n- <img src=x onerror=alert(1)>")
    assert "<img" not in html
    assert "&lt;img" in html


def test_html_renders_headings_bullets_and_emphasis():
    html = render_markdown_body(resume_json_to_markdown(json.dumps(STRUCTURED)))
    assert '<h1 class="resume-name">Basil Ahamed H</h1>' in html
    assert "<h2>Professional Summary</h2>" in html
    assert "<h3>" in html
    assert "<li>" in html
    assert "<strong>" in html


def test_html_document_is_self_contained():
    doc = markdown_to_html(resume_json_to_markdown(json.dumps(STRUCTURED)), "Resume")
    assert doc.startswith("<!DOCTYPE html>")
    assert "<style>" in doc          # inlined, not linked
    assert "<title>Resume</title>" in doc


def test_html_escapes_the_title():
    doc = markdown_to_html("# X", '<script>bad</script>')
    assert "<script>bad</script>" not in doc


def test_html_renders_legacy_markdown_too():
    doc = markdown_to_html(resume_text_to_markdown("JANE DOE\nSUMMARY\nDid things."), "Resume")
    assert "JANE DOE" not in doc       # title-cased by the legacy renderer
    assert "Jane Doe" in doc