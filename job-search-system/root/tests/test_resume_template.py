"""Regression tests for the Junian markdown-resume template integration.

The backbone CSS is stored verbatim, including upstream's
``#PREVIEW_SELECTOR`` placeholder. These tests pin the three things that make
it work here: the placeholder is substituted, the runtime-injected layer is
supplied as static CSS, and the resume body is wrapped in the matching <main>.
"""
import re

from app import html_renderer
from app.html_renderer import (PREVIEW_ID, load_stylesheet, markdown_to_html,
                               render_markdown_body)

MD = "# Jane Doe\n\n**Engineer**\n\nCity | jane@example.com\n\n## Work\n\n- Did work.\n"


def test_stylesheet_placeholder_is_substituted():
    css = load_stylesheet()
    assert "PREVIEW_SELECTOR" not in css
    assert f"#{PREVIEW_ID}" in css


def test_dynamic_layer_supplies_what_the_backbone_css_omits():
    """Upstream injects font/size/colour/page via setDynamicCss at runtime.

    Without this layer the backbone CSS alone renders in the browser default
    font, because it declares no font-family or font-size at all.
    """
    css = load_stylesheet()
    assert "Verdana" in css                       # DEFAULT_STYLES.fontEN
    assert f"font-size: {html_renderer.JUNIAN_THEME['fontSize']}px" in css
    assert "line-height: 1.30" in css             # lineHeight 1.3
    assert f"margin-top: {html_renderer.JUNIAN_THEME['paragraphSpace']}px" in css
    assert f"size: {html_renderer.JUNIAN_THEME['paper']}" in css
    assert html_renderer.JUNIAN_THEME["paper"] == "A4"


def test_country_profiles_change_the_dynamic_css():
    from app.country_resume_profile import country_resume_guidance

    sg_css = load_stylesheet("Singapore")
    de_css = load_stylesheet("Germany")

    assert "Singapore style" in country_resume_guidance("Singapore")
    assert "Lebenslauf-like" in country_resume_guidance("Germany")
    assert "font-size: 11px" in sg_css
    assert "font-size: 10px" in de_css
    assert sg_css != de_css


def test_markdown_html_uses_country_profile_css():
    html = markdown_to_html(MD, title="Resume", resume_country="Singapore")
    assert "font-family: Arial, sans-serif" in html
    assert "font-size: 11px" in html


def test_paper_geometry_agrees_between_css_and_pdf_renderer():
    """Chromium honours print() options over CSS @page, so they must match."""
    from app.pdf_renderer import PAPER_FORMAT

    assert PAPER_FORMAT == html_renderer.JUNIAN_THEME["paper"]


def test_body_is_wrapped_in_the_container_the_css_targets():
    html = markdown_to_html(MD, title="Resume")
    assert f'<main id="{PREVIEW_ID}">' in html
    assert "</main>" in html


def test_no_double_separators_from_the_css_after_rule():
    """`::after { content: " | " }` must never arm alongside real text.

    Upstream draws separators in CSS from ``.resume-header-item`` elements.
    Our generator writes them into the Markdown instead, so every element
    carrying that class must also carry ``no-separator`` — otherwise the
    reader sees doubled pipes.
    """
    body = render_markdown_body(MD)
    items = re.findall(r'class="([^"]*resume-header-item[^"]*)"', body)
    assert items, "header items should exist to exercise the rule"
    for classes in items:
        assert "no-separator" in classes.split(), (
            f"header item would double its pipes: {classes!r}")
    assert " | " in body          # the separator is real text


def test_headline_and_contact_are_inside_the_centred_header():
    """The template centres `.resume-header`, so the block must be whole.

    Upstream's Markdown carries the name and the contact lines in one header
    element. Ours has them as sibling paragraphs, so without grouping the name
    centres and everything under it stays left-aligned.
    """
    body = render_markdown_body(
        "\n".join(["# Jane Doe", "", "**Engineer**", "",
                   "City | jane@example.com", "", "## Work", "", "- Did work."]))
    header = re.search(r'<header class="resume-header">(.*?)</header>', body, re.S)
    assert header, "no header element"
    assert "Engineer" in header.group(1)
    assert "jane@example.com" in header.group(1)
    # And nothing after the name leaks out of the header block.
    assert header.group(1).count("<p") == 2


def test_header_element_the_template_styles_is_emitted():
    """Their CSS targets `.resume-header h1`; the renderer must produce it."""
    body = render_markdown_body(MD)
    assert '<header class="resume-header">' in body


def test_grouping_leaves_documents_without_an_h1_untouched():
    body = render_markdown_body("\n".join(["## Work", "", "- Did work."]))
    assert "<header" not in body
