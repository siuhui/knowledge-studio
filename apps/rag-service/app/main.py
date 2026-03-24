from fastapi import FastAPI

from .api.health import router as health_router
from .api.index_jobs import router as index_jobs_router
from .api.sources import router as sources_router
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Knowledge Base RAG Service", version="0.1.0")
app.include_router(health_router)
app.include_router(sources_router)
app.include_router(index_jobs_router)
