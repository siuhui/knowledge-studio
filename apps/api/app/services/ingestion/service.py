"""Ingestion service — dispatch entry point and per-type background pipelines.

IngestionService.dispatch() is the only public API. The API layer calls it
with a Source and BackgroundTasks; it dispatches the correct pipeline
(upload or URL) that runs acquire → parse → document → index asynchronously.
"""

from datetime import UTC, datetime

import httpx
import structlog
from fastapi import BackgroundTasks

from app.core.errors import ValidationError
from app.core.response_codes import ResponseCode
from app.core.telemetry import observe, update_current_span
from app.database import SessionLocal
from app.models.source import Source
from app.services.document import DocumentService
from app.services.indexing import run_index_pipeline
from app.services.ingestion.extractors import WebExtractionError, WebExtractor
from app.services.ingestion.parser import PARSERS
from app.services.object_storage import ObjectStorageService
from app.services.source import SourceService

logger = structlog.get_logger(__name__)


class IngestionService:
    """Orchestrate ingestion for a source.

    Owns the knowledge of which pipeline handles each source type.
    Pipelines run as background tasks so the API returns immediately.
    """

    @staticmethod
    def dispatch(source: Source, background_tasks: BackgroundTasks) -> None:
        """Dispatch the correct background pipeline based on source type."""
        if source.type == "upload":
            background_tasks.add_task(_process_upload, source_id=source.id)
        elif source.type == "url":
            background_tasks.add_task(_process_url, source_id=source.id)
        else:
            raise ValidationError(
                code=ResponseCode.SOURCE_TYPE_UNSUPPORTED,
                message=f"No pipeline for source type '{source.type}'",
            )
        logger.info("ingestion_dispatched", source_id=source.id, source_type=source.type)


# ---------------------------------------------------------------------------
# Per-type ingestion pipelines (background tasks)
# ---------------------------------------------------------------------------


def _process_upload(source_id: str) -> None:
    """Download from MinIO → parse → create Document → index."""

    @observe(name="ingestion.process_upload", capture_input=False, capture_output=False)
    def _pipeline() -> None:
        db = SessionLocal()
        try:
            source = db.get(Source, source_id)
            if not source:
                db.close()
                logger.error("source not found", source_id=source_id)
                return
            s3_key = str(source.config.get("s3_key", ""))
            kb_id = source.knowledge_base_id
            filename = str(source.config.get("original_name", "unknown"))
            update_current_span(input={"source_id": source_id, "kb_id": kb_id, "filename": filename})

            try:
                raw_bytes = ObjectStorageService.get(key=s3_key)
            except Exception:
                db.close()
                logger.exception("failed to download from MinIO", source_id=source_id)
                update_current_span(level="ERROR", status_message="MinIO download failed")
                return

            # Format detection from filename
            if "." in filename:
                name_part, ext_part = filename.rsplit(".", 1)
                ext = ext_part.lower()
                format_map = {"pdf": "pdf", "md": "markdown", "markdown": "markdown", "txt": "text"}
                source_format = format_map.get(ext, "text")
                title = name_part if ext in format_map else filename
            else:
                source_format = "text"
                title = filename

            parser = PARSERS.get(source_format)
            if not parser:
                raise ValueError(f"No parser for format: {source_format}")

            full_text = parser.parse(raw_bytes)
            if not full_text.strip():
                logger.warning("parsed content is empty", filename=filename)

            try:
                document_id = DocumentService.create(
                    db,
                    full_text=full_text,
                    title=title,
                    source_format=source_format,
                    source_id=source_id,
                    kb_id=kb_id,
                    path=filename,
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("document creation failed", source_id=source_id)
                update_current_span(level="ERROR", status_message="Document creation failed")
                return

            logger.info("document created from upload", source_id=source_id, document_id=document_id)

            run_index_pipeline(source_id=source_id, kb_id=kb_id, document_id=document_id)
            SourceService.mark_active(source_id=source_id)

        except Exception:
            pass  # already logged
        finally:
            db.close()

    _pipeline()


def _process_url(source_id: str) -> None:
    """Fetch URL → extract text → create Document → index."""

    @observe(name="ingestion.process_url", capture_input=False, capture_output=False)
    def _pipeline() -> None:
        db = SessionLocal()
        try:
            source = db.get(Source, source_id)
            if not source:
                db.close()
                logger.error("source not found", source_id=source_id)
                return
            url = str((source.config or {}).get("url", ""))
            kb_id = source.knowledge_base_id
            update_current_span(input={"source_id": source_id, "kb_id": kb_id, "url": url})

            try:
                resp = httpx.get(url, follow_redirects=True, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                db.close()
                logger.exception("url fetch failed", source_id=source_id, url=url, error=str(e))
                SourceService.mark_invalid(source_id=source_id)
                return

            content_type = resp.headers.get("content-type", "")
            raw_bytes = resp.content
            http_status = resp.status_code
            del resp

            # Determine extraction path based on content type
            if "text/html" in content_type or not content_type:
                extractor = WebExtractor()
                try:
                    result = extractor.extract(url, raw_bytes)
                except WebExtractionError:
                    db.close()
                    logger.exception("web extraction failed", source_id=source_id, url=url)
                    SourceService.mark_invalid(source_id=source_id)
                    return
                full_text = result.text
                title = result.title
                source_format = "text"
                extraction_method = result.method

            elif "application/pdf" in content_type:
                parser = PARSERS.get("pdf")
                if not parser:
                    db.close()
                    logger.error("pdf parser not available", source_id=source_id)
                    SourceService.mark_invalid(source_id=source_id)
                    return
                full_text = parser.parse(raw_bytes)
                title = url.rsplit("/", 1)[-1] or url
                source_format = "pdf"
                extraction_method = "pdf_parser"

            else:
                extractor = WebExtractor()
                try:
                    result = extractor.extract(url, raw_bytes)
                except WebExtractionError:
                    db.close()
                    logger.exception("web extraction failed", source_id=source_id, url=url)
                    SourceService.mark_invalid(source_id=source_id)
                    return
                full_text = result.text
                title = result.title
                source_format = "text"
                extraction_method = result.method

            if not full_text or not full_text.strip():
                db.close()
                logger.warning("extracted text is empty", source_id=source_id, url=url)
                SourceService.mark_invalid(source_id=source_id)
                return

            try:
                document_id = DocumentService.create(
                    db,
                    full_text=full_text,
                    title=title,
                    source_format=source_format,
                    source_id=source_id,
                    kb_id=kb_id,
                    path=url,
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("document creation failed", source_id=source_id)
                return

            logger.info("document created from url", source_id=source_id, document_id=document_id)

            try:
                SourceService.update_config(
                    db,
                    source_id=source_id,
                    config={
                        "extraction_method": extraction_method,
                        "extracted_at": datetime.now(UTC).isoformat(),
                        "title": title,
                        "content_type": content_type,
                        "http_status": http_status,
                    },
                )
            except Exception:
                logger.warning("failed to update source config metadata", source_id=source_id)

            run_index_pipeline(source_id=source_id, kb_id=kb_id, document_id=document_id)
            SourceService.mark_active(source_id=source_id)

        finally:
            db.close()

    _pipeline()
