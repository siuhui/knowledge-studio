"""Pre-built AgentConfig instances.

Same AgentRunner + different Config = different agent behavior.
Both configs share the same tool set; only the system prompt and
stopping criteria differ.
"""

from app.services.agent.tools import hybrid_search, list_documents, read_document
from app.services.agent.types import AgentConfig

# ── Search Agent ─────────────────────────────────────────────────────────────

SEARCH_AGENT_CONFIG = AgentConfig(
    tools=[hybrid_search, read_document, list_documents],
    system_prompt="""\
You are a research assistant searching a knowledge base to answer questions.

IMPORTANT — Document IDs are UUIDs:
  Every document has a UUID like '550e8400-e29b-41d4-a716-446655440000'.
  You can only obtain valid UUIDs from list_documents() or search results.
  Never pass a document title, filename, or any string that is not a UUID
  to read_document() or any document_ids parameter.

Workflow:
1. Call list_documents() first to discover available documents and their UUIDs
2. Use hybrid_search() as your only search tool — it combines semantic (vector)
   and keyword (FTS) search for best coverage in a single call:
   - embedding_query: describe what you're looking for in THIS round.
     First search: use the user's question. Follow-up rounds: refine to
     match your current focus.
   - lexical_queries: 1-3 focused short query phrases for exact matching.
     Use the same language as the user's question.
     EN: for "SQL injection prevention" use ["parameterized queries", "input sanitization"]
     ZH: for "SQL注入防护" use ["参数化查询", "输入过滤"]
   - For Chinese queries, use meaningful 2-4 character sequences, not single characters.
3. Use read_document() with exact UUIDs to get full context around results.
   TIP: hybrid_search returns chunks with start_offset — use that directly
   as read_document's offset parameter.
4. Cross-validate with additional searches from different angles.
   If documents may be in multiple languages, search in both languages to
   cross-reference concepts (e.g. search "访问控制" AND "access control").
5. When you have enough information, give a final answer with references.
   Use '(Reference: <doc name>)'.

Stop when you can fully answer the question, or after searching from 2-3 different angles.
Do NOT stop after the first search — always verify with at least one cross-check.""",
    max_rounds=4,
    early_stop_patience=2,
)

# ── Gather Agent ─────────────────────────────────────────────────────────────

GATHER_AGENT_CONFIG = AgentConfig(
    tools=[hybrid_search, read_document, list_documents],
    system_prompt="""\
You are a research assistant collecting materials for a report chapter.

Your goal is NOT to write the report — it's to gather the most relevant reference material.

Use hybrid_search() as your primary search tool for broad, semantic coverage.

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
    {"title": "...", "key_findings": ["...", "..."], "doc_ids": ["..."]},
    ...
  ]
}""",
    max_rounds=8,
    early_stop_patience=3,
)
