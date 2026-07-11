"""Indexing pipeline: chunk → embed.

Chunking: structure-aware recursive splitting with source mapping.

  - Protects fenced code blocks from being split.
  - Splits on heading boundaries (# / ## / …), tracks section_path hierarchy.
  - Within each heading section, recursively splits: paragraphs → lines
    → sentences → words → characters.
  - Each chunk carries (start_offset, end_offset) mapping back to
    Document.full_text — zero-overlap content, positions track overlap.

Two-stage design:
  Stage 1 — chunk_document():  read full_text → chunk → create Chunks (embedding=None)
  Stage 2 — embed_document():  read unembedded chunks → batch embed → write embeddings

Document creation (parse + dedup) lives in services/ingestion/.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.core.telemetry import observe, update_current_span
from app.models.chunk import Chunk
from app.models.status_enums import IndexStageStatus
from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.repositories.document_index_status import DocumentIndexStatusRepository
from app.services.embedding import embedder

logger = structlog.get_logger(__name__)

CHUNK_SIZE = 512  # tokens (approximate: 1 token ≈ 4 chars)
OVERLAP = 50  # tokens

# ── Regex helpers (compiled once at module level) ──────────────────────────

_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Separator priority chain for recursive splitting (highest → lowest).
_SEPARATORS: list[tuple[str, str]] = [
    (r"\n\s*\n", "\n\n"),                       # 1. paragraph boundaries
    (r"\n", "\n"),                               # 2. line breaks
    (r"(?<=[。.!?！？])\s+", " "),               # 3. sentence endings (zh + en)
    (r"\s+", " "),                               # 4. word boundaries
]


# ── Token estimation ───────────────────────────────────────────────────────


def _estimate_token_count(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English text."""
    return len(text) // 4


# ── Code block protection ──────────────────────────────────────────────────


@dataclass
class _Replacement:
    """Record of a code-block → placeholder substitution for offset correction."""

    orig_start: int   # position in full_text
    orig_end: int
    safe_start: int   # position in safe_text (after all prior replacements)
    safe_end: int


def _extract_code_blocks(text: str) -> tuple[str, list[str], list[_Replacement]]:
    """Replace fenced code blocks with numbered placeholders.

    Returns (safe_text, original_blocks, replacement_records).
    Replacement records enable mapping safe_text positions back to full_text.
    """
    blocks: list[str] = []
    replacements: list[_Replacement] = []
    cum_shift = 0  # cumulative (placeholder_len - original_len) so far

    def _replace(m: re.Match[str]) -> str:
        nonlocal cum_shift
        placeholder = f"{{CODEBLOCK_{len(blocks)}}}"
        orig_start = m.start()
        orig_end = m.end()
        safe_start = orig_start + cum_shift
        safe_end = safe_start + len(placeholder)
        blocks.append(m.group(0))
        replacements.append(_Replacement(
            orig_start=orig_start,
            orig_end=orig_end,
            safe_start=safe_start,
            safe_end=safe_end,
        ))
        cum_shift += len(placeholder) - (orig_end - orig_start)
        return placeholder

    safe_text = _CODE_BLOCK_RE.sub(_replace, text)
    return safe_text, blocks, replacements


def _safe_to_full(safe_pos: int, replacements: list[_Replacement]) -> int:
    """Convert a position in safe_text to the corresponding position in full_text.

    Walk through each replacement; every replacement that ends *before*
    *safe_pos* contributed a size delta that must be reversed.
    """
    full_pos = safe_pos
    for r in replacements:
        if safe_pos >= r.safe_end:
            full_pos += (r.orig_end - r.orig_start) - (r.safe_end - r.safe_start)
        elif safe_pos > r.safe_start:
            # Inside a placeholder — shouldn't happen (chunk boundaries
            # never land inside placeholders), but handle gracefully.
            full_pos = r.orig_start + (safe_pos - r.safe_start)
            return full_pos
    return full_pos


def _restore_code_blocks(chunks: list[str], blocks: list[str]) -> list[str]:
    """Replace numbered placeholders with the original code blocks."""
    result: list[str] = []
    for chunk in chunks:
        for i, block in enumerate(blocks):
            chunk = chunk.replace(f"{{CODEBLOCK_{i}}}", block)
        result.append(chunk)
    return result


# ── Heading-aware splitting ────────────────────────────────────────────────


@dataclass
class _Section:
    """A heading-delimited section with position info in safe_text coordinates."""

    text: str
    safe_start: int      # position in safe_text (inclusive)
    safe_end: int        # position in safe_text (exclusive)
    heading_level: int   # 0 = no heading
    breadcrumb: list[str] = field(default_factory=list)


