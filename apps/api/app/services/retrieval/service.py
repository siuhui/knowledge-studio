"""Retrieval service — strategy dispatcher.

Delegates to registered SearchStrategy implementations.  The default
strategy is "agentic" (multi-round LLM-driven keyword search, zero
embedding cost).  "hybrid" is available as an opt-in alternative.
"""

import structlog
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.core.response_codes import ResponseCode
from app.core.telemetry import observe, update_current_span
from app.schemas.retrieval.response import RetrievalQueryResponse

logger = structlog.get_logger(__name__)


class RetrievalService:
    """Thin dispatch layer over registered search strategies.

    Call sites only need to know the strategy name; the service looks up
    the implementation and delegates.  Strategy implementations live under
    ``services/retrieval/strategies/``.
    """

    DEFAULT_STRATEGY = "agentic"

    @staticmethod
    @observe(name="search.retrieve", capture_input=False, capture_output=False)
    def search(
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
        document_ids: list[str] | None = None,
        strategy: str | None = None,
    ) -> RetrievalQueryResponse:
        # Import strategies here to trigger @register decorators.
        # Lazy import avoids circular deps (strategies import from this package).
        from app.services.retrieval.strategies import STRATEGIES

        strategy_name = strategy or RetrievalService.DEFAULT_STRATEGY

        update_current_span(
            input={
                "query": query[:200],
                "top_k": top_k,
                "strategy": strategy_name,
            },
        )

        impl = STRATEGIES.get(strategy_name)
        if impl is None:
            available = sorted(STRATEGIES.keys())
            raise ValidationError(
                code=ResponseCode.SEARCH_STRATEGY_UNKNOWN,
                message=(f"Unknown search strategy: '{strategy_name}'. Available: {available}"),
            )

        logger.debug(
            "dispatching search",
            strategy=strategy_name,
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
        )

        result = impl.search(
            db,
            query=query,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            document_ids=document_ids,
        )

        update_current_span(
            output={
                "results_count": len(result.results),
                "top_score": result.results[0].score if result.results else None,
            },
        )

        return result
