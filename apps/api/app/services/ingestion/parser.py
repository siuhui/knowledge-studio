"""Document parsers: convert raw bytes → Markdown.

All parsers produce Markdown so the chunker has a uniform input format:
headings as ``#`` / ``##``, fenced code blocks as `` ``` ``, etc.
"""

import re
from collections import Counter
from typing import Protocol

import charset_normalizer
import fitz  # PyMuPDF
import trafilatura


class Parser(Protocol):
    def parse(self, raw_bytes: bytes) -> str: ...


class PdfParser:
    _HEADING_FONT_SIZE_RATIO = 1.15  # body × this → heading candidate
    _HEADING_MAX_LENGTH = 140        # characters — headings are short
    _MIN_BODY_SIZE = 8               # ignore tiny fonts (footnotes, watermarks)

    def parse(self, raw_bytes: bytes) -> str:
        """Extract text from PDF, emitting ``#``-prefixed headings.

        Heading detection uses per-page heuristics:

        1. Find the most common font size on the page (the body size).
        2. Any short line whose size ≥ body size × ratio is a heading.
        3. Bold short lines slightly larger than body are also headings.

        Spans from all pages are collected first, then rendered to Markdown
        in a single pass — this avoids introducing artificial paragraph
        breaks at page boundaries.
        """
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        try:
            all_spans: list[dict] = []
            all_sizes: list[float] = []

            for page in doc:
                page_dict = page.get_text("dict")
                blocks = page_dict["blocks"]
                page_spans = self._collect_spans(blocks)
                if not page_spans:
                    continue
                page_sizes = [s["size"] for s in page_spans if s["size"] >= self._MIN_BODY_SIZE]
                all_sizes.extend(page_sizes or [s["size"] for s in page_spans])
                all_spans.extend(page_spans)

            if not all_spans:
                return ""

            body_size = _most_common(all_sizes)
            heading_threshold = body_size * self._HEADING_FONT_SIZE_RATIO

            return self._spans_to_markdown(all_spans, heading_threshold, body_size)
        finally:
            doc.close()

    @staticmethod
    def _collect_spans(blocks: list[dict]) -> list[dict]:
        """Flatten blocks → lines → spans, keeping layout metadata."""
        spans: list[dict] = []
        for block in blocks:
            if block.get("type") != 0:
                continue  # skip images, etc.
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    spans.append({
                        "text": text,
                        "size": round(span.get("size", 10), 1),
                        "font": span.get("font", ""),
                        "flags": span.get("flags", 0),
                    })
        return spans

    def _spans_to_markdown(self, spans: list[dict], heading_threshold: float, body_size: float) -> str:
        """Render spans as Markdown lines, upgrading headings."""
        lines: list[str] = []
        for s in spans:
            text = s["text"]
            size = s["size"]
            bold = bool(s["flags"] & 2)  # PDF flag bit 2 = bold

            is_heading = (
                size >= heading_threshold
                or (bold and size > body_size)
            ) and len(text) < self._HEADING_MAX_LENGTH

            if is_heading:
                # Estimate level: bigger font → shallower level
                ratio = size / max(body_size, 1)
                if ratio >= 1.6:
                    level = 1
                elif ratio >= 1.35:
                    level = 2
                else:
                    level = 3
                lines.append(f"{'#' * level} {text}")
            else:
                lines.append(text)

        return "\n".join(lines)


class MarkdownParser:
    def parse(self, raw_bytes: bytes) -> str:
        """Clean Markdown: strip YAML frontmatter and image links.

        Inline links [text](url) are preserved — they carry semantic signal
        for both embeddings and LLM readers.
        """
        text = _decode_text(raw_bytes)
        text = _strip_frontmatter(text)

        # Remove image syntax: ![alt](url) — the URL is useless for retrieval
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

        return text


class TextParser:
    def parse(self, raw_bytes: bytes) -> str:
        """Decode plain text with charset detection.  Plain text is valid Markdown."""
        return _decode_text(raw_bytes)


class HtmlParser:
    def parse(self, raw_bytes: bytes) -> str:
        """Extract main content from HTML as Markdown."""
        text = trafilatura.extract(
            raw_bytes,
            include_links=False,
            include_formatting=True,
            include_tables=True,
            output_format="markdown",
        )
        return text or ""


def _decode_text(raw_bytes: bytes) -> str:
    """Decode bytes to string, trying detected encoding with fallback."""
    detected = charset_normalizer.from_bytes(raw_bytes)
    if detected:
        best = detected.best()
        if best:
            return str(best)
    # Fallback: try UTF-8, then GB18030
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort
    return raw_bytes.decode("utf-8", errors="replace")


def _most_common(values: list[float]) -> float:
    """Return the most frequent value, rounded to 1 decimal place.

    The most common font size on a page is almost always the body text size.
    Falls back to the minimum when there's no clear winner (e.g. equal counts).
    """
    rounded = [round(v, 1) for v in values]
    [(value, _count)] = Counter(rounded).most_common(1)
    return value


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from markdown text."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].lstrip()
    return text


PARSERS: dict[str, Parser] = {
    "pdf": PdfParser(),
    "markdown": MarkdownParser(),
    "text": TextParser(),
    "html": HtmlParser(),
}