def _split_by_headings(text: str) -> list[_Section]:
    """Split text at heading boundaries, tracking breadcrumb hierarchy.

    Each section's text is the raw slice of *text* — no strip, no
    reconstruction.  This guarantees ``section.text ==
    text[section.safe_start:section.safe_end]``, which makes relative
    offsets trivially convertible to absolute.
    """
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        return [_Section(text=text, safe_start=0, safe_end=len(text),
                         heading_level=0, breadcrumb=[])]

    sections: list[_Section] = []
    breadcrumb_stack: list[tuple[int, str]] = []

    # Text before the first heading — keep as raw slice
    if matches[0].start() > 0:
        before = text[:matches[0].start()]
        if before.strip():
            sections.append(_Section(
                text=before,
                safe_start=0,
                safe_end=len(before),
                heading_level=0,
                breadcrumb=[],
            ))

    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()

        while breadcrumb_stack and breadcrumb_stack[-1][0] >= level:
            breadcrumb_stack.pop()
        breadcrumb_stack.append((level, title))

        section_start = match.start()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        sections.append(_Section(
            text=text[section_start:section_end],
            safe_start=section_start,
            safe_end=section_end,
            heading_level=level,
            breadcrumb=[b[1] for b in breadcrumb_stack],
        ))

    # Merge heading-only sections into their successor when the successor
    # is deeper (e.g. H1 title → H3 chapter).  The breadcrumb stack already
    # propagated the parent title; the merge just avoids wasting a chunk on
    # a bare heading that has no retrieval value.
    merged: list[_Section] = []
    skip = False
    for i, section in enumerate(sections):
        if skip:
            skip = False
            continue
        # Heading-only: text is exactly one line matching a heading pattern
        is_heading_only = bool(_HEADING_RE.fullmatch(section.text.strip()))
        next_section = sections[i + 1] if i + 1 < len(sections) else None

        if is_heading_only and next_section is not None and next_section.heading_level > section.heading_level:
            # Merge into successor — its breadcrumb already contains our title
            merged.append(_Section(
                text=section.text + next_section.text,
                safe_start=section.safe_start,
                safe_end=next_section.safe_end,
                heading_level=next_section.heading_level,
                breadcrumb=next_section.breadcrumb,
            ))
            skip = True
        else:
            merged.append(section)

    return merged


# ── Recursive splitter ─────────────────────────────────────────────────────


def _recursive_split(text: str, max_chars: int) -> list[tuple[str, int, int]]:
    """Split *text* to fit within *max_chars*, returning (text, rel_start, rel_end).

    Positions are relative to the original *text* — leading whitespace
    offset is tracked so callers can convert to absolute offsets.
    """
    stripped = text.strip()
    if not stripped:
        return []
    leading = len(text) - len(text.lstrip())
    if len(stripped) <= max_chars:
        return [(stripped, leading, leading + len(stripped))]
    pieces = _split_level(stripped, sep_idx=0, max_chars=max_chars)
    return [(t, leading + rs, leading + re) for t, rs, re in pieces]


def _repair_heading_orphans(
    pieces: list[tuple[str, int, int]],
) -> list[tuple[str, int, int]]:
    """Merge heading-only pieces with the body piece that follows them.

    Consecutive headings (shallow → deep) are stitched together so chunk
    content always carries heading context alongside body text.
    """
    if len(pieces) <= 1:
        return pieces

    result: list[tuple[str, int, int]] = []
    i = 0
    while i < len(pieces):
        piece, p_start, p_end = pieces[i]
        is_heading = bool(_HEADING_RE.match(piece.strip()))
        next_text, next_start, next_end = pieces[i + 1] if i + 1 < len(pieces) else ("", 0, 0)
        next_is_heading = bool(_HEADING_RE.match(next_text.strip()))

        if not is_heading or not next_text:
            result.append((piece, p_start, p_end))
            i += 1
        elif next_is_heading:
            result.append((next_text + "\n\n" + piece, next_start, p_end))
            i += 2
        else:
            result.append((piece + "\n\n" + next_text, p_start, next_end))
            i += 2

    return result


