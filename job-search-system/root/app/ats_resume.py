"""ATS-first resume rendering: structured JSON -> Markdown (the source of truth).

Flow
----
    Tailor.prepare()   ->  resume_json (structured) + tailored_resume (plain text)
    /prepare, /build   ->  resume_json_to_markdown() -> resume.md   <- THE SOURCE
    resume.md          ->  app.html_renderer         -> HTML
    HTML               ->  app.pdf_renderer          -> resume.pdf
    resume_json / text ->  app.docx_generator        -> resume.docx

Markdown is the source because it is diffable, reviewable and local-first; the
other formats are derived from it and can be regenerated at any time.

Junian Markdown Resume (github.com/junian/markdown-resume) consumes ordinary
Markdown, which is what this module emits. Its optional front-matter block
(opener ``= yaml =|---``, closer ``---`` or ``...``) is emitted only when asked
for, because we cannot verify which keys that editor honours; plain Markdown
already round-trips through it.
"""

from __future__ import annotations

import json
import re

# junian/markdown-resume front-matter delimiters (from its front-matter package).
FRONT_MATTER_OPEN = "= yaml =|---"
FRONT_MATTER_CLOSE = "---"

# Provider noise / thinking traces that must never reach a resume.
_STRIP_KEYS = frozenset({
    "reasoning", "reasoning_content", "thinking", "chain_of_thought", "error",
})

_MOJIBAKE_REPLACEMENTS = {
    "\u00e2\u20ac\u00a2": "-",
    "\u00e2\u20ac\u201c": "-",
    "\u00e2\u20ac\u201d": "-",
    "\u00e2\u20ac\u02dc": "'",
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u0153": '"',
    "\u2022": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}

# Acronyms whose casing must survive heading normalisation.
_KEEP_UPPER = frozenset({
    "AI", "ML", "LLM", "LLMS", "RAG", "MCP", "SQL", "API", "APIS", "NLP",
    "JWT", "RBAC", "UBAC", "ATS", "CI", "CD", "AWS", "GCP", "UI", "UX", "ETL",
})

_CONTACT_ORDER = ("location", "email", "phone", "linkedin", "github", "portfolio")


# --------------------------------------------------------------------- text

def clean_text(text) -> str:
    """Repair mojibake and collapse horizontal whitespace."""
    if text is None:
        return ""
    cleaned = text if isinstance(text, str) else str(text)
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _inline(text) -> str:
    """Make a value safe to place on a Markdown line."""
    value = clean_text(text).replace("|", r"\|")
    return re.sub(r"^([#>*+`]|\d+\.)\s*", lambda m: "\\" + m.group(1) + " ", value)


def _bullet(text) -> str:
    value = re.sub(r"^[-*+]\s*", "", clean_text(text))
    return "- " + " ".join(value.split()) if value else ""


def _as_list(value) -> list:
    """Coerce a string / list / None into clean non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        out = []
        for raw in value.splitlines():
            raw = re.sub(r"^[-*+]\s*", "", raw.strip())
            if raw:
                out.append(clean_text(raw))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            if isinstance(item, str):
                if clean_text(item):
                    out.append(clean_text(item))
            else:
                out.extend(_as_list(item))
        return out
    if isinstance(value, (dict, list, tuple, set)):
        return []
    text = clean_text(value)
    return [text] if text else []


def _as_dicts(value) -> list:
    if not isinstance(value, (list, tuple)):
        return []
    return [v for v in value if isinstance(v, dict)]


def _join_parts(*parts) -> str:
    return " | ".join(clean_text(p) for p in parts if clean_text(p))


def _strip_non_content(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in _STRIP_KEYS}


# ------------------------------------------------------------------ parsing

def _loads(text: str):
    """Parse a JSON object, tolerating fenced blocks and surrounding prose.

    Models sometimes prefix the object with a sentence or wrap it in a fenced
    block even in JSON mode, so we fall back to the outermost brace pair.
    """
    candidate = (text or "").strip()
    if not candidate:
        return None
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate).strip()

    for attempt in (candidate, _outermost_object(candidate)):
        if not attempt:
            continue
        try:
            parsed = json.loads(attempt)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return _strip_non_content(parsed)
    return None


def _outermost_object(text: str) -> str:
    """The substring from the first ``{`` to the last ``}``, or empty."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else ""


