import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import error_codes
from ..core.errors import BadRequestError, NotFoundError
from ..core.uow import transactional
from ..models import IndexJob, IndexJobStatus, KnowledgeChunk, KnowledgeDocument, KnowledgeSource


def _chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    body = text.strip()
    if not body:
        return []
    if len(body) <= chunk_size:
        return [body]

    chunks: list[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(body):
        part = body[start : start + chunk_size].strip()
        if part:
            chunks.append(part)
        start += step
    return chunks


def _load_local_config(config_json: str | None) -> tuple[Path, str]:
    try:
        obj: dict[str, Any] = json.loads(config_json or "{}")
    except Exception as exc:
        raise BadRequestError(code=error_codes.SOURCE_CONFIG_INVALID, message="config_json must be valid JSON") from exc

    base_path = str(obj.get("base_path", "")).strip()
    kb_id = str(obj.get("kb_id", "")).strip()
    if not base_path or not kb_id:
        raise BadRequestError(
            code=error_codes.SOURCE_CONFIG_INVALID,
            message="config_json must include base_path and kb_id",
        )
    root = Path(base_path)
    if not root.exists() or not root.is_dir():
        raise BadRequestError(code=error_codes.SOURCE_PATH_NOT_FOUND, message=f"source path not found: {base_path}")
    return root, kb_id


def _read_local_files(root: Path) -> list[Path]:
    return sorted([path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".txt"}])


def create_index_job(db: Session, *, source_id: str, mode: str) -> IndexJob:
    source = db.get(KnowledgeSource, source_id)
    if source is None:
        raise NotFoundError(code=error_codes.KNOWLEDGE_SOURCE_NOT_FOUND, message=f"source_id {source_id} not found")
    if source.status != "active":
        raise BadRequestError(code=error_codes.SOURCE_NOT_ACTIVE, message=f"source_id {source_id} is not active")
    if source.source_type != "local":
        raise BadRequestError(code=error_codes.SOURCE_TYPE_NOT_SUPPORTED, message="only local source is supported in v0.1")

    job = IndexJob(id=str(uuid.uuid4()), source_id=source_id, mode=mode, status=IndexJobStatus.queued)
    with transactional(db):
        db.add(job)
    run_index_job(db, job_id=job.id)
    db.refresh(job)
    return job


def get_index_job_by_id(db: Session, *, job_id: str) -> IndexJob:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise NotFoundError(code=error_codes.INDEX_JOB_NOT_FOUND, message=f"job_id {job_id} not found")
    return job


def run_index_job(db: Session, *, job_id: str) -> None:
    job = get_index_job_by_id(db, job_id=job_id)
    source = db.get(KnowledgeSource, job.source_id)
    if source is None:
        raise NotFoundError(code=error_codes.KNOWLEDGE_SOURCE_NOT_FOUND, message=f"source_id {job.source_id} not found")

    with transactional(db):
        job.status = IndexJobStatus.running
        job.started_at = dt.datetime.utcnow()
        job.error_message = None

    try:
        root, kb_id = _load_local_config(source.config_json)
        files = _read_local_files(root)

        existing_docs = cast(list[KnowledgeDocument], db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)).all())
        if existing_docs:
            doc_ids = [doc.id for doc in existing_docs]
            with transactional(db):
                db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id.in_(doc_ids)))
                db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id))

        indexed_docs = 0
        with transactional(db):
            for file_path in files:
                raw = file_path.read_text(encoding="utf-8", errors="ignore")
                if not raw.strip():
                    continue

                document = KnowledgeDocument(
                    id=str(uuid.uuid4()),
                    source_id=source.id,
                    title=file_path.name,
                    path=str(file_path),
                    doc_version="1",
                    department=None,
                    permission_scope=kb_id,
                    status="active",
                )
                db.add(document)
                doc_chunks = _chunk_text(raw)
                for idx, content in enumerate(doc_chunks):
                    db.add(
                        KnowledgeChunk(
                            id=str(uuid.uuid4()),
                            doc_id=document.id,
                            chunk_index=idx,
                            content=content,
                            token_count=max(len(content.split()), 1),
                            index_version="1",
                            permission_scope=kb_id,
                        )
                    )
                indexed_docs += 1

            job.total_documents = len(files)
            job.indexed_documents = indexed_docs
            job.status = IndexJobStatus.success
            job.finished_at = dt.datetime.utcnow()
            job.updated_at = dt.datetime.utcnow()
    except Exception as exc:
        with transactional(db):
            job.status = IndexJobStatus.failed
            job.error_message = str(exc)[:2000]
            job.finished_at = dt.datetime.utcnow()
            job.updated_at = dt.datetime.utcnow()
