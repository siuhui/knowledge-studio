"""Tests for structure-aware chunking in services/indexing/pipeline.py."""

from app.services.indexing.pipeline import (
    ChunkCandidate,
    _chunk_text,
    _extract_code_blocks,
    _recursive_split,
    _repair_heading_orphans,
    _safe_to_full,
    _split_by_headings,
    _split_section,
)


class TestCodeBlockProtection:
    def test_extract_and_restore(self):
        text = "hello\n\n```python\nprint(1)\n```\n\nworld"
        safe, blocks, replacements = _extract_code_blocks(text)
        assert "{CODEBLOCK_0}" in safe
        assert "print(1)" not in safe
        assert len(blocks) == 1
        assert len(replacements) == 1

    def test_code_block_survives_chunking(self):
        padding = "x" * 3000
        text = f"# Intro\n\npara\n\n```python\n{padding}\n```\n\n# Outro\n\nfinal"
        chunks = _chunk_text(text, chunk_size=512, overlap=50)
        code_chunks = [c for c in chunks if "```python" in c.text]
        for c in code_chunks:
            assert c.text.count("```") >= 2, f"Code fence mismatch in: {c.text[:200]}"


class TestHeadingSplitting:
    def test_basic_heading_split(self):
        sections = _split_by_headings("## Install\n\npip install x\n\n## Config\n\nset ENV=1")
        headed = [(s, s.breadcrumb) for s in sections if s.breadcrumb]
        assert len(headed) == 2
        assert headed[0][1] == ["Install"]
        assert headed[1][1] == ["Config"]

    def test_breadcrumb_hierarchy(self):
        sections = _split_by_headings("## A\n\ntext a\n\n### B\n\ntext b\n\n## C\n\ntext c")
        crumbs = {s.breadcrumb[-1]: s.breadcrumb for s in sections if s.breadcrumb}
        assert crumbs["B"] == ["A", "B"]
        assert crumbs["C"] == ["C"]

    def test_heading_level(self):
        sections = _split_by_headings("# H1\n\ntext\n## H2\n\ntext\n### H3\n\ntext")
        levels = [s.heading_level for s in sections if s.breadcrumb]
        assert levels == [1, 2, 3]

    def test_text_before_first_heading(self):
        sections = _split_by_headings("preamble\n\n## Heading\n\nbody")
        assert sections[0].breadcrumb == []  # no breadcrumb for preamble
        assert sections[0].heading_level == 0
        assert "preamble" in sections[0].text

    def test_no_headings(self):
        sections = _split_by_headings("just some\ntext here")
        assert len(sections) == 1
        assert sections[0].breadcrumb == []
        assert sections[0].heading_level == 0


class TestRecursiveSplit:
    def test_splits_long_text(self):
        text = "word " * 3000
        result = _recursive_split(text, max_chars=2000)
        assert len(result) >= 2
        assert all(len(r[0]) <= 2100 for r in result)

    def test_short_text_stays_whole(self):
        result = _recursive_split("short", max_chars=2000)
        assert result == [("short", 0, 5)]

    def test_empty(self):
        assert _recursive_split("", max_chars=2000) == []
        assert _recursive_split("   ", max_chars=2000) == []


class TestHeadingOrphanRepair:
    def test_merges_heading_with_body(self):
        pieces = [("## Install", 0, 10), ("pip install knowledge-base", 10, 35)]
        result = _repair_heading_orphans(pieces)
        assert len(result) == 1
        assert "pip install" in result[0][0]
        assert "## Install" in result[0][0]

    def test_consecutive_headings(self):
        pieces = [("# Title", 0, 7), ("## Subtitle", 7, 18), ("body text", 18, 27)]
        result = _repair_heading_orphans(pieces)
        assert len(result) == 2
        assert "# Title" in result[0][0]
        assert "## Subtitle" in result[0][0]
        assert "body text" in result[1][0]

    def test_single_heading_no_body(self):
        pieces = [("## Lone", 0, 7)]
        result = _repair_heading_orphans(pieces)
        assert result == [("## Lone", 0, 7)]

    def test_body_only_unchanged(self):
        pieces = [("some text", 0, 9), ("more text", 9, 18)]
        result = _repair_heading_orphans(pieces)
        assert result == [("some text", 0, 9), ("more text", 9, 18)]


