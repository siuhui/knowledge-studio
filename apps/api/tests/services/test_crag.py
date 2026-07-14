"""Unit tests for CRAG (Corrective RAG) relevance evaluation and decision flow."""

from unittest.mock import MagicMock

import pytest

from app.schemas.retrieval.citation import Citation
from app.schemas.retrieval.response import RetrievalChunk, RetrievalQueryResponse
from app.services.retrieval.crag import (
    RelevanceGrade,
    _generate_supplement_query,
    crag_evaluate_and_act,
    evaluate_relevance,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_chunk(chunk_id: str, content: str, doc_title: str = "Test Doc", score: float = 0.8) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=chunk_id,
        content=content,
        score=score,
        document_title=doc_title,
        citation=Citation(
            document_id=chunk_id.split(":")[0],
            document_title=doc_title,
            chunk_index=0,
            content_snippet=content[:200],
        ),
    )


def _make_mock_llm(response: str) -> MagicMock:
    mock = MagicMock()
    mock.generate.return_value = response
    return mock


# ── evaluate_relevance tests ─────────────────────────────────────────────────


class TestEvaluateRelevance:
    def test_evaluate_relevance_relevant(self):
        """Relevant results should be graded as relevant."""
        chunks = [_make_chunk("doc-1:c0", "JWT tokens expire after 24 hours by default.")]
        llm = _make_mock_llm('{"grade": "relevant", "reason": "Answer found directly in results."}')

        grade, reason = evaluate_relevance(llm, "How long do JWT tokens last?", chunks)

        assert grade == RelevanceGrade.RELEVANT
        assert reason

    def test_evaluate_relevance_partial(self):
        """Partial results should be graded as partial."""
        chunks = [_make_chunk("doc-1:c0", "JWT is used for authentication.")]
        llm = _make_mock_llm('{"grade": "partial", "reason": "Results mention JWT but no expiry info."}')

        grade, reason = evaluate_relevance(llm, "How long do JWT tokens last?", chunks)

        assert grade == RelevanceGrade.PARTIAL
        assert reason

    def test_evaluate_relevance_irrelevant(self):
        """Irrelevant results should be graded as irrelevant."""
        chunks = [_make_chunk("doc-1:c0", "The system uses PostgreSQL for data storage.")]
        llm = _make_mock_llm('{"grade": "irrelevant", "reason": "No connection to JWT tokens."}')

        grade, reason = evaluate_relevance(llm, "How long do JWT tokens last?", chunks)

        assert grade == RelevanceGrade.IRRELEVANT
        assert reason

    def test_evaluate_relevance_empty_results(self):
        """Empty results should be graded as irrelevant."""
        llm = _make_mock_llm("irrelevant")  # Won't be called — early exit

        grade, reason = evaluate_relevance(llm, "Any question?", [])

        assert grade == RelevanceGrade.IRRELEVANT
        assert "No results found" in reason

    def test_evaluate_relevance_malformed_response(self):
        """Malformed LLM response should default to irrelevant."""
        chunks = [_make_chunk("doc-1:c0", "Some content.")]
        llm = _make_mock_llm("not valid json at all")

        grade, reason = evaluate_relevance(llm, "Question?", chunks)

        assert grade == RelevanceGrade.IRRELEVANT
        assert "Failed to parse" in reason


# ── _generate_supplement_query tests ─────────────────────────────────────────


class TestGenerateSupplementQuery:
    def test_generate_supplement_query(self):
        """Should generate a targeted supplementary query."""
        chunks = [_make_chunk("doc-1:c0", "JWT is a standard for token-based auth.")]
        llm = _make_mock_llm('{"query": "JWT token expiry configuration"}')

        query = _generate_supplement_query(llm, "How long do JWT tokens last?", chunks)

        assert query == "JWT token expiry configuration"

    def test_generate_supplement_query_malformed(self):
        """Malformed response should fall back to original question."""
        chunks = [_make_chunk("doc-1:c0", "Some content.")]
        llm = _make_mock_llm("garbage")

        query = _generate_supplement_query(llm, "original question?", chunks)

        assert query == "original question?"


# ── crag_evaluate_and_act tests ──────────────────────────────────────────────


class TestCragEvaluateAndAct:
    def test_crag_not_found_after_retry(self, db):
        """retry_count>=1 with empty results → not_found."""
        retrieval = RetrievalQueryResponse(query="test", results=[])

        result = crag_evaluate_and_act(
            db,
            query="test query",
            retrieval=retrieval,
            retry_count=1,
            llm=MagicMock(),
            kb_id="kb-1",
        )

        assert result.action == "not_found"
        assert result.message is not None

    def test_crag_irrelevant_then_correct_query(self, db):
        """First attempt irrelevant → correct query → re-search → evaluate again."""
        chunks = [_make_chunk("doc-1:c0", "Off-topic content about databases.")]

        # Two LLM calls: first for evaluate_relevance, second for correct_query
        llm = MagicMock()
        llm.generate.side_effect = [
            '{"grade": "irrelevant", "reason": "Off-topic results."}',
            '{"queries": ["JWT token expiry time"]}',
        ]

        retrieval = RetrievalQueryResponse(query="JWT token?", results=chunks)

        with pytest.MonkeyPatch.context() as mp:
            # Patch RetrivalService.search to return empty (simulating re-search)
            mp.setattr(
                "app.services.retrieval.service.RetrievalService.search",
                lambda *args, **kwargs: RetrievalQueryResponse(query="JWT token expiry time", results=[]),
            )

            result = crag_evaluate_and_act(
                db,
                query="How long do JWT tokens last?",
                retrieval=retrieval,
                retry_count=0,
                llm=llm,
                kb_id="kb-1",
            )

        # After correction → empty results + retry_count=1 → not_found
        assert result.action == "not_found"

    def test_crag_relevant_straight_through(self, db):
        """Relevant results should pass straight through without correction."""
        chunks = [_make_chunk("doc-1:c0", "JWT tokens expire after 24 hours.")]
        llm = _make_mock_llm('{"grade": "relevant", "reason": "Direct answer found."}')
        retrieval = RetrievalQueryResponse(query="test", results=chunks)

        result = crag_evaluate_and_act(
            db,
            query="How long do JWT tokens last?",
            retrieval=retrieval,
            retry_count=0,
            llm=llm,
            kb_id="kb-1",
        )

        assert result.action == "answer"
        assert len(result.chunks) == 1

    def test_crag_partial_supplements(self, db):
        """Partial results → generate supplement → merge chunks."""
        chunks = [_make_chunk("doc-1:c0", "JWT is used for auth.", "Doc A")]

        llm = MagicMock()
        llm.generate.side_effect = [
            '{"grade": "partial", "reason": "Missing expiry detail."}',
            '{"query": "token expiry configuration"}',
        ]

        retrieval = RetrievalQueryResponse(query="test", results=chunks)

        supplement_chunks = [
            _make_chunk("doc-2:c0", "Default expiry is 24 hours.", "Doc B"),
        ]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.retrieval.service.RetrievalService.search",
                lambda *args, **kwargs: RetrievalQueryResponse(
                    query="token expiry configuration", results=supplement_chunks
                ),
            )

            result = crag_evaluate_and_act(
                db,
                query="How long do JWT tokens last?",
                retrieval=retrieval,
                retry_count=0,
                llm=llm,
                kb_id="kb-1",
            )

        assert result.action == "answer"
        assert len(result.chunks) == 2  # original + supplement
