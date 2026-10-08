"""Country-specific resume prompt and render profiles.

The goal is not to create decorative national themes. It is to tune the same
ATS-safe resume for local expectations: density, section emphasis, contact line,
and what the LLM should avoid adding.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResumeCountryProfile:
    country: str
    font_family: str = "Verdana"
    font_size: int = 12
    line_height: float = 1.3
    paragraph_space: int = 5
    margin_v: int = 55
    margin_h: int = 45
    section_rule_px: int = 1
    heading_letter_spacing: str = "0.08em"
    guidance: str = ""


BASE_GUIDANCE = (
    "Use an ATS-safe, single-column resume. Do not add a photo, date of birth, "
    "marital status, religion, gender, passport/ID numbers, full street address, "
    "or unrelated personal details. Keep claims evidence-backed."
)


_PROFILES = {
    "Singapore": ResumeCountryProfile(
        country="Singapore",
        font_family="Arial",
        font_size=11,
        line_height=1.18,
        paragraph_space=3,
        margin_v=38,
        margin_h=38,
        heading_letter_spacing="0.06em",
        guidance=(
            BASE_GUIDANCE + " Singapore style: use UK English, keep the resume "
            "within two A4 pages, put technical/core skills near the top, use "
            "bold section hierarchy, reverse chronological experience, action "
            "verbs, and quantified results where verified."
        ),
    ),
    "Germany": ResumeCountryProfile(
        country="Germany",
        font_family="Arial",
        font_size=10,
        line_height=1.16,
        paragraph_space=3,
        margin_v=36,
        margin_h=38,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " Germany style: use a conservative Lebenslauf-like "
            "structure, clear dates, employer/title/location headings, concise "
            "factual bullets, and a complete reverse-chronological work history. "
            "For tech roles, keep it ATS-readable and do not add a photo unless "
            "the employer explicitly requests one."
        ),
    ),
    "Canada": ResumeCountryProfile(
        country="Canada",
        font_family="Arial",
        font_size=11,
        line_height=1.22,
        paragraph_space=4,
        margin_v=44,
        margin_h=42,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " Canada style: no photo and no unnecessary personal "
            "information. Focus on skills, work experience, measurable impact, "
            "and concise role-targeted bullets."
        ),
    ),
    "UK": ResumeCountryProfile(
        country="UK",
        font_family="Arial",
        font_size=11,
        line_height=1.22,
        paragraph_space=4,
        margin_v=44,
        margin_h=42,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " UK style: call it a CV, use UK English, no photo, "
            "no age/date of birth/marital status/nationality, and keep it concise."
        ),
    ),
    "Ireland": ResumeCountryProfile(
        country="Ireland",
        font_family="Arial",
        font_size=11,
        line_height=1.22,
        paragraph_space=4,
        margin_v=44,
        margin_h=42,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " Ireland style: UK-style CV conventions, concise "
            "impact bullets, no photo or unnecessary personal details."
        ),
    ),
    "Netherlands": ResumeCountryProfile(
        country="Netherlands",
        font_family="Arial",
        font_size=10,
        line_height=1.18,
        paragraph_space=3,
        margin_v=40,
        margin_h=38,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " Netherlands style: direct, concise, practical CV; "
            "emphasize impact, tools, and international work readiness."
        ),
    ),
    "Australia": ResumeCountryProfile(
        country="Australia",
        font_family="Arial",
        font_size=11,
        line_height=1.22,
        paragraph_space=4,
        margin_v=44,
        margin_h=42,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " Australia style: no photo or unrelated personal "
            "details; emphasize achievements, role fit, and concise skills."
        ),
    ),
    "UAE": ResumeCountryProfile(
        country="UAE",
        font_family="Arial",
        font_size=10,
        line_height=1.18,
        paragraph_space=3,
        margin_v=40,
        margin_h=38,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " UAE style: polished professional CV, clear "
            "availability/relocation/work authorization line, strong skills and "
            "project impact near the top."
        ),
    ),
    "India": ResumeCountryProfile(
        country="India",
        font_family="Arial",
        font_size=10,
        line_height=1.18,
        paragraph_space=3,
        margin_v=40,
        margin_h=38,
        heading_letter_spacing="0.04em",
        guidance=(
            BASE_GUIDANCE + " India style: concise ATS resume, skills near the "
            "top, project and technology details clearly grouped, quantified "
            "impact where verified."
        ),
    ),
}


def canonical_country(country: str | None) -> str:
    value = (country or "").strip()
    aliases = {
        "United Kingdom": "UK",
        "GB": "UK",
        "United States": "US",
        "USA": "US",
        "United Arab Emirates": "UAE",
        "SG": "Singapore",
        "DE": "Germany",
        "CA": "Canada",
        "IN": "India",
    }
    return aliases.get(value, value)


def get_resume_country_profile(country: str | None) -> ResumeCountryProfile:
    canonical = canonical_country(country)
    return _PROFILES.get(canonical, ResumeCountryProfile(
        country=canonical or "Global",
        guidance=BASE_GUIDANCE + " Global style: concise ATS-safe resume tailored to the role.",
    ))


def country_resume_guidance(country: str | None) -> str:
    return get_resume_country_profile(country).guidance


def country_resume_css(country: str | None, preview_id: str) -> str:
    p = get_resume_country_profile(country)
    i = f"#{preview_id}"
    return (
        f"{i} {{ font-family: {p.font_family}, sans-serif; font-size: {p.font_size}px; }}"
        f"{i} {{ padding: {p.margin_v}px {p.margin_h}px; }}"
        f"{i} p, {i} li {{ line-height: {p.line_height:.2f}; }}"
        f"{i} h2 {{ margin-top: {p.paragraph_space}px; }}"
        f"{i} h1 {{ letter-spacing: {p.heading_letter_spacing}; }}"
        f"{i} h1, {i} h2 {{ border-bottom-width: {p.section_rule_px}px; }}"
        f"@media print {{ @page {{ size: A4; margin: 0; }} }}"
    )