def _split_level(
    text: str, *, sep_idx: int, max_chars: int,
) -> list[tuple[str, int, int]]:
    """Split using ``_SEPARATORS[sep_idx]``; recurse on oversize pieces.

    Returns (text, rel_start, rel_end) for each piece, where positions
    are relative to the input *text*.
    """
    if len(text) <= max_chars:
        return [(text, 0, len(text))] if text.strip() else []

    if sep_idx >= len(_SEPARATORS):
        # Exhausted all separators — character-level split.
        return [(text[i:i + max_chars], i, min(i + max_chars, len(text)))
                for i in range(0, len(text), max_chars)]

    pattern, join_str = _SEPARATORS[sep_idx]

    # Use finditer to track positions
    delim_matches = list(re.finditer(pattern, text))

    if not delim_matches:
        return _split_level(text, sep_idx=sep_idx + 1, max_chars=max_chars)

    # Build parts with positions
    parts: list[tuple[str, int, int]] = []
    prev_end = 0
    for m in delim_matches:
        part_text = text[prev_end:m.start()]
        if part_text.strip():
            parts.append((part_text, prev_end, m.start()))
        prev_end = m.end()

    # Last part after final delimiter
    if prev_end < len(text):
        final = text[prev_end:]
        if final.strip():
            parts.append((final, prev_end, len(text)))

    if not parts:
        return _split_level(text, sep_idx=sep_idx + 1, max_chars=max_chars)

    # Only one part — this separator didn't split anything → try next
    if len(parts) <= 1:
        return _split_level(text, sep_idx=sep_idx + 1, max_chars=max_chars)

    chunks: list[tuple[str, int, int]] = []
    buffer: list[tuple[str, int, int]] = []
    buffer_len = 0

    for part_text, part_start, part_end in parts:
        part_len = len(part_text)
        overhead = len(join_str) if buffer else 0

        if buffer_len + overhead + part_len <= max_chars:
            buffer.append((part_text, part_start, part_end))
            buffer_len += overhead + part_len
        else:
            if buffer:
                merged = join_str.join(p[0] for p in buffer)
                chunks.append((merged, buffer[0][1], buffer[-1][2]))

            if part_len > max_chars:
                sub_pieces = _split_level(part_text, sep_idx=sep_idx + 1, max_chars=max_chars)
                for sub_text, sub_start, sub_end in sub_pieces:
                    chunks.append((sub_text, part_start + sub_start, part_start + sub_end))
                buffer = []
                buffer_len = 0
            else:
                buffer = [(part_text, part_start, part_end)]
                buffer_len = part_len

    if buffer:
        merged = join_str.join(p[0] for p in buffer)
        chunks.append((merged, buffer[0][1], buffer[-1][2]))

    return chunks


# ── Section splitter ───────────────────────────────────────────────────────


@dataclass
class _Piece:
    """A split piece with absolute positions in safe_text."""

    text: str
    start: int   # inclusive, in safe_text
    end: int     # exclusive, in safe_text


def _split_section(
    section: _Section, max_chars: int, overlap_chars: int,
) -> list[_Piece]:
    """Split a section recursively, then mark overlap as positional only.

    Overlap is expressed as overlapping (start, end) ranges — content is
    NOT duplicated.  Two adjacent pieces within the same section have
    overlapping end/start ranges, but their text is unique.
    """
    pieces = _recursive_split(section.text, max_chars)
    pieces = _repair_heading_orphans(pieces)

    # Convert relative → absolute safe_text positions
    result: list[_Piece] = []
    for text, rel_start, rel_end in pieces:
        result.append(_Piece(
            text=text,
            start=section.safe_start + rel_start,
            end=section.safe_start + rel_end,
        ))

    if overlap_chars <= 0 or len(result) <= 1:
        return result

    # Positional overlap only — no content duplication.
    # Each piece (except the first) extends its start backwards by
    # overlap_chars, so consecutive pieces have overlapping ranges.
    overlapped: list[_Piece] = [result[0]]
    for i in range(1, len(result)):
        prev = result[i - 1]
        curr = result[i]
        new_start = max(prev.start, curr.start - overlap_chars)
        overlapped.append(_Piece(text=curr.text, start=new_start, end=curr.end))

    return overlapped


# ── Public API: chunk text → ChunkCandidate ────────────────────────────────


