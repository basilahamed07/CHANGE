"""Resume → evidence autofill.

A user's OWN uploaded resume is the source of truth about them, so everything
extracted from it is written as VERIFIED evidence with an explicit source
("uploaded resume: <filename>"). This is what makes the system usable for a
new user without hand-editing YAML: upload resume → settings + evidence
profile configure themselves → matching and resume generation work.

Golden Rule 5 is still respected:
  - nothing is EVER invented — only text present in the resume/analysis;
  - DISPUTED and DO_NOT_USE claims are never touched (see merge_extracted_claims);
  - every auto-verified claim carries its source for audit.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_SKILL_SECTIONS = ("key_skills",)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", str(value).lower())


def _claim_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return f"{prefix}_{slug[:44]}" if slug else f"{prefix}_item"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        v = str(v or "").strip()
        if not v:
            continue
        key = _norm(v)
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _skill_names(raw) -> list[str]:
    """Skills arrive as strings or {name, level, category} dicts."""
    out = []
    for item in raw or []:
        if isinstance(item, dict):
            v = item.get("name") or item.get("skill") or item.get("value")
        else:
            v = item
        if v:
            out.append(str(v))
    return out


def _date_range(*parts) -> str:
    vals = [str(p).strip() for p in parts if p and str(p).strip()]
    return " – ".join(vals)


def extract_claims_from_resume(analysis: dict, profile_data: dict,
                               resume_name: str) -> dict[str, list[dict]]:
    """Return {category: [ {id, value, notes?} ]} extracted from the resume.

    Categories map onto the evidence store's YAML files so matching, the
    evidence gate and the UI all read them exactly like hand-written claims.
    """
    analysis = analysis or {}
    profile_data = profile_data or {}
    extracted: dict[str, list[dict]] = {}

    # --- skills (analysis key_skills + parsed skills section)
    skills = _dedupe(_skill_names(analysis.get("key_skills"))
                     + _skill_names(profile_data.get("skills")))
    if skills:
        extracted["skills"] = [{"id": _claim_id("skill", s), "value": s} for s in skills]

    # --- experience
    experience = []
    for item in profile_data.get("work_history") or []:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or item.get("position") or "").strip()
        company = (item.get("company") or item.get("employer") or "").strip()
        dates = _date_range(item.get("start_date"),
                            item.get("end_date") or ("Present" if item.get("current") else ""))
        if title and company:
            value = f"{title} at {company}" + (f" ({dates})" if dates else "")
        elif title or company:
            value = title or company
            if dates:
                value += f" ({dates})"
        else:
            continue
        entry = {"id": _claim_id("exp", value), "value": value}
        desc = (item.get("description") or "").strip()
        if desc:
            entry["notes"] = desc[:400]
        experience.append(entry)
    if experience:
        extracted["experience"] = experience

    # --- education
    education = []
    for item in profile_data.get("education") or []:
        if not isinstance(item, dict):
            continue
        degree = (item.get("degree") or item.get("field_of_study") or "").strip()
        school = (item.get("institution") or item.get("school") or "").strip()
        year = (item.get("end_date") or item.get("graduation_year") or "").strip()
        parts = [p for p in (degree, school) if p]
        if not parts:
            continue
        value = " — ".join(parts) + (f" ({year})" if year else "")
        education.append({"id": _claim_id("edu", value), "value": value})
    if education:
        extracted["education"] = education

    # --- certifications
    certifications = []
    for item in profile_data.get("certifications") or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        issuer = (item.get("issuer") or item.get("organization") or "").strip()
        year = (item.get("date") or item.get("issue_date") or "").strip()
        if not name:
            continue
        value = name + (f" — {issuer}" if issuer else "") + (f" ({year})" if year else "")
        certifications.append({"id": _claim_id("cert", name), "value": value})
    if certifications:
        extracted["certifications"] = certifications

    # --- projects / achievements (only if the parser produced them)
    for section, prefix in (("projects", "proj"), ("achievements", "ach")):
        rows = []
        for item in profile_data.get(section) or []:
            if isinstance(item, dict):
                name = (item.get("name") or item.get("title") or "").strip()
                desc = (item.get("description") or "").strip()
            else:
                name, desc = str(item).strip(), ""
            if not name:
                continue
            entry = {"id": _claim_id(prefix, name), "value": name}
            if desc:
                entry["notes"] = desc[:400]
            rows.append(entry)
        if rows:
            extracted[section] = rows

    # --- identity facts from the resume header (name/email/links/location)
    personal = profile_data.get("personal") or {}
    identity_values = []
    for key, label in (("full_name", "Full name"), ("email", "Email"),
                       ("phone", "Phone"), ("location", "Location"),
                       ("linkedin_url", "LinkedIn"), ("github_url", "GitHub"),
                       ("portfolio_url", "Portfolio"), ("website", "Website")):
        val = (personal.get(key) or "").strip() if isinstance(personal, dict) else ""
        if val:
            identity_values.append({"id": _claim_id("cand", key), "value": f"{label}: {val}"})
    if identity_values:
        extracted["candidate"] = identity_values

    total = sum(len(v) for v in extracted.values())
    logger.info("Resume autofill: %d claims extracted from '%s' across %d categories",
                total, resume_name, len(extracted))
    return extracted


def seed_countries_from_resume(resume_text: str, registry, max_regions: int = 4) -> list[str]:
    """Detect target regions mentioned in the resume (country names/aliases/cities).

    Used ONLY to pre-fill the country strategy when the user has not chosen any
    yet — the user can always change it in Settings → Countries & Discovery.
    """
    if not resume_text or registry is None:
        return []
    low = f" {resume_text.lower()} "
    matched: list[str] = []
    try:
        for country in registry.countries.values():
            terms = [t for t in
                     [country.name, country.region_str, *getattr(country, "aliases", []),
                      *getattr(country, "cities", [])] if t]
            for term in terms:
                if re.search(rf"(?<![a-z]){re.escape(str(term).lower())}(?![a-z])", low):
                    matched.append(country.region_str)
                    break
    except Exception:
        logger.exception("country seeding from resume failed")
        return []
    # de-dupe, preserve registry order, cap to keep the strategy focused
    seen, out = set(), []
    for region in matched:
        if region not in seen:
            seen.add(region)
            out.append(region)
    if "remote" in low and "Remote" not in out:
        out.append("Remote")
    return out[:max_regions]
