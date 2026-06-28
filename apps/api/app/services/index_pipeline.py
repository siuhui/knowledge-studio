"""Indexing pipeline: parse → chunk → embed.

The pipeline is deliberately minimal — no RAG framework, just direct control
over each step as specified in engineering-standards.md §10.
"""

import hashlib
import re

import structlog
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
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


def _reindex_document(db: Session, document_id: str) -> None:
    """Delete existing chunks and re-index a document."""
    document = DocumentRepository.get_by_id(db, document_id=document_id)
    if not document:
        logger.warning("document not found for reindexing", document_id=document_id)
        return

    # Remove old chunks
    ChunkRepository.delete_by_document(db, document_id=document_id)

    # Chunk
    texts = _chunk_text(document.content)
    if not texts:
        logger.warning("no chunks generated", document_id=document_id)
        return

    # Create chunk records (embedding will be filled by the embedder)
    chunk_records = []
    for i, text in enumerate(texts):
        chunk = Chunk(
            doc_id=document_id,
            chunk_index=i,
            content=text,
            token_count=_estimate_token_count(text),
            embedding=None,  # Will be set by embedder
        )
        chunk_records.append(chunk)

    ChunkRepository.save_batch(db, chunks=chunk_records)
    logger.info(
        "document indexed",
        document_id=document_id,
        chunk_count=len(chunk_records),
    )


def index_document(db: Session, *, raw_bytes: bytes, filename: str, source_id: str) -> str:
    """Full indexing pipeline: parse raw bytes → create document → chunk → embed.

    Returns the document ID.
    """
    # Determine format from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "text"
    format_map = {"pdf": "pdf", "md": "markdown", "markdown": "markdown", "txt": "text"}
    source_format = format_map.get(ext, "text")

    # Parse
    from app.services.indexing.parser import PARSERS

    parser = PARSERS.get(source_format)
    if not parser:
        raise ValueError(f"No parser for format: {source_format}")

    text = parser.parse(raw_bytes)
    if not text.strip():
        logger.warning("parsed content is empty", filename=filename)

    # Create document
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    existing = DocumentRepository.get_by_content_hash(db, content_hash=content_hash)
    if existing:
        logger.info(
            "content hash match, skipping re-index",
            document_id=existing.id,
            filename=filename,
        )
        return existing.id

    from app.models.document import Document

    document = Document(
        source_id=source_id,
        title=filename,
        path=filename,
        source_format=source_format,
        content=text,
        content_hash=content_hash,
        status="active",
    )
    document = DocumentRepository.save(db, document=document)

    # Chunk
    _reindex_document(db, document_id=document.id)

    return document.id


def run_index_pipeline(source_id: str, s3_key: str, filename: str) -> None:
    """Background task: download from MinIO → parse → chunk.

    Creates its own DB session since the request session is already
    closed when BackgroundTasks fire. If the pipeline fails, marks
    the source as error.
    """
    from app.database import SessionLocal
    from app.services.object_storage import ObjectStorageService
    from app.services.source import SourceService

    db = SessionLocal()
    try:
        raw_bytes = ObjectStorageService.get(key=s3_key)
        index_document(db, raw_bytes=raw_bytes, filename=filename, source_id=source_id)
        db.commit()
        logger.info("index pipeline completed", source_id=source_id)
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
