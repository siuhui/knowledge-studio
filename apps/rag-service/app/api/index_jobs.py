from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import ApiResponse, IndexJobCreateRequest, IndexJobDetail, IndexJobPayload
from ..services.index_jobs_service import create_index_job, get_index_job_by_id

router = APIRouter(prefix="/api/v1/index/jobs", tags=["index-jobs"])


@router.post("", response_model=ApiResponse[IndexJobPayload])
def create_index_job_api(
    payload: IndexJobCreateRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[IndexJobPayload]:
    job = create_index_job(db, source_id=payload.source_id, mode=payload.mode)
    return ApiResponse[IndexJobPayload](
        message="accepted",
        data=IndexJobPayload(job_id=job.id, status=job.status.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{job_id}", response_model=ApiResponse[IndexJobDetail])
def get_index_job(job_id: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[IndexJobDetail]:
    job = get_index_job_by_id(db, job_id=job_id)
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
        trace_id=get_trace_id(request),
    )
