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

Workflow:
1. Start with search_keywords() to find relevant documents
2. For promising snippets, use read_document() to get full context
3. Cross-validate with additional searches from different angles
4. When you have enough information, give a final answer with citations

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
