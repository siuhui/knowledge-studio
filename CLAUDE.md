# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

KnowledgeBase — a local knowledge retrieval and AI analysis tool (v0.1.0). Python FastAPI backend + Next.js 15 frontend + PostgreSQL 16 with pgvector + MinIO object storage. RAG pipeline: upload documents → parse → chunk → embed → hybrid search → LLM answer with citations.

## Development

Dependencies (PostgreSQL 16 + pgvector, MinIO) must already be running — manage these manually.

### Backend (`apps/api/`)

All backend commands require the venv activated first.

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger at `http://localhost:8000/docs`.

### Frontend (`apps/web/`)

```bash
cd apps/web
pnpm dev        # http://localhost:3000, HMR
```

## Testing

### Backend

```bash
cd apps/api
# Activate venv first — then:
pytest                                    # all tests
pytest tests/api/test_auth.py             # single file
pytest -m "not slow"                      # skip slow tests
```

Tests require a local `knowledgebase_test` database. [tests/conftest.py](apps/api/tests/conftest.py) creates/drops all tables per session. Test architecture: session-scoped `engine` → per-test transactional `db` session (rolls back after each test, no cleanup needed) → `client` fixture overrides `get_db` dependency. The `auth_headers` fixture registers + logs in a test user.

### Frontend

```bash
cd apps/web
pnpm test           # vitest
pnpm test -- --coverage
```

## Verification (quality gate)

Run before committing. Catch failures early — don't push red.

### Backend

```bash
cd apps/api
# Activate venv first (see table above) — then:
ruff check .        # lint
ruff format .       # format
mypy app/           # type check (strict mode)
```

### Frontend

```bash
cd apps/web
pnpm lint           # biome lint
pnpm format         # biome format
pnpm typecheck      # tsc --noEmit
```

## Architecture

### Data model chain

```
User ──1:N──> KnowledgeBase ──1:N──> Source ──1:N──> Document ──1:N──> Chunk
```

5 tables. No roles/permissions/teams — `knowledge_base.user_id` for ownership, access controlled by query filtering in services.

### Backend layered architecture

```
api/            → thin: extract params, call service, wrap ApiResponse[T]. No SQL.
services/       → business logic, orchestrate repositories, call external APIs
repositories/   → data access, encapsulate SQLAlchemy queries. No business logic.
models/         → ORM mappings only. No logic.
core/           → cross-cutting: config, errors, security, logging, trace. No upward refs.
```

Call direction: `api → service → repository → db`. Service layer raises typed exceptions (`NotFoundError`, `ForbiddenError`, `ValidationError`, etc.) which global handlers in [core/exceptions.py](apps/api/app/core/exceptions.py) catch. API routes never write try-except.

All service and repository classes use **static methods** — no class state, just namespace grouping.

### Configuration

pydantic-settings with `KB_` prefix and `__` nested delimiter. Nested config classes: `DatabaseConfig`, `JWTConfig`, `LLMConfig`, `ObjectStorageConfig`. Module-level singleton `settings` in [config.py](apps/api/app/config.py). Sensitive fields use `SecretStr`. `.env` / `.env.local` are gitignored; `.env.example` is the committed template.

### Schema migration

v0.1.0: `Base.metadata.create_all()` at startup (controlled by `KB_AUTO_CREATE_TABLES=true`). pgvector extension created with `CREATE EXTENSION IF NOT EXISTS`. Will switch to Alembic at v1.0.0.

### RAG pipeline

1. **Parse** — file → raw text via format-specific parsers ([services/indexing/parser.py](apps/api/app/services/indexing/parser.py)). PDF via PyMuPDF, Markdown via regex (strip frontmatter/images), plain text with charset detection. Parser registry: `PARSERS` dict maps format string → `Parser` Protocol.
2. **Chunk** — paragraph-aware fixed-window (512 tokens, 50 overlap). Self-written, no LangChain. ([services/indexing_service.py](apps/api/app/services/indexing_service.py))
3. **Embed** — OpenAI `text-embedding-3-small` (1536d) via Protocol abstraction. Lazy client init. ([services/embedding.py](apps/api/app/services/embedding.py))
4. **Search** — hybrid: pgvector cosine distance + PostgreSQL `tsvector` full-text, fused with Reciprocal Rank Fusion. Re-ranker is identity pass (v0.1.0). ([services/retrieval/](apps/api/app/services/retrieval/))
5. **Answer** — retrieved chunks → context string → LLM (OpenAI or Anthropic, Protocol abstraction, lazy client). ([services/llm.py](apps/api/app/services/llm.py))

Deduplication: `document.content_hash` (SHA-256 of parsed text) checked before chunk+embed to skip re-indexing identical content. `source.source_hash` is reserved for v0.2.0.

### Response format

All API responses wrapped in `ApiResponse[T]`:
```json
{ "code": "OK", "message": "success", "data": { ... } }
```

`X-Request-ID` header on every response (middleware generates uuid4 if not provided by client). Paginated lists use `PaginatedResponse[T]` with `meta` field.

### Error handling

[ResponseCode](apps/api/app/core/response_codes.py) `StrEnum` — every error path gets a specific code (e.g. `KNOWLEDGE_BASE_NOT_FOUND`, `TOKEN_INVALID`). Service layer raises typed errors from [core/errors.py](apps/api/app/core/errors.py): `NotFoundError(404)`, `ValidationError(422)`, `UnauthorizedError(401)`, `ForbiddenError(403)`, `ConflictError(409)`. Global handlers in [core/exceptions.py](apps/api/app/core/exceptions.py) catch `AppError` and unhandled `Exception`.

### Logging

structlog with JSON output in production, console renderer in dev. Context variables (`request_id`, `user_id`) bound in middleware/dependencies and automatically merged into every log line. Log at service layer, not in repositories.

### Frontend patterns

- App Router (`src/app/`), Server Components by default, `"use client"` for interactivity
- Auth token in `localStorage` under `kb_access_token`, managed by [lib/auth.ts](apps/web/src/lib/auth.ts)
- Unified fetch wrapper in [lib/api.ts](apps/web/src/lib/api.ts) — generates `X-Request-ID`, attaches auth header, throws `ApiError` on non-OK
- Shared types in [lib/types.ts](apps/web/src/lib/types.ts) mirror backend schema shapes
- Styling: Tailwind CSS v4

### Key design decisions

- **No RAG frameworks** (LangChain, LlamaIndex). Pipeline logic is hand-written for direct control.
- **Modular monolith**, not microservices.
- **PostgreSQL + pgvector** for both vector and keyword search. No Elasticsearch/Pinecone.
- **LLM + Embedding via API** only — the sole external dependency. All text data stays local.
- **Branching**: master-only (personal project), conventional commits (`feat:`/`fix:`/`refactor:`/`docs:`/`test:`/`chore:`).
