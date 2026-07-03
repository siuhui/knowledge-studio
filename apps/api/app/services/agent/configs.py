"""Pre-built AgentConfig instances.

Same AgentRunner + different Config = different agent behavior.
Both configs share the same tool set; only the system prompt and
stopping criteria differ.
"""

from app.services.agent.tools import list_documents, read_document, search_keywords
from app.services.agent.types import AgentConfig

# ── Search Agent ─────────────────────────────────────────────────────────────

SEARCH_AGENT_CONFIG = AgentConfig(
    tools=[search_keywords, read_document, list_documents],
    system_prompt="""\
You are a research assistant searching a knowledge base to answer questions.

IMPORTANT — Document IDs are UUIDs:
  Every document has a UUID like '550e8400-e29b-41d4-a716-446655440000'.
  You can only obtain valid UUIDs from list_documents() or search_keywords() results.
  Never pass a document title, filename, or any string that is not a UUID
  to read_document() or search_keywords()'s document_ids parameter.

Workflow:
1. Call list_documents() first to discover available documents and their UUIDs
2. Use search_keywords() to find relevant passages — note the UUIDs in results
3. Use read_document() with the exact UUID from step 1 or 2 to get full context
4. Cross-validate with additional searches from different angles
5. When you have enough information, give a final answer with citations

Stop when you can fully answer the question, or after searching from 2-3 different angles.
Do NOT stop after the first search — always verify with at least one cross-check.""",
    max_rounds=5,
    early_stop_patience=2,
)

# ── Gather Agent ─────────────────────────────────────────────────────────────

GATHER_AGENT_CONFIG = AgentConfig(
    tools=[search_keywords, read_document, list_documents],
    system_prompt="""\
You are a research assistant collecting materials for a report chapter.

Your goal is NOT to write the report — it's to gather the most relevant source material.

For each piece of information you find, note:
- Which document it comes from
- Why it's relevant to the chapter topic
- Whether it contradicts or supports other findings

When you have collected comprehensive material covering all aspects of the chapter topic,
output a structured summary of what you found.

The output should be a JSON object:
{
  "chapter_topic": "...",
  "subtopics": [
    {"title": "...", "key_findings": ["...", "..."], "source_doc_ids": ["..."]},
    ...
  ]
}""",
    max_rounds=8,
    early_stop_patience=3,
)
