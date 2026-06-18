from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live")
def health_live():
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready():
    return {"status": "ready"}
