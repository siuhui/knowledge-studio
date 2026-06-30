"""Indexing pipeline: parse → chunk → embed.

Three-stage design so re-chunking doesn't require re-parsing the original file:
  Stage 1 — parse_document():  parse raw bytes → persist full_text on Document
  Stage 2 — chunk_document():  read full_text → chunk → create Chunks (embedding=None)
  Stage 3 — embed_document():  read unembedded chunks → batch embed → write embeddings
"""

import hashlib
import re

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.status_enums import DocumentStatus, IndexStageStatus
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

    Creates the Document with status=PROCESSING before parsing so the
    frontend can show "解析中…" during heavy extraction (e.g. PDF).
    On success the status transitions to READY.  Dedup is checked
    against this KB after parsing — if a duplicate is found, the
    just-created record is deleted and the existing one returned.

    Returns the document ID.
    """
    # ── Determine format from filename extension ──
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "text"
    format_map = {"pdf": "pdf", "md": "markdown", "markdown": "markdown", "txt": "text"}
    source_format = format_map.get(ext, "text")

    from app.services.indexing.parser import PARSERS  # noqa: E402

    parser = PARSERS.get(source_format)
    if not parser:
        raise ValueError(f"No parser for format: {source_format}")

    # ── Create placeholder so frontend sees "processing" during parse ──
    document = Document(
        source_id=source_id,
        knowledge_base_id=kb_id,
        title=filename,
        path=filename,
        source_format=source_format,
        full_text="",
        text_hash="",
        status=DocumentStatus.PROCESSING,
    )
    document = DocumentRepository.save(db, document=document)

    # ── Parse (heavy work — PDF extraction) ──
    text = parser.parse(raw_bytes)
    if not text.strip():
        logger.warning("parsed content is empty", filename=filename)

    # ── Dedup check (within this KB) ──
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    existing = DocumentRepository.get_by_text_hash(db, text_hash=text_hash, knowledge_base_id=kb_id)
    if existing and existing.id != document.id:
        logger.info(
            "text hash match, removing duplicate",
            document_id=existing.id,
            filename=filename,
        )
        # Remove the placeholder we just created
        db.delete(document)
        db.flush()
        return existing.id

    # ── Fill in parsed content and transition to ready ──
    document.full_text = text
    document.text_hash = text_hash
    document.status = DocumentStatus.READY
    db.flush()

    logger.info(
        "document parsed",
        document_id=document.id,
        text_length=len(text),
    )

    return document.id


# ── Stage 2: Chunk ────────────────────────────────────────────────────────────


def chunk_document(db: Session, *, document_id: str) -> int:
    """Stage 2: Read Document.full_text → chunk → create Chunks.

    Idempotent — skips if chunks already exist so re-running the pipeline
    after a partial failure doesn't delete partially-embedded chunks.

    Manages DocumentIndexStatus.chunk_status.

    Returns the number of chunks (existing or newly created).
    """
    from datetime import UTC, datetime

    from app.repositories.document_index_status_repository import DocumentIndexStatusRepository

    document = DocumentRepository.get_by_id(db, document_id=document_id)
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    index_status = DocumentIndexStatusRepository.get_or_create(db, document_id=document_id)

    # Skip if already chunked (idempotent — safe to re-run)
    existing_count = ChunkRepository.count_by_document(db, document_id=document_id)
    if existing_count > 0:
        logger.info("chunks already exist, skipping", document_id=document_id, chunk_count=existing_count)
        if index_status.chunk_status != IndexStageStatus.DONE:
            index_status.chunk_status = IndexStageStatus.DONE
            index_status.chunk_count = existing_count
            index_status.chunked_at = datetime.now(UTC)
            db.flush()
        return existing_count

    # Mark chunk as running
    index_status.chunk_status = IndexStageStatus.RUNNING
    db.flush()

    # Chunk from persisted full_text (no re-parse needed)
    chunk_texts = _chunk_text(document.full_text)
    if not chunk_texts:
        logger.warning("no chunks generated", document_id=document_id)
        chunk_texts = [document.full_text]  # fallback

    kb_id = document.knowledge_base_id

    # Create Chunk records
    chunk_records = []
    for i, chunk_text in enumerate(chunk_texts):
        chunk = Chunk(
            doc_id=document_id,
            knowledge_base_id=kb_id,
            chunk_index=i,
            content=chunk_text,
            token_count=_estimate_token_count(chunk_text),
            embedding=None,
        )
        chunk_records.append(chunk)

    ChunkRepository.save_batch(db, chunks=chunk_records)

    # Mark chunk as done
    index_status.chunk_status = IndexStageStatus.DONE
    index_status.chunk_count = len(chunk_records)
    index_status.chunked_at = datetime.now(UTC)
    db.flush()

    logger.info(
        "document chunked",
        document_id=document_id,
        chunk_count=len(chunk_records),
    )

    return len(chunk_records)


# ── Stage 3: Embed ──────────────────────────────────────────────────────────────


def embed_document(db: Session, *, document_id: str) -> int:
    """Stage 3: Embed unembedded chunks for a document.

    Reads chunks via ChunkRepository, filters to unembedded only
    (resume-safe — skips already-embedded chunks), batches them,
    calls the embedder, and writes embeddings back.

    Manages DocumentIndexStatus.embed_status.

    Returns the number of chunks embedded.
    """
    from datetime import UTC, datetime

    from app.repositories.document_index_status_repository import DocumentIndexStatusRepository
    from app.services.embedding import embedder

    chunks = ChunkRepository.list_by_document(db, document_id=document_id)
    index_status = DocumentIndexStatusRepository.get_or_create(db, document_id=document_id)

    # Only embed chunks without embeddings (resume-safe)
    unembedded = [c for c in chunks if c.embedding is None]
    if not unembedded:
        logger.info("all chunks already embedded", document_id=document_id)
        if index_status.embed_status != IndexStageStatus.DONE:
            index_status.embed_status = IndexStageStatus.DONE
            index_status.embed_count = len(chunks)  # total chunks
            index_status.embedded_at = datetime.now(UTC)
            index_status.embedding_model = settings.embedding.model
            db.flush()
        return 0

    # Mark embed as running
    index_status.embed_status = IndexStageStatus.RUNNING
    index_status.embedding_model = settings.embedding.model
    db.flush()

    batch_size = settings.embedding.batch_size
    total_embedded = 0

    for i in range(0, len(unembedded), batch_size):
        batch = unembedded[i : i + batch_size]
        texts = [c.content for c in batch]

        embeddings = embedder.embed(texts)

        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

        total_embedded += len(batch)
        db.flush()
        logger.debug(
            "embedding batch",
            document_id=document_id,
            batch_start=i,
            batch_size=len(batch),
        )

    # Mark embed as done
    index_status.embed_status = IndexStageStatus.DONE
    index_status.embed_count = len(chunks)  # total chunks with embeddings now
    index_status.embedded_at = datetime.now(UTC)
    db.flush()

    logger.info(
        "document embedded",
        document_id=document_id,
        chunk_count=total_embedded,
    )

    return total_embedded


# ── Background task (orchestrates all three stages) ───────────────────────────


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
            status = fail_db.query(DocumentIndexStatus).filter(
                DocumentIndexStatus.document_id == document_id
            ).first()
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


def run_index_pipeline(source_id: str, kb_id: str, s3_key: str, filename: str) -> None:
    """Background task: download from MinIO → parse → chunk → embed.

    Each stage commits independently — a failure in one stage does not
    roll back completed earlier stages. Re-running via /extract resumes
    from the first incomplete stage.

    Pipeline failures do NOT affect Source status. Source is a config
    record — it's active as long as the S3 object exists. Document
    owns the content lifecycle; DocumentIndexStatus owns indexing state.
    """
    from app.database import SessionLocal
    from app.services.object_storage import ObjectStorageService

    db = SessionLocal()
    document_id: str | None = None
    try:
        # ── Stage 1: Parse ──
        try:
            raw_bytes = ObjectStorageService.get(key=s3_key)
            document_id = parse_document(db, raw_bytes=raw_bytes, filename=filename, source_id=source_id, kb_id=kb_id)
            db.commit()
            logger.info("stage 1 (parse) completed", source_id=source_id, document_id=document_id)
        except Exception:
            db.rollback()
            logger.exception("stage 1 (parse) failed", source_id=source_id)
            return  # no document yet, nothing to mark

        # ── Stage 2: Chunk ──
        try:
            chunk_count = chunk_document(db, document_id=document_id)
            db.commit()
            logger.info("stage 2 (chunk) completed", document_id=document_id, chunk_count=chunk_count)
        except Exception as e:
            db.rollback()
            logger.exception("stage 2 (chunk) failed", document_id=document_id)
            _mark_index_failed(document_id=document_id, stage="chunk", error_message=str(e))
            return

        # ── Stage 3: Embed ──
        try:
            embed_count = embed_document(db, document_id=document_id)
            db.commit()
            logger.info("stage 3 (embed) completed", document_id=document_id, embed_count=embed_count)
        except Exception as e:
            db.rollback()
            logger.exception("stage 3 (embed) failed", document_id=document_id)
            _mark_index_failed(document_id=document_id, stage="embed", error_message=str(e))
            return

        logger.info("index pipeline completed", source_id=source_id, document_id=document_id)
    finally:
        db.close()
