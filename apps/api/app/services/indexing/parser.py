"""Document parsers: convert raw bytes → plain text.

Parser Protocol + format registry. v0.1.0 supports PDF, Markdown, plain text.
"""

from typing import Protocol

import fitz  # PyMuPDF
import charset_normalizer


class Parser(Protocol):
    def parse(self, raw_bytes: bytes) -> str: ...


class PdfParser:
    def parse(self, raw_bytes: bytes) -> str:
        """Extract text from PDF using PyMuPDF."""
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        try:
            pages = []
            for page in doc:
                text = page.get_text()
                if text.strip():
                    pages.append(text)
            return "\n\n".join(pages)
        finally:
            doc.close()


class MarkdownParser:
    def parse(self, raw_bytes: bytes) -> str:
        """Extract text from Markdown, removing frontmatter and image links."""
        text = _decode_text(raw_bytes)

        # Remove YAML frontmatter
        text = _strip_frontmatter(text)

        # Remove image syntax: ![alt](url) and ![alt](url "title")
        import re
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

        # Remove inline links but keep text: [text](url) → text
        text = re.sub(r"\[([^\]]*?)\]\(.*?\)", r"\1", text)

        return text


class TextParser:
    def parse(self, raw_bytes: bytes) -> str:
        """Decode plain text with charset detection."""
        return _decode_text(raw_bytes)


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


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from markdown text."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].lstrip()
    return text


PARSERS: dict[str, Parser] = {
    "pdf": PdfParser(),
    "markdown": MarkdownParser(),
    "text": TextParser(),
}