def parse_resume_json(value):
    """Return a structured resume dict, or None when the value is not one."""
    if isinstance(value, dict):
        return _strip_non_content(value)
    if not isinstance(value, str) or not value.strip():
        return None
    return _loads(value)


def is_structured(value) -> bool:
    """True when the value is a genuinely structured resume.

    Deliberately strict. ``coerce_resume_json`` can wrap arbitrary text in a
    ``{"summary_text": ...}`` object, and rendering *that* as structure would
    silently emit a summary-only resume and lose every section. So we require a
    ``basics`` block plus at least one real section, and otherwise fall back to
    the plain-text path (``tailored_resume`` always holds the full content).
    """
    data = parse_resume_json(value)
    if not data or "basics" not in data:
        return False
    return any(k in data for k in ("summary", "summary_text", "skills",
                                   "experience", "projects", "education"))


def coerce_resume_json(value) -> str:
    """Normalise AI output to structured JSON text, or ``""`` if it is not.

    Returning empty instead of wrapping loose text keeps one invariant: the
    ``resume_json`` column is either a real structure or absent. The plain text
    always survives separately in ``tailored_resume``.
    """
    if not is_structured(value):
        return ""
    data = parse_resume_json(value)
    return json.dumps(_strip_non_content(data))


# ------------------------------------------------------------ shared pieces

def _basics_of(data: dict):
    basics = data.get("basics") if isinstance(data.get("basics"), dict) else {}
    name = clean_text(basics.get("name"))
    headline = clean_text(basics.get("headline"))
    contact = basics.get("contact")
    if isinstance(contact, dict):
        contact_line = _join_parts(*[contact.get(k) for k in _CONTACT_ORDER])
    else:
        contact_line = clean_text(contact)
    return name, headline, contact_line


def _skill_lines(skills):
    """Skills as ``Group: a, b, c`` lines — stable for Markdown and plain text."""
    if isinstance(skills, dict):
        out = []
        for group, values in skills.items():
            joined = ", ".join(_as_list(values))
            if joined:
                out.append(clean_text(group) + ": " + joined)
        return out
    if isinstance(skills, (list, tuple)):
        out = []
        for item in _as_dicts(skills):
            joined = ", ".join(_as_list(item.get("items") or item.get("skills")))
            if joined:
                out.append(clean_text(item.get("group") or "Skills") + ": " + joined)
        for plain in _as_list(skills):
            out.append(plain)
        return out
    return _as_list(skills)


def _experience_entries(data: dict):
    out = []
    for item in _as_dicts(data.get("experience")):
        out.append({
            "header": _join_parts(
                item.get("title"), item.get("company"),
                item.get("location"), item.get("dates"),
            ),
            "summary": clean_text(item.get("summary")),
            "bullets": _as_list(
                item.get("bullets") or item.get("highlights") or item.get("description")),
        })
    return out


def _project_entries(data: dict):
    out = []
    for item in _as_dicts(data.get("projects")):
        name = clean_text(item.get("name") or item.get("title"))
        stack = clean_text(item.get("stack"))
        header = name + (" | " + stack if stack and name else stack)
        out.append({
            "header": header,
            "bullets": _as_list(
                item.get("bullets") or item.get("highlights") or item.get("description")),
        })
    return out


def _education_entries(data: dict):
    out = []
    for item in _as_dicts(data.get("education")):
        header = _join_parts(
            item.get("degree"), item.get("institution"),
            item.get("location"), item.get("dates"),
        )
        if header:
            out.append(header)
    return out


# ------------------------------------------------------------- plain text

