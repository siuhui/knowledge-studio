from fastapi import APIRouter, HTTPException, Request

from ..database import is_database_ready
from ..core.trace import get_trace_id

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live(request: Request) -> dict[str, str]:
    return {"status": "ok", "trace_id": get_trace_id(request)}


@router.get("/ready")
def ready(request: Request) -> dict[str, str]:
    if not is_database_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DEPENDENCY_NOT_READY",
                "message": "database is not ready",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )
    return {"status": "ready", "trace_id": get_trace_id(request)}
