"""HTML -> DOCX, so Word output derives from the same HTML as the PDF.

Junian Markdown Resume derives its DOCX from the rendered HTML document
(`html-docx-js-typescript` on the HTML), which is why its DOCX and PDF always
agree. Ours previously rebuilt DOCX from plain text with guessed headings, so
the two formats could drift apart.

This module closes that gap without a dependency: we already emit a narrow,
known HTML subset (``app.html_renderer``), so we parse it with the stdlib
``html.parser`` and emit ``python-docx`` paragraphs. Because the input is
ours, there is no need for a general-purpose HTML-to-Word converter.

Layout mirrors ``app/ats_template/ats.css``: same page size, same margins,
same heading/body sizes — so Word and PDF render alike.
"""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from app.country_resume_profile import get_resume_country_profile

# Keep in sync with app/pdf_renderer and app/ats_template/ats.css.
PAGE_MARGIN_IN = 0.52

_FONT = "Verdana"
_BODY_SIZE = 8.2
_HEADING1_SIZE = 16
_HEADING2_SIZE = 10
_HEADING3_SIZE = 8.6
_SMALL_SIZE = 7.6

_INK = RGBColor(0x1A, 0x1A, 0x1A)
_MUTED = RGBColor(0x44, 0x44, 0x44)

_HEADINGS = {"h1": _HEADING1_SIZE, "h2": _HEADING2_SIZE, "h3": _HEADING3_SIZE,
             "h4": _HEADING3_SIZE, "h5": 10.5, "h6": 10.5}

# Elements whose *text* must never become document content. The renderer
# inlines ats.css into <style>; without skipping it the stylesheet's comments
# were emitted as a paragraph right under the candidate's name.
#
# Deliberately only paired tags: <meta>/<link> are void elements with no end
# tag, so pushing them would leave the stack unbalanced and swallow the body.
_SKIP = {"head", "title", "style", "script"}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def _set_cell_spacing(paragraph, *, before=0, after=0, line=1.0) -> None:
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = line


def _add_bottom_border(paragraph, *, size="6", color="000000") -> None:
    """Add a Word paragraph bottom rule, matching Junian's section lines."""
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = p_bdr.find(qn("w:bottom"))
    if bottom is None:
        bottom = OxmlElement("w:bottom")
        p_bdr.append(bottom)
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)