def resume_json_to_text(value) -> str:
    """Flatten a structured resume to plain text (feeds DOCX + hashing)."""
    data = parse_resume_json(value)
    if data is None or "basics" not in data:
        return clean_text(value) if isinstance(value, str) else ""

    name, headline, contact = _basics_of(data)
    blocks = []
    head = _join_parts(name, headline)
    if head:
        blocks.append(head)
    if contact:
        blocks.append(contact)

    def add_section(title, body_lines):
        body_lines = [b for b in body_lines if b]
        if not body_lines:
            return
        if blocks:
            blocks.append("")
        blocks.append(title)
        blocks.extend(body_lines)

    add_section("PROFESSIONAL SUMMARY",
                [clean_text(data.get("summary") or data.get("summary_text"))])
    add_section("TECHNICAL SKILLS", _skill_lines(data.get("skills")))

    exp_lines = []
    for entry in _experience_entries(data):
        if entry["header"]:
            exp_lines.append(entry["header"])
        exp_lines.extend(entry["bullets"])
    add_section("PROFESSIONAL EXPERIENCE", exp_lines)

    proj_lines = []
    for entry in _project_entries(data):
        if entry["header"]:
            proj_lines.append(entry["header"])
        proj_lines.extend(entry["bullets"])
    add_section("PROJECTS", proj_lines)

    add_section("EDUCATION", _education_entries(data))
    add_section("CERTIFICATIONS", _as_list(data.get("certifications")))
    add_section("LANGUAGES", _as_list(data.get("languages")))

    return "\n".join(blocks).strip()


def resume_text(value) -> str:
    """Plain text for any stored resume shape (structured or legacy)."""
    if is_structured(value):
        return resume_json_to_text(parse_resume_json(value))
    data = parse_resume_json(value)
    if data is not None:
        return clean_text(data.get("summary_text"))
    return clean_text(value) if isinstance(value, str) else ""


# ---------------------------------------------------------------- markdown

def _heading(text) -> str:
    """Case-correct a heading: 'PROFESSIONAL SUMMARY' -> 'Professional Summary'."""
    words = []
    for word in clean_text(text).split():
        plain = re.sub(r"[^A-Za-z0-9+#./-]", "", word).upper()
        words.append(plain if plain in _KEEP_UPPER else word.capitalize())
    return " ".join(words)


def resume_json_to_markdown(value, *, contact: str = "", front_matter: bool = False) -> str:
    """Render a structured resume dict (or its JSON text) as ATS Markdown."""
    data = parse_resume_json(value)
    if data is None or "basics" not in data:
        return resume_text_to_markdown(value if isinstance(value, str) else "")

    name, headline, contact_line = _basics_of(data)
    name = name or "Resume"
    contact_line = contact_line or clean_text(contact)

    out = []
    if front_matter:
        out.append(FRONT_MATTER_OPEN)
        out.append("name: " + name)
        if headline:
            out.append("headline: " + headline)
        if contact_line:
            out.append("contact: " + contact_line)
        out.append(FRONT_MATTER_CLOSE)
        out.append("")

    out.extend(["# " + _inline(name), ""])
    if headline:
        out.extend(["**" + _inline(headline) + "**", ""])
    if contact_line:
        out.extend([_inline(contact_line), ""])

    summary = clean_text(data.get("summary") or data.get("summary_text"))
    if summary:
        out.extend(["## Professional Summary", "", summary, ""])

    skills = _skill_lines(data.get("skills"))
    if skills:
        out.extend(["## Technical Skills", ""])
        for line in skills:
            out.extend([_inline(line), ""])

    experience = _experience_entries(data)
    if experience:
        out.extend(["## Professional Experience", ""])
        for entry in experience:
            if entry["header"]:
                out.extend(["### " + _inline(entry["header"]), ""])
            if entry["summary"]:
                out.extend([entry["summary"], ""])
            out.extend([_bullet(b) for b in entry["bullets"]])
            out.append("")

    projects = _project_entries(data)
    if projects:
        out.extend(["## Projects", ""])
        for entry in projects:
            if entry["header"]:
                out.extend(["### " + _inline(entry["header"]), ""])
            out.extend([_bullet(b) for b in entry["bullets"]])
            out.append("")

    education = _education_entries(data)
    if education:
        out.extend(["## Education", ""])
        for header in education:
            out.extend(["### " + _inline(header), ""])

    certs = _as_list(data.get("certifications"))
    if certs:
        out.extend(["## Certifications", ""])
        out.extend([_bullet(c) for c in certs])
        out.append("")

    languages = _as_list(data.get("languages"))
    if languages:
        out.extend(["## Languages", "", ", ".join(languages), ""])

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------- plain -> markdown

