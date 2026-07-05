# CLAUDE.md

This file provides guidance for AI coding agents working in this repository.

See @docs/architecture.md for detailed design, @docs/data-model.md for the data model, and @docs/engineering-standards.md for engineering standards.

## Commands

```bash
# Backend
cd apps/api
source .venv/Scripts/activate          # Windows Git Bash（Linux/macOS: .venv/bin/activate）
uvicorn app.main:app --reload --port 8000
pytest                                    # all tests (needs knowledgebase_test db)
pytest tests/api/test_auth.py             # single file
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
                                            │                      │
                                     ChatSession ──1:N──> ChatMessage
Document ──1:1──> DocumentIndexStatus

RAG: parse → chunk → embed → search (agentic=default, hybrid=optional) → LLM answer
      indexing/pipeline.py                 retrieval/strategies/
```

Key modules:
- `services/agent/` — generic ReAct loop (`AgentRunner` + `AgentConfig`), business-agnostic
- `services/retrieval/strategies/` — `agentic` (FTS on full_text, zero embedding) + `hybrid` (pgvector+RRF)
- `services/llm.py` — `LLMProvider` Protocol: `generate()`, `generate_with_tools()`, `generate_stream()`
- `services/chat.py` — `send_message` (sync) + `stream_message` (SSE async generator)
- `core/telemetry.py` — Langfuse v4: `@observe()`, `langfuse.openai` auto-tracing, no-op when disabled
- `services/indexing/pipeline.py` — 3-stage (parse→chunk→embed), independent commits per stage, resume-safe

## Key conventions

- **API responses**: `ApiResponse[T]` (`{code, message, data}`); `X-Request-ID` header; `PaginatedResponse[T]` with `meta`
- **Errors**: service raises typed errors (`NotFoundError`, `ValidationError`, etc.); API never try-except; global handlers in `core/exceptions.py`
- **Config**: pydantic-settings, `KB_` prefix, `__` nested delimiter. Nested classes: `DatabaseConfig`, `JWTConfig`, `LLMConfig`, `EmbeddingConfig`, `ObjectStorageConfig`, `TelemetryConfig`. `SecretStr` for secrets.
- **DB**: snake_case singular table names; `Base.metadata.create_all()` (v0.x); Alembic at v1.x; pgvector extension auto-created
- **File naming**: omit redundant layer suffixes — `services/auth.py` not `auth_service.py`, `repositories/user.py` not `user_repository.py` (the directory already provides context)
- **Logging**: structlog, JSON in prod; log at service layer only; never log in repositories
- **Frontend**: App Router, `"use client"` for interactivity; `lib/api.ts` fetch wrapper; `lib/sse.ts` SSE parser; Tailwind CSS v4

## Gotchas

- **Anthropic `generate_with_tools()` raises `NotImplementedError`** — agent mode requires OpenAI-compatible provider
- **Agentic search needs no Chunk or embedding** — runs on `Document.full_text` via PostgreSQL FTS only
- **embedding dimension is configurable** (`KB_EMBEDDING__DIMENSION`, default 1024), not hardcoded
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