@dataclass
class ChunkCandidate:
    """A chunk ready for persistence, with full source mapping to Document.full_text."""

    text: str
    start_offset: int      # 0-based, inclusive, in Document.full_text
    end_offset: int        # 0-based, exclusive
    section_path: list[str]
    heading_level: int
    chunk_metadata: dict[str, object]


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[ChunkCandidate]:
    """Structure-aware chunking with source-mapping back to full_text.

    1. Protect fenced code blocks → safe_text with position records.
    2. Split on heading boundaries; capture breadcrumb + heading level.
    3. Within each section, recursively split (paragraph → line →
       sentence → word → char).  Overlap is positional only.
    4. Convert all safe_text positions → full_text positions.
    5. Restore code blocks in chunk content.
    """
    if not text or not text.strip():
        return []

    char_size = chunk_size * 4
    char_overlap = overlap * 4

    # 1. Protect code blocks
    safe_text, code_blocks, replacements = _extract_code_blocks(text)

    # 2. Split by headings → sections with safe_text positions
    sections = _split_by_headings(safe_text) if _HEADING_RE.search(safe_text) else [
        _Section(text=safe_text, safe_start=0, safe_end=len(safe_text),
                 heading_level=0, breadcrumb=[]),
    ]

    # 3–4. Split each section + convert safe_text → full_text
    candidates: list[ChunkCandidate] = []
    for section in sections:
        pieces = _split_section(section, char_size, char_overlap)
        for piece in pieces:
            # Convert from safe_text positions to full_text positions
            abs_start = _safe_to_full(piece.start, replacements)
            abs_end = _safe_to_full(piece.end, replacements)
            candidates.append(ChunkCandidate(
                text=piece.text,
                start_offset=abs_start,
                end_offset=abs_end,
                section_path=section.breadcrumb,
                heading_level=section.heading_level,
                chunk_metadata={},
            ))

    # 5. Restore code blocks in chunk content
    for c in candidates:
        for i, block in enumerate(code_blocks):
            c.text = c.text.replace(f"{{CODEBLOCK_{i}}}", block)

    return candidates


# ── Stage 1: Chunk ────────────────────────────────────────────────────────────


@observe(name="index.chunk", capture_input=False, capture_output=False)
def chunk_document(db: Session, *, document_id: str) -> int:
    """Read Document.full_text → chunk → create Chunks.

    Idempotent — skips if chunks already exist so re-running the pipeline
    after a partial failure doesn't delete partially-embedded chunks.

    Manages DocumentIndexStatus.chunk_status.
    Returns the number of chunks (existing or newly created).
    """
    update_current_span(input={"document_id": document_id})

    document = DocumentRepository.get_by_id(db, document_id=document_id)
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    index_status = DocumentIndexStatusRepository.get_or_create(db, document_id=document_id)

    existing_count = ChunkRepository.count_by_document(db, document_id=document_id)
    if existing_count > 0:
        logger.info("chunks already exist, skipping", document_id=document_id, chunk_count=existing_count)
        if index_status.chunk_status != IndexStageStatus.DONE:
            index_status.chunk_status = IndexStageStatus.DONE
            index_status.chunk_count = existing_count
            index_status.chunked_at = datetime.now(UTC)
            DocumentIndexStatusRepository.save(db, status=index_status)
        update_current_span(output={"chunk_count": existing_count, "cached": True})
        return existing_count

    index_status.chunk_status = IndexStageStatus.RUNNING
    DocumentIndexStatusRepository.save(db, status=index_status)

    candidates = _chunk_text(document.full_text)
    if not candidates:
        # Fallback: single-chunk the whole text
        candidates = [ChunkCandidate(
            text=document.full_text,
            start_offset=0,
            end_offset=len(document.full_text),
            section_path=[],
            heading_level=0,
            chunk_metadata={},
        )]

    chunk_records = []
    for i, c in enumerate(candidates):
        chunk = Chunk(
            doc_id=document_id,
            chunk_index=i,
            content=c.text,
            token_count=_estimate_token_count(c.text),
            start_offset=c.start_offset,
            end_offset=c.end_offset,
            section_path=c.section_path,
            heading_level=c.heading_level,
            chunk_metadata=c.chunk_metadata,
        )
        chunk_records.append(chunk)

    ChunkRepository.save_batch(db, chunks=chunk_records)

    index_status.chunk_status = IndexStageStatus.DONE
    index_status.chunk_count = len(chunk_records)
    index_status.chunked_at = datetime.now(UTC)
    DocumentIndexStatusRepository.save(db, status=index_status)

    logger.info("document chunked", document_id=document_id, chunk_count=len(chunk_records))

    chunk_count = len(chunk_records)
    update_current_span(output={"chunk_count": chunk_count})
    return chunk_count


# ── Stage 2: Embed ──────────────────────────────────────────────────────────────


