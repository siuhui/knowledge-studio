"""Unit tests for Route & Rewrite — query classification and decontextualization."""

from unittest.mock import MagicMock

from app.services.retrieval.rewrite import RewriteResult, SearchMode, route_and_rewrite

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_llm(response: str) -> MagicMock:
    mock = MagicMock()
    mock.generate.return_value = response
    return mock


# ── route_and_rewrite tests ──────────────────────────────────────────────────


class TestRouteAndRewrite:
    def test_route_simple_query(self):
        """Simple fact lookup should route to direct mode with lexical queries."""
        llm = _make_mock_llm(
            '{"mode": "direct", "reason": "Simple fact lookup.", '
            '"semantic_query": "What is the JWT token expiry time?", '
            '"lexical_queries": ["JWT token expiry", "access token lifetime"]}'
        )

        result = route_and_rewrite(llm, "JWT 过期时间多久")

        assert result.mode == SearchMode.DIRECT
        assert len(result.lexical_queries) > 0
        assert result.semantic_query

    def test_route_complex_query(self):
        """Cross-document comparison should route to agentic mode."""
        llm = _make_mock_llm(
            '{"mode": "agentic", "reason": "Requires cross-document synthesis and comparison.", '
            '"semantic_query": "Compare the security approaches of system A and system B", '
            '"lexical_queries": ["system A security architecture", "system B authentication"]}'
        )

        result = route_and_rewrite(llm, "比较文档A和B的安全方案")

        assert result.mode == SearchMode.AGENTIC

    def test_decontextualize_pronoun(self):
        """Pronoun reference should be resolved to a standalone query."""
        llm = _make_mock_llm(
            '{"mode": "direct", "reason": "Fact lookup after decontextualization.", '
            '"semantic_query": "What is the authentication mechanism of the knowledge base system?", '
            '"lexical_queries": ["authentication mechanism", "auth system"]}'
        )

        history = [
            {"role": "user", "content": "Tell me about the knowledge base system."},
            {"role": "assistant", "content": "It is a RAG-based document Q&A platform."},
        ]

        result = route_and_rewrite(llm, "它的认证机制呢", history=history)

        assert result.mode == SearchMode.DIRECT
        assert "认证" in result.semantic_query or "auth" in result.semantic_query.lower()

    def test_lexical_queries_always_present(self):
        """Regardless of mode, lexical_queries should always be non-empty."""
        # Agentic mode
        llm = _make_mock_llm(
            '{"mode": "agentic", "reason": "Complex analysis needed.", '
            '"semantic_query": "Analyze trade-offs between architectures.", '
            '"lexical_queries": ["architecture comparison", "design trade-offs"]}'
        )

        result = route_and_rewrite(llm, "Compare architectures")
        assert len(result.lexical_queries) > 0

        # Direct mode
        llm2 = _make_mock_llm(
            '{"mode": "direct", "reason": "Simple lookup.", '
            '"semantic_query": "What is the default port?", '
            '"lexical_queries": ["default port configuration", "server port setting"]}'
        )

        result2 = route_and_rewrite(llm2, "Default port?")
        assert len(result2.lexical_queries) > 0

    def test_lexical_queries_empty_fallback(self):
        """Empty lexical_queries in LLM response → fallback to semantic_query."""
        llm = _make_mock_llm(
            '{"mode": "direct", "reason": "Simple lookup.", '
            '"semantic_query": "What is the database URL?", '
            '"lexical_queries": []}'
        )

        result = route_and_rewrite(llm, "Database URL?")

        assert len(result.lexical_queries) > 0
        assert result.lexical_queries[0] == result.semantic_query

    def test_malformed_response_defaults_to_direct(self):
        """Malformed LLM response should default to direct mode."""
        llm = _make_mock_llm("not valid json!!!")

        result = route_and_rewrite(llm, "Any question?")

        assert result.mode == SearchMode.DIRECT
        assert result.semantic_query == "Any question?"
        assert result.lexical_queries == ["Any question?"]

    def test_no_history_works(self):
        """route_and_rewrite should work without history."""
        llm = _make_mock_llm(
            '{"mode": "direct", "reason": "Simple definition.", '
            '"semantic_query": "What is RAG?", '
            '"lexical_queries": ["retrieval augmented generation", "RAG definition"]}'
        )

        result = route_and_rewrite(llm, "What is RAG?")

        assert result.mode == SearchMode.DIRECT
        assert len(result.lexical_queries) > 0


# ── RewriteResult tests ──────────────────────────────────────────────────────


class TestRewriteResult:
    def test_post_init_fills_empty_lexical(self):
        """__post_init__ should fill lexical_queries from semantic_query if empty."""
        r = RewriteResult(
            mode=SearchMode.DIRECT,
            reason="test",
            semantic_query="What is the answer?",
            lexical_queries=[],
        )
        assert r.lexical_queries == ["What is the answer?"]

    def test_post_init_preserves_existing_lexical(self):
        """__post_init__ should not overwrite existing lexical_queries."""
        r = RewriteResult(
            mode=SearchMode.AGENTIC,
            reason="test",
            semantic_query="Complex analysis",
            lexical_queries=["analysis method 1", "comparison method 2"],
        )
        assert r.lexical_queries == ["analysis method 1", "comparison method 2"]
