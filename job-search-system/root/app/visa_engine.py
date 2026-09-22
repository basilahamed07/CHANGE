"""M3: Visa/sponsorship keyword engine — DETERMINISTIC (no LLM).

Golden Rule 4: deterministic code for deterministic problems. Scanning a job
description for sponsorship keywords is exact string matching, never AI.
"""

from __future__ import annotations

import re


def _regex(keywords: list[str]) -> re.Pattern | None:
    """One compiled alternation, longest-first so 'highly skilled migrant visa'
    matches before 'visa'. Word-boundary anchored on both sides."""
    if not keywords:
        return None
    parts = sorted((re.escape(k) for k in keywords), key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(" + "|".join(parts) + r")(?![a-z0-9])")


def scan_visa_mentions(text: str, keywords: list[str]) -> dict:
    """Scan text for sponsorship keywords. Machine-readable, deterministic.

    Returns:
        {
          "matched": [keyword, ...],       # which keywords appeared
          "count": int,
          "sponsors_international": bool,  # any keyword found
        }
    """
    t = (text or "").lower()
    if not t:
        return {"matched": [], "count": 0, "sponsors_international": False}
    rx = _regex(keywords)
    if not rx:
        return {"matched": [], "count": 0, "sponsors_international": False}
    found = sorted(set(m.group(1) for m in rx.finditer(t)))
    return {
        "matched": found,
        "count": len(found),
        "sponsors_international": bool(found),
    }
