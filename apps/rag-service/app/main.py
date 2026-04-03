from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.health import router as health_router
from .api.index_jobs import router as index_jobs_router
from .api.knowledge_bases import router as knowledge_bases_router
from .api.qa import router as qa_router
from .api.retrieval import router as retrieval_router
from .api.sources import router as sources_router
from .api.teams import router as teams_router
from .api.uploads import router as uploads_router
from .api.users import router as users_router
from .config import settings
from .core.exceptions import register_exception_handlers
from .core.middlewares import trace_id_middleware
from .database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # v0.x prototype mode: allow auto create in local/dev for rapid iteration.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Knowledge Base RAG Service", version="0.1.0", lifespan=lifespan)
app.middleware("http")(trace_id_middleware)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(sources_router)
app.include_router(index_jobs_router)
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(knowledge_bases_router)
app.include_router(uploads_router)
app.include_router(retrieval_router)
app.include_router(qa_router)
