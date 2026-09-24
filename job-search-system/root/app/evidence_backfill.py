"""Backfill VERIFIED evidence from data already stored in a workspace.

Why this exists: the resume-tailoring gate compares generated text against the
VERIFIED evidence corpus. A user whose resume was uploaded BEFORE resume-driven
autofill existed (or who uploaded while the AI analysis was unavailable) ends up
with a nearly empty corpus — every generated line then fails as
"unsupported_claim" and preparation returns 422 forever.

This module repairs that using ONLY facts already inside the user's own
workspace (resume text, analysed skills/titles, parsed profile rows). It costs
ZERO AI calls and never invents anything.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_RESUME_CLAIM_CHARS = 12000


def _slug(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")[:44]


def build_backfill_claims(resume_text: str, search_config: dict | None,
                          full_profile: dict | None) -> dict[str, list[dict]]:
    """Turn already-stored workspace data into evidence claims (no AI)."""
    search_config = search_config or {}
    full_profile = full_profile or {}
    extracted: dict[str, list[dict]] = {}

    # 1. The resume text itself — the checker's primary corpus for generated
    #    bullets that paraphrase the candidate's own document.
    resume_text = (resume_text or "").strip()
    if len(resume_text) > 120:
        extracted["experience"] = [{
            "id": "resume_source_text",
            "value": resume_text[:MAX_RESUME_CLAIM_CHARS],
            "notes": "Verbatim uploaded resume text (source of truth).",
        }]

    # 2. Skills already analysed from the resume.
    skills = [str(s).strip() for s in (search_config.get("key_skills") or []) if str(s).strip()]
    if skills:
        extracted["skills"] = [{"id": f"skill_{_slug(s)}", "value": s} for s in skills]

    # 3. Work history rows already parsed into the profile.
    work = full_profile.get("work_history") or []
    exp = extracted.setdefault("experience", [])
    for row in work:
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or row.get("position") or "").strip()
        company = (row.get("company") or "").strip()
        start = (row.get("start_date") or "").strip()
        end = (row.get("end_date") or "").strip() or ("Present" if row.get("current") else "")
        if not (title or company):
            continue
        dates = " – ".join(p for p in (start, end) if p)
        value = f"{title} at {company}" if (title and company) else (title or company)
        if dates:
            value += f" ({dates})"
        entry = {"id": f"exp_{_slug(value)}", "value": value}
        if row.get("description"):
            entry["notes"] = str(row["description"])[:400]
        exp.append(entry)

    # 4. Education rows.
    edu = []
    for row in full_profile.get("education") or []:
        if not isinstance(row, dict):
            continue
        degree = (row.get("degree") or row.get("field_of_study") or "").strip()
        school = (row.get("institution") or row.get("school") or "").strip()
        year = (row.get("end_date") or row.get("graduation_year") or "").strip()
        parts = [p for p in (degree, school) if p]
        if not parts:
            continue
        value = " — ".join(parts) + (f" ({year})" if year else "")
        edu.append({"id": f"edu_{_slug(value)}", "value": value})
    if edu:
        extracted["education"] = edu

    # 5. Certifications.
    certs = []
    for row in full_profile.get("certifications") or []:
        if not isinstance(row, dict):
            continue
        name = (row.get("name") or "").strip()
        if not name:
            continue
        issuer = (row.get("issuer") or "").strip()
        certs.append({"id": f"cert_{_slug(name)}",
                      "value": name + (f" — {issuer}" if issuer else "")})
    if certs:
        extracted["certifications"] = certs

    return {k: v for k, v in extracted.items() if v}


async def backfill_workspace(db, store) -> dict:
    """Load stored workspace data → merge as VERIFIED claims → sync to DB."""
    search_config = await db.get_search_config() or {}
    resume_text = (search_config.get("resume_text") or "").strip()
    if not resume_text:
        # Fall back to any stored resume row.
        try:
            resumes = await db.get_resumes()
            for r in resumes:
                if r.get("resume_text"):
                    resume_text = r["resume_text"]
                    if r.get("is_default"):
                        break
        except Exception:
            pass
    if not resume_text:
        return {"skipped": "no stored resume text"}

    try:
        full_profile = await db.get_full_profile()
    except Exception:
        full_profile = {}

    claims = build_backfill_claims(resume_text, search_config, full_profile)
    if not claims:
        return {"skipped": "nothing to backfill"}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = store.merge_extracted_claims(
        claims, f"stored resume backfill ({today})")
    await store.sync_to_db(db)
    logger.info("Evidence backfill: %s", summary)
    return summary
