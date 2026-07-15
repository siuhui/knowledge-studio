# Knowledge Studio (WIP)

Ingest, ask, generate — all powered by AI.

## Features

- **Ingest** — Upload PDF, Markdown, plain text, or import from URLs. Content is automatically parsed, chunked, and indexed for search.
- **Ask** — Ask questions in natural language and get answers with source citations. Supports multi-turn conversation with streaming output.
- **Generate** — Produce structured multi-chapter reports from the content in your knowledge base.
- **Observe** — Built-in tracing across every LLM call and retrieval step.

## Quick Start

**Prerequisites:** Docker & Docker Compose, an OpenAI-compatible API key.

```bash
git clone https://github.com/siuhui/knowledge-studio.git
cd knowledge-studio

cp apps/api/.env.example apps/api/.env
# Edit .env: fill in KS_LLM__API_KEY and KS_EMBEDDING__API_KEY

docker compose -f infra/docker-compose.yml up -d
```

Open [http://localhost:3000](http://localhost:3000), register an account, create a knowledge base, and upload your first document.

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 (minioadmin / minioadmin) |

## Development

Two ways to run in development

### Docker Compose (hot reload)

Full stack with live reload for both API and frontend. Database and MinIO data are bind-mounted to `infra/data/` so they survive container teardown.

```bash
cp apps/api/.env.example apps/api/.env
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d
```

### Local (manual)

Run only infrastructure in Docker, start backend and frontend manually for the fastest feedback loop.

**Requirements:** Python 3.12+, pnpm (for Node.js 20+).

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d db minio

# Backend
cd apps/api
cp .env.example .env
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash (Linux/macOS: .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd apps/web
pnpm install && pnpm dev
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Database | PostgreSQL 16 + pgvector |
| Storage | MinIO (S3-compatible) |
| Frontend | Next.js 15, React 19, Tailwind CSS v4 |
| AI | OpenAI-compatible API, Anthropic |
| Telemetry | Langfuse (OpenTelemetry) |

## Documentation

- [Product Requirements](docs/prd.md)
- [Architecture & Design](docs/architecture.md)
- [Data Model](docs/data-model.md)
- [Engineering Standards](docs/engineering-standards.md)

## License

MIT
