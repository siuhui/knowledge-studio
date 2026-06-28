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
2. **Chunk** — paragraph-aware fixed-window (512 tokens, 50 overlap). Self-written, no LangChain. ([services/index_pipeline.py](apps/api/app/services/index_pipeline.py))
3. **Embed** — OpenAI `text-embedding-3-small` (1536d) via Protocol abstraction. Lazy client init. ([services/embedding.py](apps/api/app/services/embedding.py))
4. **Search** — hybrid: pgvector cosine distance + PostgreSQL `tsvector` full-text, fused with Reciprocal Rank Fusion. Re-ranker is identity pass (v0.1.0). ([services/retrieval/](apps/api/app/services/retrieval/))
5. **Answer** — retrieved chunks → context string → LLM (OpenAI or Anthropic, Protocol abstraction, lazy client). ([services/llm.py](apps/api/app/services/llm.py))

Deduplication: `document.content_hash` (SHA-256 of parsed text) checked before chunk+embed to skip re-indexing identical content. `source.source_hash` is reserved for v0.2.0.

### Source module

Source is a **configuration record** — it describes where content comes from, not the content itself. It doesn't track processing state or own files; those belong to Document and ObjectStorage respectively.

**Boundary**:

```
Source (config) ──→ ObjectStorage (binary files)
                ──→ Document (parsed text) ──→ Chunk (indexable segments)
```

| Layer | Responsibility | Statuses |
|---|---|---|
| `source` | Configuration pointer — where content originated | `active`, `inactive`, `error` |
| ObjectStorage | Binary file persistence (MinIO/S3) | N/A — stateless |
| `document` | Parsed text + indexing pipeline progress | `processing`, `active`, `error` |

Source `status` reflects configuration validity (is the S3 object still there? is the URL reachable?), NOT whether documents have been vectorized. Document `status` owns the pipeline lifecycle.

**`source.config`** stores only a reference path, no operational metadata:

```json
// type = "upload"
{ "s3_key": "sources/{kb_id}/{source_id}/paper.pdf", "original_name": "paper.pdf",
  "file_size": 2048576, "mime_type": "application/pdf", "format": "pdf" }

// type = "url" (v0.2.0)
{ "url": "https://...", "crawled_at": null }

// type = "github" (v0.2.0)
{ "repo": "owner/repo", "branch": "main", "path": "docs/", "last_synced": null }
```

**S3 key format**: `uploads/{kb_id}/{random_token}_{sanitized_name}` — server-generated, random token prevents guessing valid keys. The `kb_id` prefix enables `/complete` to validate ownership.

**ObjectStorageService** ([services/object_storage.py](apps/api/app/services/object_storage.py)) — thin boto3/MinIO wrapper. Static methods: `generate_presigned_post`, `head_object`, `get`, `delete`, `delete_prefix`. Lazy client init. Called by API layer orchestration, not injected into services. `head_object` raises `NotFoundError(UPLOAD_OBJECT_NOT_FOUND)` for 404 and `AppError(STORAGE_UNAVAILABLE, 502)` for other boto3 errors.

**Upload flow (presigned POST — browser-to-MinIO direct)**:

```
1. POST /api/v1/uploads/presign   → auth + kb permission → server generates object_key with random token
2. Browser → MinIO direct          → multipart/form-data POST (bytes bypass backend)
3. POST /api/v1/uploads/complete   → validates object_key prefix matches kb_id → head_object → { object_key, filename, size }
4. POST /api/v1/kb/{id}/sources    → SourceService.create(config={s3_key,...}) → BackgroundTasks: index_pipeline
5. GET  /api/v1/sources/{id}/documents → poll for Document status (processing → active)
6. POST /api/v1/sources/{id}/extract  → re-run pipeline from existing s3_key (retry on error)
```

Key design decisions:
- File bytes never pass through the backend — presigned POST goes Browser → MinIO directly.
- `object_key` is always server-generated; `/complete` validates the prefix matches the claimed `kb_id` to prevent cross-KB pollution.
- Content-Type validation is advisory only (browser-supplied, trivially forgeable); the real format check happens in the parser.
- `POST /uploads/complete` validates the object exists in MinIO but does NOT write to the DB. It returns metadata; the frontend calls `POST /sources` with that metadata.
- `SourceService.create` only accepts a complete `config` dict; it doesn't touch files or MinIO.
- Indexing runs via FastAPI `BackgroundTasks` in its own DB session (not the request session).
- `POST /sources/{id}/extract` downloads from MinIO via `ObjectStorageService.get()` and re-runs parse → chunk → embed.

**Delete**: `SourceService.delete` cleans up the MinIO object (via `config.s3_key`) then cascades to Document → Chunk via ORM.

**Orphan cleanup**: Objects in `uploads/` that never become Sources can be cleaned by S3 lifecycle policy (expire after N days) or a cron script that lists `uploads/*` keys and cross-references `source.config.s3_key` values in the database.

### File naming

Service modules under `services/` omit `_service` suffix — the directory already conveys the role. Repository modules under `repositories/` keep `_repository` suffix to avoid name collisions with `models/`.

```
services/auth.py              → AuthService
services/knowledge_base.py    → KnowledgeBaseService
services/document.py          → DocumentService
services/source.py            → SourceService
services/index_pipeline.py    → index_document()  (pipeline: parse → chunk → embed)
services/object_storage.py   → ObjectStorageService (presigned POST, get, delete)
services/embedding.py         → embed()
services/llm.py               → generate()
services/retrieval/           → RetrievalService, hybrid_search, rerank, build_citations
services/indexing/parser.py   → format-specific PARSERS
```

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