def _looks_like_heading(line: str) -> bool:
    if len(line) > 70 or any(ch.isdigit() for ch in line):
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return False
    return sum(ch.isupper() for ch in letters) / len(letters) > 0.75


def resume_text_to_markdown(text) -> str:
    """Best-effort Markdown from unstructured resume text (legacy fallback).

    Kept for resumes stored before the structured schema existed: it guesses
    headings by ALL-CAPS and bullets by their marker, so prefer the structured
    path whenever ``resume_json`` is present.
    """
    lines = [ln.strip() for ln in clean_text(text).splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""

    out = []
    first_content = True
    for line in lines:
        # Collapse any run of leading bullet markers into exactly one, so a
        # mojibake bullet inside a real bullet never renders as "- - item".
        if re.match(r"^[-*+]\s", line):
            line = re.sub(r"^(?:[-*+]\s*)+", "- ", line)
        if first_content:
            out.extend(["# " + line.title(), ""])
            first_content = False
            continue
        if _looks_like_heading(line):
            out.extend(["## " + _heading(line), ""])
            continue
        if line.startswith("- "):
            out.append(line)
            continue
        if " | " in line and out and not out[-1].startswith("#"):
            out.extend(["**" + line + "**", ""])
            continue
        out.extend([line, ""])
    return "\n".join(out).strip() + "\n"


def text_forms_for_evidence_check(tailored_resume, resume_json="") -> list:
    """Every text form of a resume that could reach an ATS.

    The evidence gate only guards what it is handed, so it must be handed the
    text the package actually renders from — not only the plain text. When the
    resume is structured, the flattened structure is checked too, so a claim
    that exists only in the structure can never ship unverified (Golden Rule 5).

    Returns only non-empty forms; callers fall back to ``[""]`` if the caller
    has nothing to check at all.
    """
    forms = [tailored_resume or ""]
    if is_structured(resume_json):
        rendered = clean_text(resume_json_to_text(parse_resume_json(resume_json)))
        if rendered and rendered not in forms:
            forms.append(rendered)
    return [f for f in forms if f.strip()]


def build_resume_markdown(stored, *, contact: str = "") -> str:
    """One entry point for callers: structured when possible, else legacy."""
    if not stored or not str(stored).strip():
        return ""
    if is_structured(stored):
        return resume_json_to_markdown(stored, contact=contact)
    data = parse_resume_json(stored)
    if data:
        # An unstructured wrapper still carries the text we need.
        stored = data.get("summary_text") or ""
    return resume_text_to_markdown(stored)


def looks_like_resume_markdown(markdown_text) -> bool:
    """Reject label/value dumps masquerading as resume Markdown.

    The PDF/DOCX styling only has something to work with when the source has
    the resume skeleton: H1 name, H2 sections, role/project H3s, and bullets.
    """
    text = markdown_text if isinstance(markdown_text, str) else ""
    if not text.strip():
        return False
    has_h1 = bool(re.search(r"(?m)^#\s+\S", text))
    h2s = re.findall(r"(?m)^##\s+(.+)$", text)
    has_core_section = any(
        re.search(r"(summary|experience|skills|projects|education)", h, re.I)
        for h in h2s
    )
    has_detail = bool(re.search(r"(?m)^###\s+\S", text) or re.search(r"(?m)^-\s+\S", text))
    # Common bad model shape: "name: ...\nheadline: ..." with no Markdown
    # structure. A few colons are normal in skill lines, but too many labels
    # without headings indicates a raw key/value dump.
    label_lines = len(re.findall(r"(?m)^[A-Za-z_ ]{2,24}:\s+\S", text))
    return has_h1 and len(h2s) >= 2 and has_core_section and has_detail and label_lines < 10
