# CLAUDE.md

This file provides guidance for AI coding agents working in this repository.

See @docs/architecture.md for detailed design, @docs/data-model.md for the data model, and @docs/engineering-standards.md for engineering standards.

## Commands

```bash
# Backend
cd apps/api
source .venv/Scripts/activate          # Windows Git Bash（Linux/macOS: .venv/bin/activate）
uvicorn app.main:app --reload --port 8000
pytest tests/unit                         # unit only — no DB, ~0.5s
pytest tests/integration                  # integration — needs knowledge_studio_test db
pytest tests/integration/api/test_auth.py # single file
ruff check . && ruff format . && mypy app/  # quality gate（mypy=strict in pyproject.toml）

# Frontend
cd apps/web
pnpm dev                    # http://localhost:3000
pnpm test                   # vitest
pnpm lint && pnpm format && pnpm typecheck  # quality gate
```

## Architecture at a glance

```
api/ → services/ → repositories/ → db     (all classes use static methods)
models/  → ORM only, no logic
core/    → cross-cutting: config, errors, security, logging, trace, telemetry

User ──1:N──> KnowledgeBase ──1:N──> Source ──1:N──> Document ──1:N──> Chunk
              │                                                    │
              ├─1:N──> ChatSession ──1:N──> ChatMessage            │
              └─1:N──> StudioTask                    Document ──1:1─┴─> DocumentIndexStatus

9 tables (studio_task added for report generation; status_enums.py is enums, not a table)

RAG: parse → chunk → embed → search (route_and_rewrite LLM routes direct/agentic per query) → LLM answer
      ingestion/  indexing/pipeline.py       retrieval/service.py (inline dispatch)
```

Key modules:
- `services/agent/` — generic ReAct loop (`AgentRunner` + `AgentConfig`), business-agnostic
- `services/retrieval/service.py` — `RetrievalService.search()` dispatches inline (if/elif) between `direct` (default, single-pass hybrid + CRAG) and `agentic` (multi-round agent); `DEFAULT_MODE="direct"`
- `services/llm.py` — `LLMProvider` Protocol: `generate()`, `generate_with_tools()`, `generate_stream()`
- `services/chat.py` — `send_message` (sync) + `stream_message` (SSE async generator); `route_and_rewrite()` picks `direct`/`agentic` per query, `search_mode` can force it
- `services/ingestion/` — fetch + parse (`parser.py` PDF/MD/TXT registry, `extractors.py` URL via trafilatura + Playwright fallback) → `Document.full_text`
- `services/studio/` — `StudioTaskRunner` + `ReportWorkflow` (plan→gather→generate→assemble→store); report only, no PPT yet
- `core/telemetry.py` — Langfuse v4: `@observe()`, `langfuse.openai` auto-tracing, no-op when disabled
- `services/indexing/pipeline.py` — chunk→embed only (parse lives in `ingestion/`); independent commits per stage, resume-safe

## Key conventions

- **API responses**: `ApiResponse[T]` (`{code, message, data}`); `X-Request-ID` header; `PaginatedResponse[T]` with `meta`
- **Errors**: service raises typed errors (`NotFoundError`, `ValidationError`, etc.); API never try-except; global handlers in `core/exceptions.py`
- **Config**: pydantic-settings, `KS_` prefix, `__` nested delimiter. Nested classes: `DatabaseConfig`, `JWTConfig`, `LLMConfig`, `EmbeddingConfig`, `ObjectStorageConfig`, `TelemetryConfig`, `IngestionConfig`. `SecretStr` for secrets.
- **DB**: snake_case singular table names; `Base.metadata.create_all()` (v0.x); Alembic at v1.x; pgvector extension auto-created
- **File naming**: omit redundant layer suffixes — `services/auth.py` not `auth_service.py`, `repositories/user.py` not `user_repository.py` (the directory already provides context)
- **Logging**: structlog, JSON in prod; log at service layer only; never log in repositories
- **Frontend**: App Router, `"use client"` for interactivity; `lib/api.ts` fetch wrapper; `lib/sse.ts` SSE parser; Tailwind CSS v4

## Gotchas

- **Anthropic `generate_with_tools()` raises `NotImplementedError`** — agent mode requires OpenAI-compatible provider
- **Both retrieval modes depend on Chunk** — agentic uses `hybrid_search` (Chunk-level FTS + vector + RRF), direct uses `hybrid_retrieve` same pipeline
- **embedding dimension is configurable** (`KS_EMBEDDING__DIMENSION`, default 1024), not hardcoded
- **`Document.status` ≠ indexing progress** — content lifecycle only (`pending/ready/failed`); chunk/embed state is in `DocumentIndexStatus` (1:1)
- **`source_id` is nullable** on Document (SET NULL on source delete); **`knowledge_base_id` is not nullable** — it's the canonical KB reference, not just denormalization (required because source can be deleted)
- **Source must be created first (pending)**, *then* upload fills it → complete activates → triggers background indexing
- **S3 key format**: `uploads/{kb_id}/{source_id}/{opaque_token}/{sanitized_name}` — server-generated, source-scoped
- **Indexing pipeline is 3-stage with independent commits** — each stage commits before starting the next; resume-safe on retry
- **DbSession = scope="function"** (auto-commit/rollback per-request); **DbSessionStreaming = scope="request"** (stays alive for SSE response)

## What NOT to do

- Don't add RAG frameworks (LangChain, LlamaIndex) — pipeline is hand-written
- Don't add Elasticsearch / Pinecone / Meilisearch — PostgreSQL+pgvector is the only search backend
- Don't merge `generate()` and `generate_with_tools()` — they serve different call sites with incompatible parameter sets
- Don't log in repositories — service layer only
- Don't use `print()` for logging — structlog only
- Don't put business logic in models — ORM mappings only
- Don't write SQL in API routes — thin layer, delegate to services
- Don't create tables for intermediate pipeline stages — only persist at Document/DocumentIndexStatus/Chunk boundaries
- **Don't write Alembic migrations or backward-compat shims** — v0.x, no production data, `Base.metadata.create_all()` drops and recreates. Schema changes go directly in model files; old DB is discarded
