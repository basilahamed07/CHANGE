"""Deterministic title-relevance filter — no AI cost, runs at ingest.

Feed sources (USAJobs, BuiltIn, HackerNews, Arbeitnow) return their entire
listing feed regardless of keywords, which flooded the Jobs page with
irrelevant roles (Graphic Designer, Billing Specialist, Actuarial Director…).
Every listing now passes this gate BEFORE the database insert: if a title
matches none of the user's search terms (or the AI-role default set), it is
skipped with a counter, exactly like the region pre-filter.

This is deterministic Python doing a deterministic problem (master prompt
Phase 14) — no LLM tokens spent at scrape time.
"""

import re

from app.scrapers.defaults import JOB_TITLES as DEFAULT_JOB_TITLES

# Tokens that mark AI/ML relevance even when the exact role string differs
# (e.g. "GenAI Developer", "Applied Scientist - LLM Ops").
AI_TOKENS = (
    "ai", "a.i.", "genai", "generative", "llm", "llms", "ml", "nlp",
    "machine learning", "deep learning", "rag", "data scientist",
    "mlops", "computer vision", "agent", "agentic", "prompt",
    "backend engineer",
)

# Titles that may contain a token above but are clearly different jobs
# (e.g. "Graphic Designer" contains no AI token, but "AI Product
# Marketer" style cases are handled by requiring tech context).
BLOCKED_PATTERNS = (
    r"\bintern\b", r"\bvolunteer\b", r"\bunpaid\b",
    r"\bgraphic designer\b", r"\bactuar", r"\battorney\b",
    r"\bparalegal\b", r"\brecruit", r"\bnurse\b", r"\bclinical\b",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _word_boundary_match(text: str, phrase: str) -> bool:
    """Match a phrase with word boundaries, tolerant of separators."""
    pattern = r"\b" + re.escape(_normalize(phrase)).replace(r"\ ", r"[\s\-/]+") + r"\b"
    return re.search(pattern, text) is not None


def is_relevant_title(title: str, search_terms: list[str] | None = None) -> bool:
    """True if the title is plausibly one of the user's target roles.

    Rules (fail-closed for noise, generous for AI variants):
      1. Blocked patterns (intern, volunteer, graphic designer…) → False.
      2. Title contains any configured search term → True.
      3. Title contains an AI/ML token → True.
      4. Anything else (Billing Specialist, Foreign Attorney…) → False.
    """
    t = _normalize(title)
    if not t:
        return False

    for pat in BLOCKED_PATTERNS:
        if re.search(pat, t):
            return False

    terms = list(search_terms or [])
    if not terms:
        terms = list(DEFAULT_JOB_TITLES)
    for term in terms:
        if _word_boundary_match(t, term):
            return True

    return any(_word_boundary_match(t, tok) for tok in AI_TOKENS)
