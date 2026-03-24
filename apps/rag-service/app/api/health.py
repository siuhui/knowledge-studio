import uuid

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok", "trace_id": str(uuid.uuid4())}


@router.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "trace_id": str(uuid.uuid4())}
