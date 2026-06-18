from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, documents, health, knowledge_bases, retrieval, sources
from app.config import settings
from app.core.exceptions import AppError, app_error_handler, general_exception_handler
from app.core.logging import setup_logging
from app.core.middlewares import register_middlewares
from app.database import Base, engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("starting up", app_name=settings.app_name, env=settings.env)

    if settings.auto_create_tables:
        # Ensure pgvector extension
        with engine.connect() as conn:
            conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {settings.database.pg_vector_extension}"))
            conn.commit()
        Base.metadata.create_all(bind=engine)
        logger.info("tables created", auto_create_tables=True)

    yield

    # Shutdown
    logger.info("shutting down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
register_middlewares(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Routes
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(knowledge_bases.router)
app.include_router(sources.router)
app.include_router(documents.router)
app.include_router(retrieval.router)
