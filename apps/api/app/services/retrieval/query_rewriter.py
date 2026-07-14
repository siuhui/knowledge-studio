"""CRAG utility: correct a failed query for a second retrieval attempt."""

from __future__ import annotations

import json

from app.core.telemetry import observe, update_current_span
from app.services.llm import LLMProvider


@observe(name="search.crag.correct_query", as_type="chain", capture_input=False, capture_output=False)
def correct_query(
    llm: LLMProvider,
    original_query: str,
    failed_results_summary: str,
) -> list[str]:
    """Analyse why the last search failed and generate corrected search queries.

    This is an internal CRAG utility, not a standalone component. It is called
    when ``evaluate_relevance`` returns ``irrelevant`` — one chance to
    correct course before admitting the KB does not contain the answer.

    Returns a list of corrected query strings (typically 1-2). The caller
    feeds the first one back into retrieval with ``retry_count=1``.
    """
    prompt = f"""\
The last search for this question returned irrelevant results.

Original question: {original_query}

What the last search found (irrelevant):
{failed_results_summary}

Analyse WHY the search missed — was the query too narrow? Wrong terminology?
Then generate 1-2 corrected search queries that target the right angle.

Output JSON:
{{"queries": ["corrected query 1", "corrected query 2"]}}"""

    response = llm.generate(system_prompt="", messages=[{"role": "user", "content": prompt}])

    update_current_span(
        input={"original_query": original_query[:200]},
        output={"response": response[:300]},
    )

    # Parse the JSON response to extract queries
    try:
        data = json.loads(response)
        queries: list[str] = data.get("queries", [original_query])
        return queries if queries else [original_query]
    except (json.JSONDecodeError, TypeError):
        return [original_query]
