"""Langfuse telemetry (v4 SDK).

When ``KB_TELEMETRY__ENABLED=false`` or credentials are missing,
``trace_context()`` returns ``nullcontext()``, ``update_current_span()``
is a no-op, and ``get_current_trace_id()`` returns ``None``.

Credential flow: pydantic-settings (``config.py``) reads from ``.env`` →
``init_telemetry()`` passes values directly to ``Langfuse()`` constructor.
No ``LANGFUSE_*`` environment variables are ever set / needed — the
config is consumed in one place.

Span naming convention
----------------------
Spans use ``{domain}.{operation}`` dot-notation:

    chat.*      — ChatService: conversational Q&A
                  (``chat.message`` sync, ``chat.message.stream`` SSE)
    index.*     — Indexing pipeline: parse → chunk → embed
                  (``index.pipeline``, ``index.parse``, ``index.chunk``,
                  ``index.embed``)
    search.*    — Retrieval: shared by chat and studio (``search.retrieve``)
    agent.*     — Agent runtime (``agent.run``, ``agent.run.stream``)
    studio.*    — Studio (``studio.task`` lifecycle root, child spans:
                  ``studio.report`` → ``studio.report.plan`` /
                  ``studio.report.gather`` / ``studio.report.generate``)

Observation type convention
----------------------------
Langfuse supports typed observations (``agent``, ``tool``, ``retriever``,
``chain``, ``evaluator``, ``generation``, ``embedding``) that enable
per-type filtering and dashboards in the Langfuse UI.  Our mapping:

    @observe(name="agent.run", as_type="agent")
    # Agent decision loop — orchestrates tools with LLM guidance

    @observe(name="agent.tool_call", as_type="tool")
    # Agent tool execution — hybrid_search, read_document, list_documents

    @observe(name="search.retrieve", as_type="retriever")
    # Data retrieval from PostgreSQL + pgvector

    @observe(name="search.crag.evaluate", as_type="evaluator")
    # Assesses relevance/correctness of retrieved results

    @observe(name="...", as_type="chain")
    # Pipeline steps: chat.message, search.rewrite, search.crag.*,

    # LLM and embedding calls are auto-traced by ``langfuse.openai``
    # → ``generation`` and ``embedding`` types (no manual spans needed)

The default ``@observe`` without ``as_type`` produces a generic ``span``
observation.  We use typed observations for all new retrieval-pipeline
spans so the UI can distinguish agent reasoning from tool execution
from retrieval queries without relying on name-prefix conventions.

LLM and embedding calls are auto-traced by ``langfuse.openai``
integration — no manual spans needed in ``llm.py`` or ``embedding.py``.
Business-level orchestration spans use ``@observe`` with
``capture_input=False``, ``as_type`` set per the convention above, and
set input/output explicitly via ``update_current_span()``.

Best-practice compliance:

- Framework integrations (``langfuse.openai``) are preferred over manual
  ``child_span(…, as_type="generation")`` for LLM/embedding calls.
- ``@observe`` uses ``capture_input=False``; relevant input is set
  explicitly via ``update_current_span()`` to avoid leaking internals.
- Span names map to project architecture domains, not generic categories
  like "rag".
- Observation types (``as_type``) are set on every ``@observe`` so the
  Langfuse UI can show typed views (agent traces, tool latency, retrieval
  quality) without manual filtering.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING, Any, Literal

import structlog

from app.config import settings

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from langfuse import Langfuse

logger = structlog.get_logger(__name__)

_client: Langfuse | None = None


# ── Re-export @observe (no-op safe when langfuse is not installed) ─────────


def _noop_observe(*args: Any, **kwargs: Any) -> Any:
    """Pass-through decorator used when langfuse is unavailable."""
    if args and callable(args[0]):
        return args[0]  # @observe (no parens)
    return lambda fn: fn  # @observe(...) (with parens)


try:
    from langfuse import observe  # noqa: F401
except ImportError:
    observe = _noop_observe

__all__ = [
    "observe",
    "update_current_span",
    "trace_context",
    "get_current_trace_id",
    "create_score",
    "init_telemetry",
    "shutdown_telemetry",
]


# ── Guard ────────────────────────────────────────────────────────────────────


def _is_configured() -> bool:
    if not settings.telemetry.enabled:
        return False
    pk = settings.telemetry.langfuse_public_key
    sk = settings.telemetry.langfuse_secret_key
    return pk is not None and sk is not None


# ── Public API (no-op safe when telemetry is disabled) ────────────────────────


def update_current_span(
    *,
    name: str | None = None,
    input: Any | None = None,  # noqa: A002
    output: Any | None = None,
    metadata: dict[str, Any] | None = None,
    version: str | None = None,
    level: Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"] | None = None,
    status_message: str | None = None,
) -> None:
    """Update the current span's input / output / metadata, or no-op.

    Usage inside an ``@observe``-decorated function::

        update_current_span(input={"query": content}, output={"answer": answer})
    """
    if _client is None:
        return
    _client.update_current_span(
        name=name,
        input=input,
        output=output,
        metadata=metadata,
        version=version,
        level=level,
        status_message=status_message,
    )


def trace_context(**attrs: Any) -> AbstractContextManager[None]:
    """Propagate trace-level attributes (user_id, session_id, tags, etc.).

    Usage::

        with trace_context(user_id=uid, session_id=sid, tags=["chat"]):
            ...
    """
    if _client is None:
        return nullcontext()

    from langfuse import propagate_attributes

    return propagate_attributes(**attrs)


def get_current_trace_id() -> str | None:
    """Return the current W3C trace ID, or None if disabled."""
    if _client is None:
        return None
    return _client.get_current_trace_id()


def create_score(
    *,
    name: str,
    value: float,
    comment: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Record a score on the current trace, or no-op when telemetry is disabled.

    ``trace_id`` defaults to the current trace via ``get_current_trace_id()``.
    """
    if _client is None:
        return
    tid = trace_id or _client.get_current_trace_id()
    if tid is None:
        return
    _client.create_score(trace_id=tid, name=name, value=value, comment=comment or "")