@observe(name="index.embed", capture_input=False, capture_output=False)
def embed_document(db: Session, *, document_id: str) -> int:
    """Embed unembedded chunks for a document.

    Filters to unembedded only (resume-safe), batches them,
    calls the embedder, and writes embeddings back.

    Manages DocumentIndexStatus.embed_status.
    Returns the number of chunks embedded.
    """
    update_current_span(input={"document_id": document_id})

    chunks = ChunkRepository.list_by_document(db, document_id=document_id)
    index_status = DocumentIndexStatusRepository.get_or_create(db, document_id=document_id)

    unembedded = [c for c in chunks if c.embedding is None]
    if not unembedded:
        logger.info("all chunks already embedded", document_id=document_id)
        if index_status.embed_status != IndexStageStatus.DONE:
            index_status.embed_status = IndexStageStatus.DONE
            index_status.embed_count = len(chunks)
            index_status.embedded_at = datetime.now(UTC)
            index_status.embedding_model = settings.embedding.model
            DocumentIndexStatusRepository.save(db, status=index_status)
        update_current_span(output={"embedded_count": 0, "cached": True})
        return 0

    index_status.embed_status = IndexStageStatus.RUNNING
    index_status.embedding_model = settings.embedding.model
    DocumentIndexStatusRepository.save(db, status=index_status)

    batch_size = settings.embedding.batch_size
    total_embedded = 0

    for i in range(0, len(unembedded), batch_size):
        batch = unembedded[i : i + batch_size]
        texts = [c.content for c in batch]

        embeddings = embedder.embed(texts)

        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

        total_embedded += len(batch)
        logger.debug("embedding batch", document_id=document_id, batch_start=i, batch_size=len(batch))

    index_status.embed_status = IndexStageStatus.DONE
    index_status.embed_count = len(chunks)
    index_status.embedded_at = datetime.now(UTC)
    DocumentIndexStatusRepository.save(db, status=index_status)

    logger.info("document embedded", document_id=document_id, chunk_count=total_embedded)

    update_current_span(output={"embedded_count": total_embedded, "model": settings.embedding.model})
    return total_embedded


# ── Shared chunk + embed helper ──────────────────────────────────────────────


def _run_chunk_embed(db: Session, *, document_id: str, source_id: str) -> tuple[int, int]:
    """Run chunk and embed stages. Returns (chunk_count, embed_count)."""
    logger.info("indexing started", source_id=source_id, document_id=document_id)

    # Stage 1: Chunk
    try:
        chunk_count = chunk_document(db, document_id=document_id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("chunk failed", document_id=document_id)
        _mark_index_failed(document_id=document_id, stage="chunk", error_message=str(e))
        update_current_span(level="ERROR", status_message="Chunk stage failed")
        raise

    logger.info("chunk completed", document_id=document_id, chunk_count=chunk_count)

    # Stage 2: Embed
    try:
        embed_count = embed_document(db, document_id=document_id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("embed failed", document_id=document_id)
        _mark_index_failed(document_id=document_id, stage="embed", error_message=str(e))
        update_current_span(level="ERROR", status_message="Embed stage failed")
        raise

    logger.info("embed completed", document_id=document_id, embed_count=embed_count)
    logger.info("index pipeline completed", source_id=source_id, document_id=document_id)
    return chunk_count, embed_count


def _mark_index_failed(*, document_id: str | None, stage: str, error_message: str) -> None:
    """Write failure status to DocumentIndexStatus via an independent session.

    Called after the pipeline main session has been rolled back, so the
    index_status update survives independently of chunk/embed data.
    """
    if document_id is None:
        return

    from app.database import SessionLocal
    from app.models.document_index_status import DocumentIndexStatus

    message = error_message[:500] if error_message else None

    with SessionLocal() as fail_db:
        with fail_db.begin():
            status = fail_db.query(DocumentIndexStatus).filter(DocumentIndexStatus.document_id == document_id).first()
            if status is None:
                status = DocumentIndexStatus(document_id=document_id)
                fail_db.add(status)
            if stage in ("chunk", "embed"):
                setattr(status, f"{stage}_status", IndexStageStatus.FAILED)
            status.error_stage = stage
            status.error_message = message
            logger.info(
                "index status marked as failed",
                document_id=document_id,
                stage=stage,
            )


def run_index_pipeline(source_id: str, kb_id: str, document_id: str) -> None:
    """Background task: chunk → embed for an already-created Document.

    Runs in an independent background thread (FastAPI BackgroundTasks).
    ``@observe`` creates a root span; the decorator degrades to a
    pass-through when telemetry is disabled.
    """
    from app.database import SessionLocal

    @observe(name="index.pipeline", capture_input=False, capture_output=False)
    def _pipeline() -> None:
        db = SessionLocal()
        update_current_span(
            input={"source_id": source_id, "kb_id": kb_id, "document_id": document_id},
        )
        try:
            chunk_count, embed_count = _run_chunk_embed(db, document_id=document_id, source_id=source_id)
            update_current_span(
                output={
                    "document_id": document_id,
                    "chunk_count": chunk_count,
                    "embed_count": embed_count,
                },
            )
        except Exception:
            pass  # _run_chunk_embed already logs + marks failed
        finally:
            db.close()

    _pipeline()
