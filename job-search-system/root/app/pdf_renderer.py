"""HTML -> PDF rendering for resume artifacts.

Primary path: a headless Chromium page printing the styled HTML to PDF. That
gives real pagination, selectable text, and a layout identical to what the
browser previews — the same approach Junian's editor uses, but server-side.

Fallback path: when Playwright or a browser binary is unavailable, render the
text with the existing PyMuPDF generator (``app.pdf_generator``). The fallback
is unstyled but always produces a valid, ATS-readable PDF, so a missing browser
degrades quality instead of failing the request.

A single browser is reused across renders: launching Chromium costs ~1s, which
would dominate a per-job package build.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False

# Page geometry. Chromium honours the print() options below, not the CSS
# ``@page`` size, when both are present, so these must agree with
# html_renderer.JUNIAN_THEME["paper"].
# A4 = 8.27in x 11.69in. Margins are zero because the Junian template applies
# its own 55px/45px padding on the container; doubling them would shrink the
# text column far more than upstream's own layout.
PAPER_FORMAT = "A4"
PAGE_WIDTH_IN = 8.27
PAGE_HEIGHT_IN = 11.69
PAGE_MARGIN_IN = 0.0

DEFAULT_TIMEOUT_MS = 20_000

# Consecutive launch failures before the primary renderer is disabled outright.
MAX_LAUNCH_FAILURES = 3


class _BrowserSession:
    """Lazily-started, shared Chromium instance guarded by an asyncio lock."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._unavailable = False
        self._launch_failures = 0

    async def page(self):
        """Return a fresh page, or None when Chromium cannot be started."""
        if not PLAYWRIGHT_AVAILABLE or self._unavailable:
            return None
        async with self._lock:
            try:
                if self._playwright is None:
                    self._playwright = await async_playwright().start()
                if self._browser is None or not self._browser.is_connected():
                    self._browser = await self._playwright.chromium.launch(
                        headless=True,
                        args=["--disable-dev-shm-usage", "--no-sandbox"],
                    )
                self._launch_failures = 0
                return await self._browser.new_page()
            except Exception as e:
                # Only give up after repeated failures: a single transient
                # launch error (memory pressure, a busy machine) must not
                # permanently disable the primary renderer, while a genuinely
                # missing browser binary should not cost a launch attempt on
                # every package build.
                self._launch_failures += 1
                logger.warning(
                    "Chromium unavailable for PDF rendering (%s: %s), attempt %d",
                    type(e).__name__, e, self._launch_failures,
                )
                if self._launch_failures >= MAX_LAUNCH_FAILURES:
                    logger.warning(
                        "Chromium disabled after %d failed launches — "
                        "falling back to the text renderer", self._launch_failures,
                    )
                    self._unavailable = True
                await self._reset()
                return None

    async def _reset(self) -> None:
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._playwright = None

    async def close(self) -> None:
        async with self._lock:
            await self._reset()


_session = _BrowserSession()


def browser_available() -> bool:
    """Whether the primary (Chromium) renderer can be attempted."""
    return PLAYWRIGHT_AVAILABLE and not _session._unavailable


async def close_browser() -> None:
    """Release the shared browser. Safe to call when nothing was started."""
    await _session.close()


async def html_to_pdf(html_document: str, *, timeout_ms: int = DEFAULT_TIMEOUT_MS,
                      attempts: int = 3) -> bytes | None:
    """Render an HTML document to PDF bytes, or None when Chromium is unavailable.

    Retries matter: ``Page.pdf: Protocol error (IO.read): Read failed`` is
    reproducible intermittently on Windows (measured 1-in-5 without retries),
    and it is transient — the very next attempt succeeds. Falling back to the
    text renderer on the first hiccup would silently downgrade the layout.
    """
    if not PLAYWRIGHT_AVAILABLE or _session._unavailable:
        return None
    for attempt in range(max(1, attempts)):
        pdf = await _render_once(html_document, timeout_ms)
        if pdf:
            if attempt:
                logger.info("Chromium PDF render succeeded on attempt %d", attempt + 1)
            return pdf
        if _session._unavailable:
            # Browser could not be launched at all — a configuration fact, not
            # a transient error. Stop retrying and let the fallback render.
            return None
        await asyncio.sleep(0.2)
    return None


async def _render_once(html_document: str, timeout_ms: int) -> bytes | None:
    page = await _session.page()
    if page is None:
        return None
    try:
        await page.set_content(html_document, wait_until="load", timeout=timeout_ms)
        # Let webfonts settle before pagination; print CSS resolves layout here.
        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        return await page.pdf(
            format=PAPER_FORMAT,
            print_background=True,
            margin={
                "top": f"{PAGE_MARGIN_IN}in",
                "bottom": f"{PAGE_MARGIN_IN}in",
                "left": f"{PAGE_MARGIN_IN}in",
                "right": f"{PAGE_MARGIN_IN}in",
            },
        )
    except Exception as e:
        logger.warning("Chromium PDF render failed (%s: %s)", type(e).__name__, e)
        return None
    finally:
        try:
            await page.close()
        except Exception:
            pass


def _fallback_pdf(plain_text: str, title: str, name: str = "") -> bytes:
    """Text-based PDF via the existing PyMuPDF generator."""
    from app.pdf_generator import generate_resume_pdf

    return generate_resume_pdf(plain_text, name=name)


async def markdown_to_pdf(markdown_text: str, *, title: str = "Resume",
                          plain_text: str | None = None,
                          name: str = "",
                          resume_country: str = "") -> tuple[bytes, str]:
    """Render Markdown to PDF.

    Returns ``(pdf_bytes, renderer)`` where renderer is ``"chromium"`` or
    ``"text"``, so callers can record which path produced the artifact.
    """
    from app.html_renderer import markdown_to_html
    from app.ats_resume import resume_text_to_markdown  # noqa: F401  (documented sibling)

    document = markdown_to_html(markdown_text, title, resume_country=resume_country)
    pdf = await html_to_pdf(document)
    if pdf:
        return pdf, "chromium"
    return _fallback_pdf(plain_text if plain_text is not None else markdown_text,
                         title, name=name), "text"
