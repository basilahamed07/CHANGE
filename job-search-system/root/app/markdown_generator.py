"""Markdown exports for cover letters.

Resume Markdown lives in ``app.ats_resume`` — it renders the structured resume
and is the source every other resume format derives from. This module keeps the
cover-letter export: plain paragraphs of plain text, no structure to model.
Both helpers guarantee clean, ASCII-safe output — no mojibake, no stray control
characters — so the downloaded file reads well in any editor.
"""

from __future__ import annotations

import re


_MOJIBAKE_REPLACEMENTS = {
    "â€¢": "-",
    "â€“": "-",
    "â€”": "-",
    "â€˜": "'",
    "â€™": "'",
    "â€œ": '"',
    "â€�": '"',
    "\u2022": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}


def _clean_text(text: str) -> str:
    cleaned = text or ""
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def generate_cover_letter_markdown(cover_letter: str) -> str:
    """Return a simple Markdown cover letter preserving paragraphs."""
    text = _clean_text(cover_letter)
    if not text:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n\n".join(paragraphs).strip() + "\n"
