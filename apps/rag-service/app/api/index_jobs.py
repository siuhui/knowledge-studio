import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IndexJob, IndexJobStatus, KnowledgeSource
from ..schemas import ApiResponse, IndexJobCreateRequest, IndexJobDetail, IndexJobPayload

router = APIRouter(prefix="/api/v1/index/jobs", tags=["index-jobs"])


def _trace_id() -> str:
    return str(uuid.uuid4())


@router.post("", response_model=ApiResponse[IndexJobPayload])
def create_index_job(payload: IndexJobCreateRequest, db: Session = Depends(get_db)) -> ApiResponse[IndexJobPayload]:
    source = db.get(KnowledgeSource, payload.source_id)
    if source is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "KNOWLEDGE_SOURCE_NOT_FOUND",
                "message": f"source_id {payload.source_id} not found",
                "data": None,
                "trace_id": _trace_id(),
            },
        )

    job = IndexJob(source_id=payload.source_id, mode=payload.mode, status=IndexJobStatus.queued)
    db.add(job)
    db.commit()
    db.refresh(job)

    return ApiResponse[IndexJobPayload](
        message="accepted",
        data=IndexJobPayload(job_id=job.id, status=job.status.value),
        trace_id=_trace_id(),
    )


@router.get("/{job_id}", response_model=ApiResponse[IndexJobDetail])
def get_index_job(job_id: str, db: Session = Depends(get_db)) -> ApiResponse[IndexJobDetail]:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "INDEX_JOB_NOT_FOUND",
                "message": f"job_id {job_id} not found",
                "data": None,
                "trace_id": _trace_id(),
            },
        )

    return ApiResponse[IndexJobDetail](
        message="success",
        data=IndexJobDetail(
            job_id=job.id,
            source_id=job.source_id,
            mode=job.mode,
            status=job.status.value,
            error_message=job.error_message,
            total_documents=job.total_documents,
            indexed_documents=job.indexed_documents,
            started_at=job.started_at,
            finished_at=job.finished_at,
        ),
        trace_id=_trace_id(),
    )
