"""M7: Company research enrichment — cached rich fields (deterministic).

Extends the legacy research_company() (DDG instant answer + Glassdoor rating)
with deterministic discovery of careers URL + LinkedIn URL + AI/product clues,
all behind the companies-table cache (no re-research per job, TTL-based).

Golden Rule 4: regex/parse only — no LLM. AI interpretation can layer on top
later; the cache stores raw discovered fields.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

COMPANY_CACHE_TTL_DAYS = 30  # company facts change slowly

_CAREERS_RX = re.compile(
    r"https?://[a-z0-9.\-]*[a-z0-9\-]+\.[a-z]{2,}(/careers|/jobs|/join(?:us)?|/company/careers)\b",
    re.I)
_LINKEDIN_COMPANY_RX = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[a-z0-9\-_%]+", re.I)
AI_CLUE_RX = re.compile(
    r"\b(LLM|GenAI|generative AI|GPT|RAG|machine learning|deep learning|"
    r"computer vision|MLOps|AI[- ]first|foundation models|agents)\b", re.I)


def _domain_guess(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", (company or "").lower())
    return f"{slug}.com" if slug else ""


def extract_ai_clues(text: str) -> list[str]:
    """Deterministic AI/product signals from any company text."""
    return sorted({m.group(0).lower() for m in AI_CLUE_RX.finditer(text or "")})[:8]


def extract_links(text: str, company: str = "") -> dict:
    """Careers + LinkedIn URLs from a company page (deterministic regex)."""
    careers = _CAREERS_RX.search(text or "")
    linkedin = _LINKEDIN_COMPANY_RX.search(text or "")
    return {
        "careers_url": careers.group(0) if careers else "",
        "linkedin_url": linkedin.group(0) if linkedin else "",
    }


async def enrich_company(company_name: str, website_hint: str = "") -> dict:
    """Discover rich fields for one company. Never raises; missing fields are ''.

    Order: try website hint → domain guess. Parse home + careers pages for
    links and AI clues. Falls back to the legacy DDG description path.
    """
    info: dict = {"name": company_name, "description": "", "website": "",
                  "careers_url": "", "linkedin_url": "", "ai_clues": [],
                  "glassdoor_rating": None, "research_status": "partial"}

    # Legacy DDG instant answer (cheap, no key) for description/website
    try:
        from app.company_research import research_company
        legacy = await research_company(company_name)
        info["description"] = legacy.get("description", "")
        if legacy.get("website"):
            info["website"] = legacy["website"]
        if legacy.get("glassdoor_rating"):
            info["glassdoor_rating"] = legacy["glassdoor_rating"]
    except Exception as e:
        logger.debug("legacy company research failed for %s: %s", company_name, e)

    base = website_hint or info["website"] or f"https://{_domain_guess(company_name)}"
    if base and base.startswith("http"):
        info["website"] = info["website"] or base
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; jobagent/1.0)"}
            async with httpx.AsyncClient(timeout=12.0, headers=headers,
                                         follow_redirects=True) as client:
                resp = await client.get(base)
                if resp.status_code == 200:
                    text = resp.text
                    links = extract_links(text, company_name)
                    info["careers_url"] = links["careers_url"]
                    info["linkedin_url"] = links["linkedin_url"]
                    info["ai_clues"] = extract_ai_clues(re.sub(r"<[^>]+>", " ", text))
                    if info["careers_url"]:
                        info["research_status"] = "complete"
        except Exception as e:
            logger.debug("company page fetch failed for %s: %s", base, e)

    if not (info["careers_url"] or info["linkedin_url"] or info["description"]
            or info["ai_clues"]):
        info["research_status"] = "not_found"
    return info


def company_cache_fresh(row: dict) -> bool:
    """True if the cached company row is within the TTL."""
    try:
        ts = datetime.fromisoformat(str(row.get("researched_at")).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - ts < timedelta(days=COMPANY_CACHE_TTL_DAYS)
    except (ValueError, TypeError):
        return False