class _DocumentBuilder(HTMLParser):
    """Accumulate paragraphs and runs from our HTML subset."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.block_tag: str | None = None   # current block element ("p","h1"...)
        self.list_stack: list[str] = []     # "ul" / "ol"
        self.skip_stack: list[str] = []     # head/style/script/title we must ignore
        self.style: list[str] = []          # inline emphasis: b/i/code/a
        self.text: list[str] = []           # text of the current block
        self.out: list[tuple] = []          # (kind, payload)
        self._heading: str | None = None

    # -- element boundaries -------------------------------------------
    def handle_starttag(self, tag, attrs):
        if self.skip_stack:
            # Nested inside head/style/script/title: only track its own closing
            # tag so the depth counter stays balanced.
            if tag in _SKIP:
                self.skip_stack.append(tag)
            return
        if tag in _SKIP:
            self._flush_block()
            self.skip_stack.append(tag)
            return
        if tag in ("ul", "ol"):
            self.list_stack.append(tag)
            return
        if tag == "li":
            self._flush_block()
            self.block_tag = "li"
            self.text = []
            return
        if tag in _HEADINGS or tag == "p":
            self._flush_block()
            self.block_tag = tag
            self._heading = tag if tag in _HEADINGS else None
            self.text = []
            return
        if tag == "br":
            self.text.append("\n")
            return
        if tag == "hr":
            self._flush_block()
            return
        if tag in ("strong", "b"):
            self.style.append("b")
        elif tag in ("em", "i"):
            self.style.append("i")
        elif tag == "code":
            self.style.append("code")
        elif tag == "a":
            self.style.append("a")

    def handle_endtag(self, tag):
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            elif tag in self.skip_stack:
                # Unbalanced markup: unwind to the matching level.
                while self.skip_stack and self.skip_stack[-1] != tag:
                    self.skip_stack.pop()
                if self.skip_stack:
                    self.skip_stack.pop()
            return
        if tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            return
        if tag == "li" or tag in _HEADINGS or tag == "p":
            self._flush_block()
            return
        if tag in ("strong", "b", "em", "i", "code", "a"):
            if self.style and self.style[-1] == ("i" if tag in ("em", "i") else
                                                 ("b" if tag in ("strong", "b") else tag)):
                self.style.pop()

    def handle_data(self, data):
        if self.skip_stack:
            return                       # stylesheet / title / script text
        # convert_charrefs=True already decoded entities; decoding again here
        # would corrupt literal text such as "&amp;amp;".
        if self.block_tag is None:
            # Text outside any block (shouldn't happen with our renderer),
            # but never drop it silently.
            if data.strip():
                self.block_tag = "p"
                self._heading = None
                self.text = [data]
            return
        self.text.append(data)

    # -- emit ----------------------------------------------------------
    def _flush_block(self) -> None:
        if self.block_tag is None:
            return
        raw = "".join(self.text)
        content = raw if self.block_tag == "li" else _collapse(raw)
        if self.block_tag == "li" and content.strip():
            self.out.append(("li", content.strip()))
        elif content.strip() or self.block_tag in _HEADINGS:
            self.out.append(("heading" if self._heading else "para",
                             (self._heading, content.strip())))
        self.block_tag = None
        self._heading = None
        self.text = []


def _runs(paragraph, text: str, *, base_bold: bool = False,
          base_size: float = _BODY_SIZE, base_color=None, font: str = _FONT):
    """Split on * and emit runs; ** is already resolved by our renderer."""
    parts = re.split(r"(\*[^*]+\*)", text)
    for part in parts:
        if not part:
            continue
        italic = part.startswith("*") and part.endswith("*") and len(part) > 2
        run = paragraph.add_run(part[1:-1] if italic else part)
        run.font.name = font
        run.font.size = Pt(base_size)
        if base_bold or italic:
            run.font.bold = True
        if base_color is not None:
            run.font.color.rgb = base_color
    if not paragraph.runs:
        paragraph.add_run(text)


def generate_docx_from_html(html_document: str, *, name: str = "",
                            paper: str = "Letter",
                            resume_country: str = "") -> bytes:
    """Convert our rendered HTML into a DOCX document (OOXML bytes)."""
    parser = _DocumentBuilder()
    # The parser only needs the body; feeding the whole document is fine
    # because head/style are in _IGNORED.
    parser.feed(html_document or "")
    parser.close()
    if not parser.out:
        parser.out.append(("para", ("p", _collapse(html_document))))

    profile = get_resume_country_profile(resume_country)
    font = profile.font_family or _FONT
    body_size = max(7.8, profile.font_size - 2.0)
    small_size = max(7.0, body_size - 0.6)
    heading1_size = 16 if profile.font_size >= 11 else 15
    heading2_size = max(9.2, body_size + 1.4)
    heading3_size = max(8.2, body_size + 0.4)
    heading_sizes = dict(_HEADINGS)
    heading_sizes.update({"h1": heading1_size, "h2": heading2_size, "h3": heading3_size})
    margin_in = max(0.35, min(0.62, profile.margin_h / 96))

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(body_size)
    normal.font.color.rgb = _INK

    for section in doc.sections:
        section.top_margin = Inches(margin_in)
        section.bottom_margin = Inches(margin_in)
        section.left_margin = Inches(margin_in)
        section.right_margin = Inches(margin_in)

    doc.core_properties.title = f"Resume - {name}" if name else "Resume"
    doc.core_properties.author = name or ""

    first_heading = True
    for kind, payload in parser.out:
        if kind == "li":
            para = doc.add_paragraph(style="List Bullet")
            _runs(para, payload, base_size=body_size, base_color=_INK, font=font)
            para.paragraph_format.left_indent = Inches(0.18)
            para.paragraph_format.first_line_indent = Inches(-0.08)
            _set_cell_spacing(para, after=0.5, line=1.0)
            continue

        heading_tag, text = payload
        if kind == "heading" and heading_tag in heading_sizes:
            size = heading_sizes[heading_tag]
            para = doc.add_paragraph()
            # The first heading in the document is the candidate's name.
            is_name = first_heading and heading_tag == "h1"
            first_heading = False
            para.alignment = (WD_ALIGN_PARAGRAPH.CENTER if is_name
                              else WD_ALIGN_PARAGRAPH.LEFT)
            _runs(para, text, base_bold=True, base_size=size,
                  base_color=_INK if heading_tag == "h1" else _INK, font=font)
            if is_name:
                _set_cell_spacing(para, before=2, after=2, line=1.0)
                _add_bottom_border(para, size="6")
                for run in para.runs:
                    run.font.bold = True
            elif heading_tag == "h2":
                _set_cell_spacing(para, before=5, after=2, line=1.0)
                _add_bottom_border(para, size="6")
            elif heading_tag == "h3":
                _set_cell_spacing(para, before=5, after=1, line=1.0)
            else:
                _set_cell_spacing(para, before=3, after=1, line=1.0)
            para.paragraph_format.keep_with_next = True
            continue

        para = doc.add_paragraph()
        # Contact lines and small print render slightly smaller, as in CSS.
        is_header_line = first_heading is False and "|" in text and len(text) < 180
        small = is_header_line or (len(text) > 80 and "|" in text and not text.startswith("*"))
        if is_header_line:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _runs(para, text, base_size=small_size if small else body_size,
              base_color=_MUTED if small else _INK, font=font)
        _set_cell_spacing(para, after=1.5 if small else 2, line=1.0)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_docx_from_markdown(markdown_text: str, *, name: str = "",
                                paper: str = "Letter",
                                resume_country: str = "") -> bytes:
    """Render Markdown to DOCX via the same HTML the PDF renderer uses."""
    from app.html_renderer import markdown_to_html

    document = markdown_to_html(
        markdown_text or "", title=name or "Resume", resume_country=resume_country)
    return generate_docx_from_html(
        document, name=name, paper=paper, resume_country=resume_country)
