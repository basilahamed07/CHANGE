"""Markdown -> HTML for resume artifacts, with no third-party dependency.

Scope is deliberately narrow: this renders exactly the Markdown subset
``app.ats_resume`` emits (headings, bullets, bold/italic, paragraphs) plus the
small extras a cover letter needs. Anything outside that subset degrades to
escaped plain text rather than being dropped.

Every value is HTML-escaped before any markup is added. Resume text is
AI-generated and a job description is untrusted input, so the renderer must
never pass raw HTML through to the page.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent / "ats_template"
# The Junian markdown-resume default resume template ("Resume Template 1").
# Its file is stored verbatim, including the upstream `#PREVIEW_SELECTOR`
# placeholder, which upstream swaps for `#vue-smart-pages-preview` at load
# time; we swap it for our own container id the same way.
_CSS_PATH = _TEMPLATE_DIR / "junian.css"
# Our original hand-written ATS stylesheet, kept as the fallback so a missing
# or unreadable junian.css still renders a sane single-column resume.
_FALLBACK_CSS_PATH = _TEMPLATE_DIR / "ats.css"

# The id the backbone CSS is scoped to. Must match the <main> in _document().
PREVIEW_ID = "resume-preview"

# Values copied from upstream site/src/utils/constants/default.ts. The backbone
# CSS deliberately carries NO font, size, colour or page setup — upstream injects
# those at runtime via setDynamicCss() — so without this layer the resume would
# render in the browser default font on Letter.
JUNIAN_THEME = {
    "fontFamily": "Verdana",
    "fontSize": 12,
    "lineHeight": 1.3,
    "paragraphSpace": 5,
    "themeColor": "#000000",
    "marginV": 55,
    "marginH": 45,
    "paper": "A4",
}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

# Inline emphasis. Bold first so ``**x**`` is not eaten by the italic rule.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
_CODE_RE = re.compile(r"`([^`]+)`")
# A bare http(s) URL or www host becomes a link; the label is the URL itself.
_URL_RE = re.compile(r"(?<![\"'=])\b(https?://[^\s<>()]+|www\.[^\s<>()]+)")


def _escape(text: str) -> str:
    return html.escape(text or "", quote=True)


def _inline_markup(text: str) -> str:
    """Render inline emphasis/links for one already-escaped line."""
    escaped = _escape(text)
    # Un-escape the emphasis delimiters we intend to honour, then re-apply them
    # as real tags. Everything else stays escaped.
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC_RE.sub(r"<em>\1</em>", escaped)
    escaped = _CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = escaped.replace(r"\|", "|")
    return _URL_RE.sub(_linkify, escaped)


def _linkify(match: re.Match) -> str:
    url = match.group(1)
    href = url if url.startswith("http") else "https://" + url
    return f'<a href="{html.escape(href, quote=True)}">{url}</a>'


_PARA_RE = re.compile(r"^<p>(?P<inner>.*)</p>$", re.S)


def _group_header(blocks: list[str]) -> list[str]:
    """Pull the lines under the H1 inside <header class="resume-header">.

    The Junian template centres its *whole* header block — upstream's Markdown
    has the name and the contact lines inside one header element. Ours has them
    as sibling paragraphs, so without this the name renders centred while the
    headline and contact lines stay left-aligned: the template's layout does
    not actually apply.

    Each absorbed paragraph is marked ``no-separator`` so the template's
    ``.resume-header-item:not(.no-separator)::after { content: " | " }`` rule
    can never arm — the separators are real text in the Markdown, and drawing
    them in CSS as well would double every pipe.
    """
    try:
        head = next(i for i, b in enumerate(blocks)
                    if b.startswith('<header class="resume-header">'))
    except StopIteration:
        return blocks                      # no H1 ⇒ nothing to group

    items: list[str] = []
    end = head + 1
    while end < len(blocks):
        m = _PARA_RE.match(blocks[end])
        if not m:
            break
        items.append(f'<p class="resume-header-item no-separator">'
                     f"{m.group('inner')}</p>")
        end += 1

    if not items:
        return blocks

    merged = (blocks[head][:-len("</header>")] + "\n" + "\n".join(items)
             + "\n</header>")
    return blocks[:head] + [merged] + blocks[end:]


def _flush_paragraph(buffer: list, out: list) -> None:
    if not buffer:
        return
    text = " ".join(buffer).strip()
    if text:
        out.append(f"<p>{_inline_markup(text)}</p>")
    buffer.clear()


def _flush_bullets(items: list, out: list) -> None:
    if not items:
        return
    out.append('<ul class="bullets">')
    for item in items:
        out.append(f"<li>{_inline_markup(item)}</li>")
    out.append("</ul>")
    items.clear()


def render_markdown_body(markdown_text: str) -> str:
    """Convert Markdown to an HTML fragment (no wrapper, no CSS)."""
    lines = (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")

    out: list = []
    paragraph: list = []
    bullets: list = []
    in_code = False
    code_lines: list = []
    seen_h1 = False

    def flush_all() -> None:
        _flush_paragraph(paragraph, out)
        _flush_bullets(bullets, out)

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre>" + _escape("\n".join(code_lines)) + "</pre>")
                code_lines.clear()
                in_code = False
            else:
                flush_all()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue

        if not line.strip():
            flush_all()
            continue

        if _HR_RE.match(line):
            flush_all()
            out.append("<hr>")
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_all()
            level = len(heading.group(1))
            content = heading.group(2).strip()
            if level == 1 and not seen_h1:
                seen_h1 = True
                out.append(
                    '<header class="resume-header">'
                    f'<h1 class="resume-name">{_inline_markup(content)}</h1>'
                    "</header>"
                )
            else:
                out.append(f"<h{level}>{_inline_markup(content)}</h{level}>")
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            _flush_paragraph(paragraph, out)
            bullets.append(bullet.group(1).strip())
            continue

        ordered = _ORDERED_RE.match(line)
        if ordered:
            _flush_paragraph(paragraph, out)
            bullets.append(ordered.group(1).strip())
            continue

        paragraph.append(line.strip())

    if in_code and code_lines:
        out.append("<pre>" + _escape("\n".join(code_lines)) + "</pre>")
    flush_all()

    return "\n".join(_group_header(out))


def _dynamic_css(resume_country: str = "") -> str:
    """Upstream's runtime-injected layer, materialised as static CSS.

    Mirrors ``setDynamicCss()`` in upstream site/src/utils/css.ts, whose
    arithmetic (h2/h3 = lineHeight * 1.154, dl = * 1.038) is reproduced.
    """
    from app.country_resume_profile import get_resume_country_profile

    profile = get_resume_country_profile(resume_country)
    t = {
        **JUNIAN_THEME,
        "fontFamily": profile.font_family,
        "fontSize": profile.font_size,
        "lineHeight": profile.line_height,
        "paragraphSpace": profile.paragraph_space,
        "marginV": profile.margin_v,
        "marginH": profile.margin_h,
    }
    lh = t["lineHeight"]
    i = f"#{PREVIEW_ID}"
    return (
        f"{i} {{ font-family: {t['fontFamily']}, sans-serif; font-size: {t['fontSize']}px; }}"
        f"{i} {{ padding: {t['marginV']}px {t['marginH']}px; }}"
        f"{i} :not(.resume-header-item) > a {{ color: {t['themeColor']} }}"
        f"{i} h1, {i} h2, {i} h3 {{ color: {t['themeColor']} }}"
        f"{i} h1, {i} h2 {{ border-bottom-color: {t['themeColor']} }}"
        f"{i} h1, {i} h2 {{ border-bottom-width: {profile.section_rule_px}px }}"
        f"{i} h1 {{ letter-spacing: {profile.heading_letter_spacing} }}"
        f"{i} h2 {{ margin-top: {t['paragraphSpace']}px }}"
        f"{i} p, {i} li {{ line-height: {lh:.2f} }}"
        f"{i} h2, {i} h3 {{ line-height: {lh * 1.154:.2f} }}"
        f"{i} dl {{ line-height: {lh * 1.038:.2f} }}"
        f"@media print {{ @page {{ size: {t['paper']}; margin: 0; }} }}"
    )


def load_stylesheet(resume_country: str = "") -> str:
    """Return the resume stylesheet scoped to our container id.

    Upstream's template expects to be injected under ``#vue-smart-pages-*``;
    we substitute our own container and append the dynamic layer upstream
    applies at runtime.
    """
    try:
        css = _CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        try:
            return _FALLBACK_CSS_PATH.read_text(encoding="utf-8") + "\n" + _dynamic_css(resume_country)
        except OSError:
            return ""
    css = css.replace("#PREVIEW_SELECTOR", f"#{PREVIEW_ID}")
    return f"{css}\n{_dynamic_css(resume_country)}"


def _document(title: str, body: str, css: str, *, inline_css: bool) -> str:
    safe_title = _escape(title or "Resume")
    if inline_css and css:
        style = f"<style>\n{css}\n</style>"
    else:
        style = '<link rel="stylesheet" href="ats.css">'
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{safe_title}</title>\n"
        f"{style}\n"
        "</head>\n<body>\n"
        f'<main id="{PREVIEW_ID}">\n'
        f"{body}\n"
        "</main>\n"
        "</body>\n</html>\n"
    )


def markdown_to_html(markdown_text: str, title: str = "Resume",
                     *, inline_css: bool = True, css: str | None = None,
                     resume_country: str = "") -> str:
    """Render Markdown into a standalone HTML document.

    ``inline_css=True`` (the default) embeds the stylesheet so the file is
    self-contained — the same property the Junian editor's HTML export has.
    """
    body = render_markdown_body(markdown_text)
    stylesheet = load_stylesheet(resume_country) if css is None else css
    return _document(title, body, stylesheet, inline_css=inline_css)
