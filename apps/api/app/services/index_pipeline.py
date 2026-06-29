"""Indexing pipeline: parse → chunk.

Two-stage design so re-chunking doesn't require re-parsing the original file:
  Stage 1 — parse_document():  parse raw bytes → persist full_text on Document
  Stage 2 — chunk_document():  read full_text → chunk → create Chunks

Embedding is deferred (v0.2.0); Chunk records are created with embedding=None.
"""

import hashlib
import re

import structlog
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository

logger = structlog.get_logger(__name__)

CHUNK_SIZE = 512  # tokens (approximate: 1 token ≈ 4 chars)
OVERLAP = 50  # tokens


def _estimate_token_count(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English text."""
    return len(text) // 4


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Paragraph-aware fixed-window chunking.

    Splits on paragraph boundaries first; if a paragraph exceeds chunk_size,
    falls back to sentence-level splitting.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []

    char_overlap = overlap * 4

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if _estimate_token_count(para) <= chunk_size:
            chunks.append(para)
        else:
            # Paragraph too long, split by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sentence in sentences:
                if _estimate_token_count(current + " " + sentence) <= chunk_size:
                    current = (current + " " + sentence).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sentence
            if current:
                chunks.append(current)

    # Apply overlap: prepend tail of previous chunk to next
    if char_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-char_overlap:]
            overlapped.append(prev_tail + "\n" + chunks[i])
        chunks = overlapped

    return chunks


# ── Stage 1: Parse ───────────────────────────────────────────────────────────


def parse_document(db: Session, *, raw_bytes: bytes, filename: str, source_id: str, kb_id: str) -> str:
    """Stage 1: Parse raw bytes → create Document with full_text.

    Document is created with status='parsed' and the denormalized
    knowledge_base_id for direct ownership lookups (independent of source).
    Chunking happens separately in stage 2 so re-chunking never requires
    re-parsing.

    Returns the document ID.
    """
    # ── Determine format from filename extension ──
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "text"
    format_map = {"pdf": "pdf", "md": "markdown", "markdown": "markdown", "txt": "text"}
    source_format = format_map.get(ext, "text")

    # ── Parse ──
    from app.services.indexing.parser import PARSERS  # noqa: E402

    parser = PARSERS.get(source_format)
    if not parser:
        raise ValueError(f"No parser for format: {source_format}")

    text = parser.parse(raw_bytes)
    if not text.strip():
        logger.warning("parsed content is empty", filename=filename)

    # ── Dedup check ──
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    existing = DocumentRepository.get_by_text_hash(db, text_hash=text_hash)
    if existing:
        logger.info(
            "text hash match, skipping re-parse",
            document_id=existing.id,
            filename=filename,
        )
        return existing.id

    # ── Create Document (parsed but not yet chunked) ──
    document = Document(
        source_id=source_id,
        knowledge_base_id=kb_id,
        title=filename,
        path=filename,
        source_format=source_format,
        full_text=text,
        text_hash=text_hash,
        status="parsed",
    )
    document = DocumentRepository.save(db, document=document)

    logger.info(
        "document parsed",
        document_id=document.id,
        text_length=len(text),
    )

    return document.id


# ── Stage 2: Chunk ────────────────────────────────────────────────────────────


def chunk_document(db: Session, *, document_id: str) -> int:
    """Stage 2: Read Document.full_text → chunk → create Chunks → status='active'.

    Deletes any existing chunks for this document before creating new ones
    (idempotent — safe to call on already-chunked documents).

    Returns the number of chunks created.
    """
    document = DocumentRepository.get_by_id(db, document_id=document_id)
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    # Remove old chunks (if re-chunking)
    ChunkRepository.delete_by_document(db, document_id=document_id)

    # Chunk from persisted full_text (no re-parse needed)
    chunk_texts = _chunk_text(document.full_text)
    if not chunk_texts:
        logger.warning("no chunks generated", document_id=document_id)
        chunk_texts = [document.full_text]  # fallback

    # Create Chunk records
    chunk_records = []
    for i, chunk_text in enumerate(chunk_texts):
        chunk = Chunk(
            doc_id=document_id,
            chunk_index=i,
            content=chunk_text,
            token_count=_estimate_token_count(chunk_text),
            embedding=None,  # deferred to v0.2.0
        )
        chunk_records.append(chunk)

    ChunkRepository.save_batch(db, chunks=chunk_records)

    # Transition status
    document.status = "active"
    db.flush()

    logger.info(
        "document chunked",
        document_id=document_id,
        chunk_count=len(chunk_records),
    )

    return len(chunk_records)


# ── Background task (orchestrates both stages) ────────────────────────────────


def run_index_pipeline(source_id: str, kb_id: str, s3_key: str, filename: str) -> None:
    """Background task: download from MinIO → parse → chunk.

    Creates its own DB session since the request session is already
    closed when BackgroundTasks fire. If the pipeline fails, marks
    the source as error.

    Receives kb_id directly (denormalized) to avoid looking up the
    source in a background task — the source may be deleted by the
    time this task runs.
    """
    from app.database import SessionLocal
    from app.services.object_storage import ObjectStorageService
    from app.services.source import SourceService

    db = SessionLocal()
    try:
        raw_bytes = ObjectStorageService.get(key=s3_key)

        # Stage 1: Parse
        document_id = parse_document(db, raw_bytes=raw_bytes, filename=filename, source_id=source_id, kb_id=kb_id)

        # Stage 2: Chunk
        chunk_document(db, document_id=document_id)

        db.commit()
        logger.info("index pipeline completed", source_id=source_id, document_id=document_id)
    except Exception:
        db.rollback()
        logger.exception("index pipeline failed", source_id=source_id)
        # Mark source as error (creates its own session, safe in bg task)
        try:
            SourceService.mark_error(source_id=source_id)
        except Exception:
            logger.exception(
                "failed to mark source as error after pipeline failure",
                source_id=source_id,
            )
    finally:
        db.close()
