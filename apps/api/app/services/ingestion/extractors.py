"""Web content extraction: trafilatura with Playwright fallback for JS-rendered pages."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

import structlog
import trafilatura
from playwright.sync_api import Route, sync_playwright

from app.core.security import BLOCKED_NETWORKS
from app.core.telemetry import observe

logger = structlog.get_logger(__name__)


@dataclass
class WebExtractionResult:
    text: str
    title: str
    method: str  # "trafilatura" | "playwright"
    metadata: dict[str, Any] = field(default_factory=dict)


class WebExtractionError(Exception):
    def __init__(self, *, url: str, message: str):
        self.url = url
        self.message = message
        super().__init__(message)


class WebExtractor:
    """Extract main content from web pages.

    Primary path: trafilatura (fast, no browser).
    Fallback: Playwright (renders JS, then trafilatura on rendered HTML).

    Fallback triggers when trafilatura extracts less than 20% of the
    raw HTML's visible text — a signal that content is JS-rendered.
    """

    def __init__(self, fallback_ratio: float = 0.2):
        self.fallback_ratio = fallback_ratio

    @observe(name="ingestion.web_extract", capture_input=False, capture_output=False)
    def extract(self, url: str, html_bytes: bytes) -> WebExtractionResult:
        """Extract content from fetched HTML bytes.

        Returns WebExtractionResult with method indicating which path succeeded.
        Raises WebExtractionError if both paths fail.
        """
        # Decode bytes to string
        try:
            html = html_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html = html_bytes.decode("latin-1")

        # Step 1: trafilatura
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            output_format="txt",
        )

        if not _should_fallback(text, html, self.fallback_ratio):
            title = _extract_html_title(html) or _derive_title_from_url(url)
            logger.info("trafilatura extraction succeeded", url=url, word_count=len(text.split()) if text else 0)
            return WebExtractionResult(
                text=(text or "").strip(),
                title=title,
                method="trafilatura",
            )

        logger.info("trafilatura likely missed JS content, falling back to Playwright", url=url)

        # Step 2: Playwright fallback
        try:
            rendered_html = _render_with_playwright(url, self._block_internal_ips)
        except Exception as e:
            logger.warning("Playwright rendering failed", url=url, error=str(e))
            # If trafilatura got something, return it as best-effort
            if text and text.strip():
                title = _extract_html_title(html) or _derive_title_from_url(url)
                return WebExtractionResult(
                    text=text.strip(),
                    title=title,
                    method="trafilatura",
                )
            raise WebExtractionError(url=url, message=f"Both trafilatura and Playwright failed: {e}")

        # Re-extract with trafilatura on rendered HTML
        rendered_text = trafilatura.extract(
            rendered_html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            output_format="txt",
        )

        if not rendered_text or not rendered_text.strip():
            raise WebExtractionError(url=url, message="Playwright rendered but trafilatura still got no content")

        # Extract title from rendered page
        title = _extract_html_title(rendered_html) or _derive_title_from_url(url)
        logger.info("Playwright extraction succeeded", url=url, word_count=len(rendered_text.split()))

        return WebExtractionResult(
            text=rendered_text.strip(),
            title=title,
            method="playwright",
        )

    @staticmethod
    def _block_internal_ips(route: Route) -> None:
        """Playwright route handler — block requests to internal IPs."""
        url = route.request.url
        hostname = urlparse(url).hostname
        if hostname:
            try:
                ip = ip_address(hostname)
            except ValueError:
                pass
            else:
                if any(ip in net for net in BLOCKED_NETWORKS):
                    route.abort()
                    return
        route.continue_()


def _should_fallback(extracted_text: str | None, raw_html: str, fallback_ratio: float) -> bool:
    """Decide whether to fall back to Playwright.

    Returns True when trafilatura likely missed JS-rendered content.
    Uses ratio of extracted text to raw HTML visible text, not an absolute
    word count — so genuinely short pages don't trigger unnecessary fallback.
    """
    if not extracted_text or not extracted_text.strip():
        return True

    html_text = _strip_tags(raw_html)
    html_words = len(html_text.split())
    extracted_words = len(extracted_text.split())

    if html_words > 50 and extracted_words < html_words * fallback_ratio:
        return True
    return False


def _strip_tags(html: str) -> str:
    """Remove HTML tags and normalize whitespace, leaving visible text."""
    # Remove script and style content
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_html_title(html: str) -> str | None:
    """Extract <title> content from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _derive_title_from_url(url: str) -> str:
    """Derive a readable title from a URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path:
        filename = path.rsplit("/", 1)[-1]
        if filename:
            return filename
    return parsed.netloc.replace("www.", "")


def _render_with_playwright(url: str, block_handler: Callable[[Route], None]) -> str:
    """Render a page with Playwright and return the full HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
        )
        page = context.new_page()

        page.route("**/*", block_handler)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
        finally:
            context.close()
            browser.close()

    return html
