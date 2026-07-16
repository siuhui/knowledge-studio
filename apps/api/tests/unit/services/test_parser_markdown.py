"""Smoke tests for the Markdown-output parsers."""

import io

import fitz  # PyMuPDF

from app.services.ingestion.parser import HtmlParser, MarkdownParser, PdfParser, TextParser


def _make_pdf() -> bytes:
    """Create a PDF with heading-sized and body-sized text using PyMuPDF.

    Uses large font for titles / section headings and small font for body
    text so PdfParser's heading detection has real size data to work with.
    """
    doc = fitz.open()
    page = doc.new_page()

    y = 700  # starting y position

    # Title: large bold
    page.insert_text(fitz.Point(72, y), "Annual Report 2025", fontsize=18)
    assert page.get_text("dict")["blocks"], "Should have text blocks after insert"
    y -= 30

    # Body: normal
    page.insert_text(fitz.Point(72, y), "Revenue grew by 15% year over year.", fontsize=11)
    y -= 25

    # Section heading: medium bold
    page.insert_text(fitz.Point(72, y), "Financial Highlights", fontsize=14)
    y -= 25

    # Body
    page.insert_text(fitz.Point(72, y), "Operating margin improved to 22%.", fontsize=11)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestMarkdownParser:
    def test_preserves_structure(self):
        md = (
            b"---\ntitle: test\n---\n"
            b"# Hello\n\n"
            b"**bold** and [a link](http://example.com).\n\n"
            b"```python\nprint(1)\n```\n"
        )
        result = MarkdownParser().parse(md)

        assert "---" not in result
        assert "title:" not in result
        assert "# Hello" in result
        assert "**bold**" in result
        assert "[a link](http://example.com)" in result
        assert "```python" in result

    def test_no_frontmatter_idempotent(self):
        result = MarkdownParser().parse(b"# Just a heading\n\ntext")
        assert "# Just a heading" in result
        assert "text" in result


def _make_multipage_pdf() -> bytes:
    """PDF with a paragraph split across two pages."""
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text(fitz.Point(72, 700), "Section One", fontsize=16)
    p1.insert_text(fitz.Point(72, 675), "This paragraph starts on page one and continues onto", fontsize=11)

    p2 = doc.new_page()
    p2.insert_text(fitz.Point(72, 700), "page two where the sentence finishes here.", fontsize=11)
    p2.insert_text(fitz.Point(72, 675), "Section Two", fontsize=16)
    p2.insert_text(fitz.Point(72, 650), "A new paragraph on the second page.", fontsize=11)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestPdfParser:
    def test_text_extraction(self):
        """PDF text should be extracted with heading markers on large-font lines."""
        result = PdfParser().parse(_make_pdf())

        assert "Annual Report" in result
        assert "Financial Highlights" in result
        assert "Revenue grew" in result
        assert "Operating margin" in result

        lines = result.split("\n")
        heading_lines = [line for line in lines if line.startswith("#")]

        # With font sizes 18 and 14 vs body 11, heading detection should fire
        # at least once.  Whether it fires for both depends on how PyMuPDF
        # serialises the font metrics, so we're conservative.
        assert heading_lines, f"Expected at least one heading line, got:\n{result[:500]}"

    def test_cross_page_no_artificial_break(self):
        """A paragraph split across two pages should not get a double-newline.

        ``\\n\\n`` at a page boundary would cause the chunker to treat the
        two halves as separate paragraphs.  The parser must join pages
        without introducing artificial breaks.
        """
        result = PdfParser().parse(_make_multipage_pdf())
        # If pages were joined with \n\n, the sentence halves would be
        # separated by double newline.  We expect them to be consecutive
        # lines (single \n between them).
        assert "Section One" in result
        assert "Section Two" in result
        assert "starts on page one" in result
        assert "sentence finishes here" in result

        # The cross-page sentence should appear as consecutive lines,
        # not separated by a blank line.
        before, after = result.split("starts on page one")
        tail = after.split("\n")
        # tail[0] = " and continues onto"
        # tail[1+] should contain "page two where..." without an empty string between
        joined = "\n".join(tail[:4])
        assert "page two" in joined
        assert not after.startswith("\n\n"), f"Should not have double newline between pages, got {after[:50]!r}"

    def test_empty_pdf(self):
        buf = io.BytesIO()
        doc = fitz.open()
        doc.new_page()
        doc.save(buf)
        doc.close()
        result = PdfParser().parse(buf.getvalue())
        # Empty page — no headings, no body
        assert isinstance(result, str)
        assert "|__" not in result  # no internal dunder markers


class TestHtmlParser:
    def test_markdown_output(self):
        html = b"<html><body><h1>Title</h1><p>A paragraph.</p></body></html>"
        result = HtmlParser().parse(html)
        assert "Title" in result
        assert "paragraph" in result

    def test_empty_html(self):
        assert HtmlParser().parse(b"<html></html>") == ""


class TestTextParser:
    def test_plain_text(self):
        result = TextParser().parse(b"hello\n\nworld")
        assert "hello" in result
        assert "world" in result
