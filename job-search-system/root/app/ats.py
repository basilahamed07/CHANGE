"""Deterministic ATS lint for generated resumes — Golden Rule #4, no LLM.

One question, answered without a model: *would a typical applicant-tracking
system actually read this resume's content?* Real ATS parsers fall over on
tables, multi-column layouts, text boxes, images and missing standard headings,
and they silently drop a resume whose contact block they cannot find.

Everything here is pure text analysis: same input ⇒ same report, zero cost.

**HONESTY NOTE (2026-10-03):** nothing in the app calls this yet — only
`tests/test_ats.py` imports it, despite the original docstring claiming it ran on
every package build. It is designed to gate that path (a weak resume gets one
regeneration with the missing keywords; if still weak the report is attached so
the weakness is visible rather than silent), but wiring it in is deferred to
Stage-8 PACKAGES hardening. Do not assume packages are ATS-linted today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Section headings an ATS expects to be able to find. Matched on a normalized
# line, so "PROFESSIONAL EXPERIENCE" and "Professional Experience:" both hit.
STANDARD_SECTIONS: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "objective",
                "about", "about me"),
    "experience": ("experience", "professional experience", "work experience",
                   "employment", "employment history", "work history"),
    "education": ("education", "academic background", "academics"),
    "skills": ("skills", "technical skills", "core competencies",
               "technologies", "technical proficiencies"),
}

# Two or more of these on one line is a column/table layout, which most parsers
# read as garbage (or drop entirely).
_COLUMN_SEPARATORS = ("\t", "  |  ", " | ")
_BOX_CHARS = "│┃┆┇┊┋╎╏▏▕"
_BULLET_CHARS = "-*•‣▪◦●○"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().\-]{7,}\d)")
_LINKEDIN_RE = re.compile(r"(?:linkedin\.com|github\.com)/[A-Za-z0-9_\-/]+", re.I)

# A raw phone pattern is far too greedy: it matches dates and year ranges
# (`2021-2026`, `2024-01-15`), which would silently satisfy the contact check
# on a resume that carries no phone at all. Real E.164 numbers have >= 10
# digits, and dates/year ranges never do.
_MIN_PHONE_DIGITS = 10


def _find_phone(text: str) -> str | None:
    """First plausible phone number, or None. See `_MIN_PHONE_DIGITS`."""
    for m in _PHONE_RE.finditer(text or ""):
        if sum(ch.isdigit() for ch in m.group()) >= _MIN_PHONE_DIGITS:
            return m.group()
    return None


def _pipe_column_layout(line: str) -> bool:
    """True when `|` separators mark a table rather than a contact block.

    Resumes conventionally put contact details on ONE line separated by `|`
    (`email | phone | linkedin`) — every ATS parses that fine, so flagging it
    would fail nearly every real resume. A genuine column layout carries no
    contact markers at all.
    """
    if line.count("|") < 2:
        return False
    if not any(sep in line for sep in _COLUMN_SEPARATORS):
        return False
    return not (_EMAIL_RE.search(line) or _find_phone(line))

_STOPWORDS = frozenset("""
a an and or the to of in for with on at by from as is are be been being will
would can could should may might must do does did doing have has had having
we you they he she it i our your their its this that these those not no if
then than so such about into over under again more most other some any all
both each few nor only own same too very s t just don now role position job
work working team teams experience experienced years year strong good great
plus etc via per within across including include includes ability able
requirements required requirement responsibilities responsibility you'll we're
looking join help build building using use used new well also ensure ensure
what who whom which when where why how our us their them his her
""".split())


def _normalize(line: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", line.lower()).strip()


def _content_lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _sections_found(lines: list[str]) -> list[str]:
    """Which standard sections appear as their own (short) heading line."""
    found: set[str] = set()
    for raw in lines:
        if len(raw) > 60:
            continue
        norm = _normalize(raw)
        if not norm:
            continue
        for section, aliases in STANDARD_SECTIONS.items():
            if section in found:
                continue
            if any(norm == a or norm.rstrip("s ") == a.rstrip("s ") for a in aliases):
                found.add(section)
    return sorted(found)


def _visual_hazards(lines: list[str]) -> list[str]:
    """Layout constructs that break text extraction."""
    hazards: list[str] = []
    for raw in lines:
        if any(ch in raw for ch in _BOX_CHARS):
            hazards.append(f"box-drawing/text-box characters: {raw[:60]!r}")
        elif _pipe_column_layout(raw):
            hazards.append(f"column layout (pipes): {raw[:60]!r}")
        elif "\t" in raw:
            hazards.append(f"tab-separated columns: {raw[:60]!r}")
    # De-duplicate while keeping order; one example per hazard kind is enough.
    seen: set[str] = set()
    out: list[str] = []
    for h in hazards:
        kind = h.split(":", 1)[0]
        if kind in seen:
            continue
        seen.add(kind)
        out.append(h)
    return out


def _bullet_markers(lines: list[str]) -> set[str]:
    markers: set[str] = set()
    for raw in lines:
        if raw and raw[0] in _BULLET_CHARS:
            markers.add(raw[0])
    return markers


def jd_keywords(job_description: str, limit: int = 40) -> list[str]:
    """Content words the JD leans on, longest-first, stopwords removed.

    Deterministic proxy for "what will the ATS and the recruiter search for".
    Includes common tech tokens like c++, ci/cd and node.js that a plain word
    split would otherwise mangle.
    """
    text = (job_description or "").lower()
    tokens = re.findall(r"[a-z0-9][a-z0-9+#./\-]*", text)
    counts: dict[str, int] = {}
    for tok in tokens:
        # Keep + and # inside the token (c++, c#, ci/cd) but drop edge punctuation.
        base = tok.strip("-./")
        if len(base) < 3 or base in _STOPWORDS:
            continue
        if base.isdigit():
            continue
        counts[base] = counts.get(base, 0) + 1
    ranked = sorted(counts, key=lambda k: (-counts[k], -len(k), k))
    return ranked[:limit]


def _keyword_coverage(resume_text: str, keywords: list[str]) -> tuple[float, list[str]]:
    if not keywords:
        return 1.0, []
    haystack = (resume_text or "").lower()
    missing = [k for k in keywords if k not in haystack]
    present = len(keywords) - len(missing)
    return present / len(keywords), missing


@dataclass
class AtsIssue:
    code: str
    severity: str          # "fail" | "warn"
    detail: str
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail, "items": self.items}


@dataclass
class AtsReport:
    score: int
    issues: list[AtsIssue] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)
    word_count: int = 0
    keyword_coverage: float = 1.0

    @property
    def ok(self) -> bool:
        """No `fail`-severity issue survived. Warnings never block."""
        return not any(i.severity == "fail" for i in self.issues)

    @property
    def failures(self) -> list[dict]:
        return [i.to_dict() for i in self.issues if i.severity == "fail"]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
            "missing_keywords": self.missing_keywords,
            "sections_found": self.sections_found,
            "word_count": self.word_count,
            "keyword_coverage": round(self.keyword_coverage, 3),
        }


# Below this the package path regenerates once (see app/routers/packages.py).
ATS_PASS_THRESHOLD = 70
# Below this fraction of the JD's keywords the resume is off-target. Raised from
# 0.4 -> 0.6: a resume missing more than 40% of the JD's skills should not clear
# the keyword gate. Below `KEYWORD_COVERAGE_THIN` it merely warns.
KEYWORD_COVERAGE_FLOOR = 0.6
KEYWORD_COVERAGE_THIN = 0.75


def ats_lint(
    resume_text: str,
    job_description: str = "",
    profile: dict | None = None,
) -> AtsReport:
    """Grade `resume_text` for ATS parseability and JD alignment.

    `profile` is accepted for future structured checks (contact details from the
    user's stored profile); it is not required and its absence never fails.
    """
    text = resume_text or ""
    lines = _content_lines(text)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+#./\-]*", text)
    word_count = len(words)

    issues: list[AtsIssue] = []
    score = 100

    # -- contact block ------------------------------------------------------
    has_email = bool(_EMAIL_RE.search(text))
    has_phone = _find_phone(text) is not None
    if not has_email and not has_phone:
        issues.append(AtsIssue(
            "missing_contact", "fail",
            "No email or phone number found — an ATS cannot attach this resume "
            "to a candidate."))
        score -= 30
    elif not has_email:
        issues.append(AtsIssue(
            "missing_email", "warn",
            "No email address found; only a phone number."))
        score -= 8
    if not _LINKEDIN_RE.search(text):
        issues.append(AtsIssue(
            "missing_profile_link", "warn",
            "No LinkedIn/GitHub URL found (optional, but recruiters look)."))
        score -= 3

    # -- standard sections --------------------------------------------------
    sections = _sections_found(lines)
    if len(sections) < 2:
        issues.append(AtsIssue(
            "missing_standard_sections", "fail",
            "Fewer than two standard section headings "
            f"({', '.join(STANDARD_SECTIONS)}) were found; parsers key off these.",
            items=list(STANDARD_SECTIONS.keys())))
        score -= 25
    elif "experience" not in sections:
        issues.append(AtsIssue(
            "missing_experience_heading", "warn",
            "No EXPERIENCE heading found."))
        score -= 8

    # -- layout hazards -----------------------------------------------------
    hazards = _visual_hazards(lines)
    if hazards:
        issues.append(AtsIssue(
            "layout_hazard", "fail",
            "Table/column constructs that ATS parsers read as noise.",
            items=hazards))
        score -= 20

    markers = _bullet_markers(lines)
    if len(markers) > 1:
        issues.append(AtsIssue(
            "inconsistent_bullets", "warn",
            f"Mixed bullet markers ({''.join(sorted(markers))}); use one.",
            items=sorted(markers)))
        score -= 4

    # -- length -------------------------------------------------------------
    if word_count < 150:
        issues.append(AtsIssue(
            "too_short", "warn",
            f"Only {word_count} words — likely a truncated or empty resume."))
        score -= 15
    elif word_count > 1400:
        issues.append(AtsIssue(
            "too_long", "warn",
            f"{word_count} words — trim toward 700-1000 for a 1-2 page resume."))
        score -= 6

    # -- JD keyword coverage ------------------------------------------------
    keywords = jd_keywords(job_description)
    coverage, missing = _keyword_coverage(text, keywords)
    if keywords and coverage < KEYWORD_COVERAGE_FLOOR:
        issues.append(AtsIssue(
            "low_keyword_coverage", "fail",
            f"Only {coverage:.0%} of the job description's keywords appear in "
            f"the resume (floor {KEYWORD_COVERAGE_FLOOR:.0%}).",
            items=missing[:20]))
        score -= 20
    elif keywords and coverage < KEYWORD_COVERAGE_THIN:
        issues.append(AtsIssue(
            "thin_keyword_coverage", "warn",
            f"{coverage:.0%} of the job description's keywords appear.",
            items=missing[:20]))
        score -= 5

    return AtsReport(
        score=max(0, min(100, score)),
        issues=issues,
        missing_keywords=missing[:25],
        sections_found=sections,
        word_count=word_count,
        keyword_coverage=coverage,
    )


def ats_pass(report: AtsReport) -> bool:
    """The gate: a report passes when it has no hard failure AND clears the score."""
    return report.ok and report.score >= ATS_PASS_THRESHOLD