# ── Lifecycle ────────────────────────────────────────────────────────────────


def init_telemetry() -> None:
    """Initialise Langfuse client.

    Call once per worker inside the FastAPI lifespan.  Credentials are
    passed directly to ``Langfuse()`` — no ``LANGFUSE_*`` env vars needed.
    ``get_client()`` / ``@observe`` / ``propagate_attributes`` discover
    the registered instance through the SDK's ``LangfuseResourceManager``.
    """
    global _client

    if not _is_configured():
        logger.info("telemetry disabled or unconfigured")
        return

    pk = settings.telemetry.langfuse_public_key
    sk = settings.telemetry.langfuse_secret_key
    # Narrow SecretStr | None → SecretStr for type checker
    if pk is None or sk is None:
        return  # unreachable — _is_configured() returned True above

    from langfuse import Langfuse

    kwargs: dict[str, Any] = {
        "public_key": pk.get_secret_value(),
        "secret_key": sk.get_secret_value(),
        "environment": settings.telemetry.environment,
        "release": settings.telemetry.release,
    }
    if settings.telemetry.langfuse_base_url is not None:
        kwargs["base_url"] = settings.telemetry.langfuse_base_url

    _client = Langfuse(**kwargs)

    if not _client.auth_check():
        logger.warning("telemetry auth check failed — client will not export traces")
        _client.shutdown()
        _client = None
        return

    logger.info(
        "telemetry initialized",
        base_url=settings.telemetry.langfuse_base_url,
        environment=settings.telemetry.environment,
    )


def shutdown_telemetry() -> None:
    """Flush pending spans and shut down background exporters on shutdown."""
    if _client is not None:
        _client.shutdown()
        logger.debug("telemetry shutdown complete")