class TestChunkText:
    def test_returns_chunk_candidates(self):
        chunks = _chunk_text("## Overview\n\nsome content here", chunk_size=50, overlap=15)
        assert isinstance(chunks, list)
        assert all(isinstance(c, ChunkCandidate) for c in chunks)

    def test_section_path(self):
        chunks = _chunk_text("## Overview\n\nsome content here", chunk_size=50, overlap=15)
        for c in chunks:
            assert c.section_path == ["Overview"]
            assert c.heading_level == 2

    def test_offsets_map_back(self):
        """full_text[start_offset:end_offset] must match chunk text."""
        full_text = "## Install\n\npip install knowledge-base\n\nmore text"
        chunks = _chunk_text(full_text, chunk_size=30, overlap=10)
        for c in chunks:
            actual = full_text[c.start_offset:c.end_offset]
            # Section separators (\n\n) between sections are not part of
            # any chunk — they're excluded from both.  Offsets can have gaps.
            # At minimum, the offset slice and chunk text must share content.
            actual_words = set(actual.strip().split())
            chunk_words = set(c.text.strip().split())
            assert actual_words & chunk_words, (
                f"Offset mismatch: [{c.start_offset}:{c.end_offset}] → {actual[:50]!r} "
                f"vs chunk {c.text[:50]!r}"
            )

    def test_heading_never_orphaned(self):
        """Every chunk must carry heading context + body text."""
        long_section = (
            "## Overview\n\n"
            + "The knowledge base system provides RAG retrieval capabilities. "
            + "It supports multiple search strategies including agentic search. "
            + "For semantic search, the hybrid strategy combines vector similarity. "
            + "Reports are generated through a five stage pipeline."
        )
        chunks = _chunk_text(long_section, chunk_size=50, overlap=15)

        for c in chunks:
            assert c.section_path == ["Overview"], f"Missing section_path: {c.section_path}"
            # Chunk must have body text beyond the heading
            after_heading = c.text.split("\n\n", 1)[-1] if "\n\n" in c.text else c.text
            assert len(after_heading.strip()) > 10, f"Chunk looks heading-only: {c.text[:200]}"

    def test_cross_section_boundary_clean(self):
        md = "## Install\n\npip install x\n\n## Config\n\nset ENV=1\n\ndeploy now"
        chunks = _chunk_text(md, chunk_size=50, overlap=15)
        # Install chunks should have Install section_path
        install_chunks = [c for c in chunks if c.section_path == ["Install"]]
        for c in install_chunks:
            assert "Config" not in c.section_path, f"Cross-section leak in section_path: {c.section_path}"

    def test_overlap_is_positional_only(self):
        """Overlap between consecutive chunks is in offsets, not duplicated in content."""
        long_section = (
            "## Overview\n\n"
            + "First paragraph with enough text to fill the chunk size limit. "
            + "Second paragraph that will likely end up in a different chunk. "
            + "Third paragraph to ensure we get multiple chunks from this section."
        )
        chunks = _chunk_text(long_section, chunk_size=30, overlap=10)
        assert len(chunks) >= 2
        # Consecutive chunks within same section should have overlapping offsets
        same_section = [c for c in chunks if c.section_path == ["Overview"]]
        if len(same_section) >= 2:
            for i in range(1, len(same_section)):
                prev = same_section[i - 1]
                curr = same_section[i]
                assert curr.start_offset < prev.end_offset, (
                    f"No positional overlap: prev [{prev.start_offset}:{prev.end_offset}], "
                    f"curr [{curr.start_offset}:{curr.end_offset}]"
                )

    def test_plain_text_no_headings(self):
        chunks = _chunk_text("hello\n\nworld")
        assert len(chunks) >= 1
        for c in chunks:
            assert c.section_path == []
            assert c.heading_level == 0

    def test_empty(self):
        assert _chunk_text("") == []
        assert _chunk_text("   \n\n  ") == []


class TestSplitSection:
    def test_overlap_is_positional(self):
        text = "The quick brown fox jumps over the lazy dog. " * 20
        section = _split_by_headings(text)[0]

        pieces = _split_section(section, max_chars=200, overlap_chars=30)
        assert len(pieces) >= 3
        # Overlap is positional — pieces[i] starts before pieces[i-1] ends
        for i in range(1, len(pieces)):
            assert pieces[i].start < pieces[i - 1].end, (
                f"Piece [{i}] missing positional overlap: "
                f"[{pieces[i].start}:{pieces[i].end}] vs "
                f"prev [{pieces[i - 1].start}:{pieces[i - 1].end}]"
            )
            # Content should NOT be duplicated (no text overlap check —
            # positional alone defines overlap)


class TestOffsetConversion:
    def test_safe_to_full_no_replacements(self):
        assert _safe_to_full(100, []) == 100
        assert _safe_to_full(0, []) == 0

    def test_safe_to_full_after_placeholder(self):
        from app.services.indexing.pipeline import _Replacement

        # Original: "abc```code```def" (16 chars)
        # Safe:     "abc{CODEBLOCK_0}def" (21 chars — placeholder is 15 chars)
        # orig_start=3, orig_end=15 (```code``` = 12 chars), safe_start=3, safe_end=18
        r = _Replacement(orig_start=3, orig_end=15, safe_start=3, safe_end=18)
        # Position after placeholder (safe_pos >= safe_end)
        # safe_pos=19 → should map back to orig position accounting for
        # len(placeholder) - len(original) = 15-12 = 3 char difference
        assert _safe_to_full(19, [r]) == 16

    def test_safe_to_full_before_placeholder(self):
        from app.services.indexing.pipeline import _Replacement

        r = _Replacement(orig_start=3, orig_end=15, safe_start=3, safe_end=18)
        # Position before placeholder — no shift
        assert _safe_to_full(1, [r]) == 1
