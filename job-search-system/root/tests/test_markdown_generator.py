"""Cover-letter Markdown export.

Resume Markdown moved to ``app.ats_resume`` (rendered from the structured
resume) and is covered in ``tests/test_ats_resume.py``.
"""
from app.markdown_generator import generate_cover_letter_markdown


def test_generate_cover_letter_markdown():
    md = generate_cover_letter_markdown("Dear Team,\n\nI am interested.\n\nSincerely,\nBasil")
    assert md == "Dear Team,\n\nI am interested.\n\nSincerely,\nBasil\n"


def test_generate_cover_letter_markdown_repairs_mojibake():
    md = generate_cover_letter_markdown("Dear Team,\n\nâ€¢ Bullet-like line.\n")
    assert "â€¢" not in md
    assert "- Bullet-like line." in md


def test_generate_cover_letter_markdown_empty():
    assert generate_cover_letter_markdown("") == ""
    assert generate_cover_letter_markdown(None) == ""


def test_generate_cover_letter_markdown_collapses_runs_of_whitespace():
    md = generate_cover_letter_markdown("Hello   there\tfriend")
    assert md == "Hello there friend\n"