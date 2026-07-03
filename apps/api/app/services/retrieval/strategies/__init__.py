"""Search strategy protocol and registry.

Each strategy implements SearchStrategy.search() and returns a uniform
RetrievalQueryResponse.  Strategies are registered via the @register
decorator and looked up by name at dispatch time.
"""

from collections.abc import Callable
from typing import Protocol, TypeVar

from sqlalchemy.orm import Session

from app.schemas.retrieval.response import RetrievalQueryResponse


class SearchStrategy(Protocol):
    """Retrieval strategy protocol.

    Every strategy implements search() with the same signature so
    RetrievalService can dispatch without knowing which strategy is active.
    """

    def search(
        self,
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
        document_ids: list[str] | None = None,
    ) -> RetrievalQueryResponse: ...


# ── Strategy registry ──────────────────────────────────────────────────────────

STRATEGIES: dict[str, SearchStrategy] = {}

_T = TypeVar("_T", bound=type)


def register(name: str) -> Callable[[_T], _T]:
    """Decorator that registers a strategy class under *name*.

    Usage::

        @register("agentic")
        class AgenticSearchStrategy:
            ...
    """

    def decorator(cls: _T) -> _T:
        STRATEGIES[name] = cls()
        return cls

    return decorator


# ── Strategy discovery ──────────────────────────────────────────────────────────


def _discover_strategies() -> None:
    """Import all strategy modules so @register decorators fire.

    Each module under ``strategies/`` registers itself via the @register
    decorator when imported.  This function is called once at module load
    time to populate the STRATEGIES registry.

    To add a new strategy: create a new module in this package, decorate
    your class with ``@register("name")``, then add an import line here.
    """
    import app.services.retrieval.strategies.agentic  # noqa: F401
    import app.services.retrieval.strategies.hybrid  # noqa: F401


_discover_strategies()
