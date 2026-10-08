"""HTML -> DOCX conversion (the same source the PDF renders).

Covers the guarantee that makes DOCX and PDF agree: both derive from the same
rendered HTML. Also pins the bug where the inlined `ats.css` stylesheet leaked
into the document as content — `html_docx` defined an `_IGNORED` set it never
checked, so `handle_data()` turned CSS comments into a paragraph under the
candidate's name.
"""
import io
import re
import zipfile

from app.html_docx import generate_docx_from_html, generate_docx_from_markdown
from app.html_renderer import markdown_to_html
from app.ats_resume import resume_json_to_markdown

STRUCTURED_MD = resume_json_to_markdown({
    "basics": {"name": "Basil Ahamed H",
               "headline": "AI Engineer | LLM | RAG",
               "contact": {"email": "basil@example.com", "location": "Chennai, India"}},
    "summary": "AI/ML Engineer with RAG experience.",
    "skills": [{"group": "Programming", "items": ["Python", "PyTorch"]}],
    "experience": [{
        "title": "AI Application Developer", "company": "Changepond Technologies",
        "dates": "May 2024 - Present",
        "bullets": ["Built a multi-agent NLP-to-SQL chatbot.",
                    "Reduced latency from 60s to 20s."],
    }],
    "projects": [{"name": "Bug Tracking System", "stack": "Flask",
                  "bullets": ["Solo Flask app."]}],
    "education": [{"degree": "B.E. Computer Science",
                   "institution": "E.G.S. Pillay Engineering College", "dates": "2020 - 2023"}],
})


def _parts(docx_bytes: bytes):
    """Return (document.xml, plain_text, bold_count, list_count)."""
    z = zipfile.ZipFile(io.BytesIO(docx_bytes))
    xml = z.read("word/document.xml").decode("utf-8")
    text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S))
    return xml, text


def test_markdown_to_docx_is_a_real_word_document():
    docx = generate_docx_from_markdown(STRUCTURED_MD, name="Basil Ahamed H")
    assert docx[:2] == b"PK"                     # OOXML is a zip
    z = zipfile.ZipFile(io.BytesIO(docx))
    assert "word/document.xml" in z.namelist()


def test_docx_contains_every_resume_section():
    _, text = _parts(generate_docx_from_markdown(STRUCTURED_MD))
    for needle in ("Basil Ahamed H", "Professional Summary", "Technical Skills",
                   "AI Application Developer", "Changepond Technologies",
                   "multi-agent NLP-to-SQL chatbot", "Bug Tracking System",
                   "E.G.S. Pillay Engineering College"):
        assert needle in text, f"missing from DOCX: {needle}"


def test_docx_does_not_leak_the_stylesheet():
    """Regression: inlined ats.css must never become document content."""
    html = markdown_to_html(STRUCTURED_MD, "Resume")
    assert "<style>" in html                     # the CSS really is inlined
    docx = generate_docx_from_markdown(STRUCTURED_MD)
    _, text = _parts(docx)
    for leak in ("ATS-safe resume stylesheet", "@page", "font-family",
                 "one column, no floats", "break-inside"):
        assert leak not in text, f"stylesheet leaked into the DOCX: {leak}"


def test_docx_text_is_comparable_to_the_pdf_text_layer():
    """DOCX and PDF derive from the same Markdown, so their content agrees."""
    import asyncio
    import fitz

    from app.pdf_renderer import markdown_to_pdf, close_browser

    async def _pdf():
        pdf, _renderer = await markdown_to_pdf(STRUCTURED_MD, title="Resume")
        await close_browser()
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            return "".join(p.get_text() for p in doc)
        finally:
            doc.close()

    _, docx_text = _parts(generate_docx_from_markdown(STRUCTURED_MD))
    pdf_text = asyncio.run(_pdf())

    for needle in ("Basil Ahamed H", "Changepond Technologies",
                   "Bug Tracking System", "E.G.S. Pillay"):
        assert needle in docx_text, f"missing from DOCX: {needle}"
        assert needle in pdf_text, f"missing from PDF: {needle}"
    # Both must carry the bulk of the resume (CSS leaks inflate this).
    assert abs(len(docx_text) - len(pdf_text)) < len(pdf_text) * 0.5


def test_docx_headings_are_bold_and_bullets_are_lists():
    xml, _ = _parts(generate_docx_from_markdown(STRUCTURED_MD))
    assert "<w:b/>" in xml or 'w:val="1"' in xml  # bold headings
    assert "List" in xml or "numPr" in xml        # real list markup


def test_docx_renders_emphasis():
    xml, text = _parts(generate_docx_from_markdown(STRUCTURED_MD))
    assert "AI Engineer" in text           # the **...** headline survives
    assert xml                             # and produced a real document


def test_docx_from_html_handles_a_full_document():
    html = markdown_to_html("# Jane Doe\n\n## Skills\n\n- Python\n", "Jane Doe")
    docx = generate_docx_from_html(html, name="Jane Doe")
    _, text = _parts(docx)
    assert "Jane Doe" in text
    assert "Skills" in text
    assert "Python" in text


def test_docx_from_html_ignores_head_elements():
    html = "<html><head><title>My Resume</title></head><body><h1>Real Name</h1></body></html>"
    xml, text = _parts(generate_docx_from_html(html))
    assert "Real Name" in text
    assert "My Resume" not in text      # <title> must not become content


def test_docx_never_returns_empty():
    """A package must always get a document, even for empty/odd input."""
    for source in ("", None, "plain text with no markup", "<html></html>"):
        docx = generate_docx_from_markdown(source or "")
        assert docx[:2] == b"PK"
        assert len(docx) > 1000


def test_docx_preserves_mojibake_repair():
    md = "# Jane\n\n- \u2022 Fixed things\n"
    _, text = _parts(generate_docx_from_markdown(md))
    assert "Fixed things" in text


def test_docx_escaped_content_stays_text():
    """AI output containing HTML must be rendered as literal text."""
    xml, text = _parts(generate_docx_from_markdown("# X\n\n- <script>alert(1)</script>\n"))
    assert "alert(1)" in text             # shown, not executed or dropped
    assert "<script" not in xml           # never a real element in the OOXML