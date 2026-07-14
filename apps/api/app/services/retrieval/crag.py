"""CRAG (Corrective RAG) — relevance evaluation and corrective retrieval.

Evaluates whether retrieved results can answer the user's question. When
results are irrelevant, corrects the query direction and re-searches — at
most once. After two failed attempts the system honestly reports "not found".

Only handles "retrieval succeeded but quality is insufficient". Infrastructure
failures (both retrieval paths down) are detected upstream and bypass CRAG.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

from app.core.telemetry import create_score, observe, update_current_span

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.schemas.retrieval.response import RetrievalChunk, RetrievalQueryResponse
    from app.services.llm import LLMProvider

logger = structlog.get_logger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────


class RelevanceGrade(StrEnum):
    RELEVANT = "relevant"  # results are sufficient to answer
    PARTIAL = "partial"  # results are on-topic but incomplete
    IRRELEVANT = "irrelevant"  # results are off-topic or empty


@dataclass
class CragResult:
    """CRAG decision with the chunks to use (if any) and a user-facing message."""

    action: str  # "answer" | "not_found" | "error"
    chunks: list[RetrievalChunk] = field(default_factory=list)
    message: str | None = None  # user-facing message for not_found / error


# ── Helpers ───────────────────────────────────────────────────────────────────


def _summarize_results(results: list[RetrievalChunk], max_items: int = 5) -> str:
    """Build a short text summary of search results for the LLM prompt."""
    if not results:
        return "(no results found)"
    parts: list[str] = []
    for i, r in enumerate(results[:max_items]):
        parts.append(f"[{i + 1}] {r.document_title}: {r.content[:200]}")
    return "\n".join(parts)


# ── Relevance evaluation ──────────────────────────────────────────────────────


@observe(name="search.crag.evaluate", as_type="evaluator", capture_input=False, capture_output=False)
def evaluate_relevance(
    llm: LLMProvider,
    question: str,
    results: list[RetrievalChunk],
) -> tuple[RelevanceGrade, str]:
    """Assess whether search results can answer the user's question.

    1 LLM call. Returns (grade, reason).  ``reason`` is a brief
    natural-language explanation usable for logging and frontend display.
    """
    if not results:
        return RelevanceGrade.IRRELEVANT, "No results found"

    summaries = []
    for i, r in enumerate(results[:10]):
        summaries.append(f"[{i + 1}] {r.document_title}: {r.content[:200]}...")

    prompt = f"""\
Evaluate whether these search results can answer the user's question.

Question: {question}

Search results:
{chr(10).join(summaries)}

Judge:
- "relevant"   — results contain enough information to answer the question
- "partial"    — results are on-topic but incomplete, need targeted supplementary search
- "irrelevant" — results are off-topic or empty

Output JSON:
{{"grade": "relevant|partial|irrelevant", "reason": "brief explanation"}}"""

    response = llm.generate(system_prompt="", messages=[{"role": "user", "content": prompt}])

    update_current_span(
        input={"question": question[:200], "chunk_count": len(results)},
        output={"response": response[:300]},
    )

    # Parse
    try:
        data = json.loads(response)
        grade_str = data.get("grade", "irrelevant")
        reason = data.get("reason", "")
    except (json.JSONDecodeError, TypeError):
        grade_str = "irrelevant"
        reason = "Failed to parse CRAG evaluation response"

    # Map to enum
    grade_map = {
        "relevant": RelevanceGrade.RELEVANT,
        "partial": RelevanceGrade.PARTIAL,
        "irrelevant": RelevanceGrade.IRRELEVANT,
    }
    grade = grade_map.get(grade_str, RelevanceGrade.IRRELEVANT)

    # Write score for Langfuse UI filtering/aggregation
    score_value = {
        "relevant": 1.0,
        "partial": 0.5,
        "irrelevant": 0.0,
    }[grade.value]
    create_score(
        name="relevance_grade",
        value=score_value,
        comment=reason,
    )

    logger.debug("crag evaluation complete", grade=grade.value, reason=reason[:120])
    return grade, reason


# ── Supplement query generation ───────────────────────────────────────────────


@observe(name="search.crag.supplement", as_type="chain", capture_input=False, capture_output=False)
def _generate_supplement_query(
    llm: LLMProvider,
    question: str,
    results: list[RetrievalChunk],
) -> str:
    """Generate a targeted supplementary query for partial results. 1 LLM call."""
    summary = _summarize_results(results[:5])
    prompt = f"""\
The search results for this question are partially relevant but incomplete.

Question: {question}

Current results:
{summary}

What specific angle or sub-topic is missing? Generate ONE focused search query
that would fill the gap.

Output JSON:
{{"query": "supplementary search query"}}"""

    response = llm.generate(system_prompt="", messages=[{"role": "user", "content": prompt}])

    try:
        data = json.loads(response)
        return str(data.get("query", question))
    except (json.JSONDecodeError, TypeError):
        return question


# ── Full CRAG decision flow ───────────────────────────────────────────────────


def crag_evaluate_and_act(
    db: Session,
    *,
    query: str,
    retrieval: RetrievalQueryResponse,
    retry_count: int,
    llm: LLMProvider,
    kb_id: str,
) -> CragResult:
    """Full CRAG flow: evaluate → decide → (optionally) correct → re-evaluate.

    ``retry_count`` must be 0 (first attempt) or 1 (after one correction).
    The hard cap of one correction prevents infinite loops when the KB
    genuinely lacks the information.

    Re-search is performed through ``RetrievalService.search()`` so both
    existing strategies (agentic / hybrid) are supported.
    """
    from app.services.retrieval.query_rewriter import correct_query
    from app.services.retrieval.service import RetrievalService

    # ── Empty results, already retried → not_found ──
    if not retrieval.results and retry_count >= 1:
        return CragResult(action="not_found", message="No relevant information found in the knowledge base.")

    # ── Evaluate ──
    grade, reason = evaluate_relevance(llm, query, retrieval.results)

    if grade == RelevanceGrade.RELEVANT:
        return CragResult(action="answer", chunks=list(retrieval.results))

    if grade == RelevanceGrade.PARTIAL:
        supplement_query = _generate_supplement_query(llm, query, retrieval.results)
        sup_retrieval = RetrievalService.search(
            db,
            query=supplement_query,
            knowledge_base_id=kb_id,
            top_k=10,
        )
        all_chunks = list(retrieval.results) + list(sup_retrieval.results)
        return CragResult(action="answer", chunks=all_chunks)

    # ── Irrelevant ──
    if grade == RelevanceGrade.IRRELEVANT:
        if retry_count >= 1:
            return CragResult(action="not_found", message="No relevant information found in the knowledge base.")

        # First irrelevant → correct and re-search
        corrected = correct_query(llm, query, _summarize_results(retrieval.results))
        if not corrected:
            return CragResult(action="not_found", message="No relevant information found in the knowledge base.")

        new_retrieval = RetrievalService.search(
            db,
            query=corrected[0],
            knowledge_base_id=kb_id,
            top_k=10,
        )
        return crag_evaluate_and_act(
            db,
            query=query,
            retrieval=new_retrieval,
            retry_count=1,
            llm=llm,
            kb_id=kb_id,
        )

    # Unreachable — all enum members handled above
    return CragResult(action="error", message="Retrieval evaluation error")
