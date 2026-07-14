"""Route & Rewrite — 1 LLM call: decontextualize + complexity check + lexical queries.

Single-pass classification that replaces the old two-step (rewrite then route) with
one cheaper call.  Produces a ``RewriteResult`` consumed by ``chat.py`` to branch
between direct (hybrid + CRAG) and agentic (multi-round agent) retrieval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

from app.core.telemetry import create_score, observe, update_current_span

if TYPE_CHECKING:
    from app.services.llm import LLMProvider

logger = structlog.get_logger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────


class SearchMode(StrEnum):
    DIRECT = "direct"
    AGENTIC = "agentic"


@dataclass
class RewriteResult:
    """Output of one-pass route & rewrite.

    ``lexical_queries`` is always non-empty — direct mode uses them for
    hybrid retrieval; agentic mode passes them as hints to the agent.
    """

    mode: SearchMode
    reason: str
    semantic_query: str  # decontextualized, standalone version of the question
    lexical_queries: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.lexical_queries:
            self.lexical_queries = [self.semantic_query]


# ── Routing prompt ────────────────────────────────────────────────────────────

_ROUTE_PROMPT = """\
You are a query understanding router. Your job is to analyse the user's question
(and any conversation history) and produce a structured output.

## Step 1 — Decontextualize
If the question refers to previous messages (pronouns like "it", "they", "that",
or ellipsis like "and what about security?"), rewrite it into a fully standalone
question.  If it is already standalone, return it as-is.

## Step 2 — Classify complexity
Decide whether the question can be answered with a SINGLE search pass ("direct")
or needs MULTI-ROUND agentic reasoning ("agentic").

**direct** — straightforward fact lookup, definition, or simple comparison.
  The answer is likely in a single passage.  Examples: "What is the JWT expiry
  time?", "List the supported databases", "Where is the rate limit configured?"

**agentic** — needs multi-step reasoning: document discovery, cross-document
  synthesis, summarization, or subjective judgement.  Examples: "Compare the
  security approaches of system A and system B", "Summarise all documents in
  the knowledge base", "What topics are covered in my documents?", "Analyse
  the trade-offs between these architecture proposals"

  IMPORTANT: questions that ask to "summarise", "give an overview of", or
  describe the *contents* of the knowledge base (rather than a specific fact)
  MUST be classified as agentic — they require listing documents first, then
  reading broadly, not a single targeted search.

## Step 3 — Generate lexical queries
Produce 1-3 focused short query phrases for exact keyword matching.  These are
NOT natural-language questions — they are dense keyword/entity phrases in the
SAME LANGUAGE as the question.

  EN: ["JWT token expiry configuration", "access token lifetime"]
  ZH: ["JWT令牌过期时间", "访问令牌生命周期"]
  Bad: ["What is the JWT token expiry time?"]

For Chinese queries, use meaningful character sequences (2-4 chars), not single
characters.  If the knowledge base may contain both Chinese and English documents,
consider generating queries in both languages.

Output ONLY a JSON object (no markdown, no explanation):

{
  "mode": "direct" | "agentic",
  "reason": "brief one-sentence explanation of the classification",
  "semantic_query": "decontextualized standalone question",
  "lexical_queries": ["phrase 1", "phrase 2"]
}"""


# ── Public API ────────────────────────────────────────────────────────────────


@observe(name="search.rewrite", as_type="chain", capture_input=False, capture_output=False)
def route_and_rewrite(
    llm: LLMProvider,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> RewriteResult:
    """Classify query complexity, decontextualize, and generate lexical queries.

    1 LLM call.  ``lexical_queries`` is always non-empty — the caller can
    use them directly without further validation.
    """
    messages: list[dict[str, str]] = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    history_text = ""
    if history:
        lines = [f"{m['role']}: {m['content'][:200]}" for m in history[-6:]]
        history_text = "\n".join(lines)

    prompt = _ROUTE_PROMPT
    if history_text:
        prompt += f"\n\n## Conversation history (for context)\n{history_text}"

    prompt += f"\n\n## Current question\n{question}"

    response = llm.generate(system_prompt="", messages=[{"role": "user", "content": prompt}])

    update_current_span(
        input={"question": question[:200], "history_len": len(history or [])},
        output={"response": response[:400]},
    )

    # Parse JSON response
    try:
        data = json.loads(response)
        mode_str = data.get("mode", "direct")
        reason = data.get("reason", "")
        semantic_query = data.get("semantic_query", question)
        lexical = data.get("lexical_queries", [question])
    except (json.JSONDecodeError, TypeError):
        logger.warning("failed to parse route_and_rewrite response, defaulting to direct")
        return RewriteResult(
            mode=SearchMode.DIRECT,
            reason="Failed to parse LLM response, defaulting to direct",
            semantic_query=question,
            lexical_queries=[question],
        )

    # Map mode string to enum
    mode = SearchMode.DIRECT if mode_str == "direct" else SearchMode.AGENTIC

    # Ensure lexical_queries is always non-empty
    if not isinstance(lexical, list) or not lexical:
        lexical = [semantic_query]

    # Write classification score
    create_score(
        name="mode_classification",
        value=1.0 if mode == SearchMode.AGENTIC else 0.0,
        comment=reason,
    )

    logger.debug(
        "route_and_rewrite complete",
        mode=mode.value,
        reason=reason[:120],
        semantic_query=semantic_query[:100],
        lexical_count=len(lexical),
    )

    return RewriteResult(
        mode=mode,
        reason=reason,
        semantic_query=semantic_query,
        lexical_queries=lexical,
    )
