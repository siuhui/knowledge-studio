"""Unit tests for AgentRunner — ReAct loop, tools, and types."""

import json
from unittest.mock import MagicMock

import pytest

from app.services.agent.configs import GATHER_AGENT_CONFIG, SEARCH_AGENT_CONFIG
from app.services.agent.runner import AgentRunner
from app.services.agent.tools import hybrid_search, list_documents, read_document
from app.services.agent.types import (
    AgentConfig,
    AgentResult,
    Artifact,
    ToolContext,
    ToolResult,
)
from app.services.llm import ToolCallDecision, ToolSpec

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_llm(decisions: list[ToolCallDecision]):
    """Create a mock LLM provider that returns decisions in sequence."""
    mock = MagicMock()
    mock.generate_with_tools.side_effect = decisions
    return mock


def _make_tool_decision(
    tool_name: str,
    tool_args: dict | None = None,
    thought: str | None = "thinking",
) -> ToolCallDecision:
    return ToolCallDecision(
        is_final=False,
        thought=thought,
        tool_name=tool_name,
        tool_args=tool_args or {},
        content=None,
    )


def _make_final_decision(content: str = "Final answer.", thought: str | None = "done thinking") -> ToolCallDecision:
    return ToolCallDecision(
        is_final=True,
        thought=thought,
        tool_name=None,
        tool_args=None,
        content=content,
    )


# ── AgentConfig tests ────────────────────────────────────────────────────────


class TestAgentConfig:
    def test_duplicate_tool_names_raises(self):
        """Duplicate tool names should raise ValueError."""
        tool_a = MagicMock()
        tool_a.name = "search"
        tool_b = MagicMock()
        tool_b.name = "search"  # duplicate

        with pytest.raises(ValueError, match="Duplicate tool names"):
            AgentConfig(
                tools=[tool_a, tool_b],
                system_prompt="test",
            )

    def test_tool_registry_lookup(self):
        """get_tool should return the correct tool by name."""
        tool_a = MagicMock()
        tool_a.name = "search"
        tool_b = MagicMock()
        tool_b.name = "read"

        config = AgentConfig(tools=[tool_a, tool_b], system_prompt="test")
        assert config.get_tool("search") is tool_a
        assert config.get_tool("read") is tool_b


# ── Artifact tests ───────────────────────────────────────────────────────────


class TestArtifact:
    def test_valid_artifact(self):
        a = Artifact(data={"key": "value", "num": 42}, doc_id="doc-1")
        assert a.data == {"key": "value", "num": 42}
        assert a.doc_id == "doc-1"

    def test_to_json(self):
        a = Artifact(data={"x": 1})
        assert json.loads(a.to_json()) == {"x": 1}

    def test_non_serializable_data_raises(self):
        """Artifact must reject non-JSON-serializable data at construction."""
        with pytest.raises(ValueError, match="JSON-serializable"):
            Artifact(data={"fn": lambda: None})  # type: ignore[dict-item]


# ── Tool tests (with mock DB) ────────────────────────────────────────────────


class TestTools:
    def test_hybrid_search_structure(self):
        """Verify hybrid_search has correct protocol attributes."""
        assert hybrid_search.name == "hybrid_search"
        assert hybrid_search.parameters["type"] == "object"
        assert "properties" in hybrid_search.parameters
        assert "required" in hybrid_search.parameters
        assert "embedding_query" in hybrid_search.parameters["required"]
        assert callable(hybrid_search.execute)

    def test_read_document_structure(self):
        assert read_document.name == "read_document"
        assert "document_id" in read_document.parameters["properties"]
        assert callable(read_document.execute)

    def test_list_documents_structure(self):
        assert list_documents.name == "list_documents"
        assert callable(list_documents.execute)

    def test_list_documents_executes(self, db):
        """list_documents should return ToolResult with correct structure."""
        ctx = ToolContext(db=db, kb_id="kb-test")
        result = list_documents.execute(ctx)
        assert isinstance(result, ToolResult)
        assert isinstance(result.summary, str)
        assert "document_count" in result.metadata

    def test_read_document_not_found(self, db):
        """read_document should handle missing documents gracefully."""
        ctx = ToolContext(db=db, kb_id="kb-test")
        result = read_document.execute(ctx, document_id="nonexistent-id")
        assert result.artifact_count == 0
        assert "not found" in result.summary.lower()


# ── AgentRunner tests ────────────────────────────────────────────────────────


class TestAgentRunnerLoop:
    def test_final_answer_on_first_round(self, db):
        """LLM returns final answer immediately — single round, no tools."""
        llm = _make_mock_llm([_make_final_decision("The answer is 42.")])
        config = AgentConfig(tools=[], system_prompt="You are helpful.", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("What is the answer?", ToolContext(db=db, kb_id="kb-1"))

        assert isinstance(result, AgentResult)
        assert result.final_answer == "The answer is 42."
        assert result.total_tool_calls == 0
        assert len(result.steps) == 2  # thought + final

    def test_tool_call_then_final(self, db):
        """Agent calls a tool, gets result, then answers."""
        mock_tool = MagicMock()
        mock_tool.name = "lookup"
        mock_tool.description = "Look up info"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.return_value = ToolResult(
            summary="Found: Paris is the capital of France.",
            artifacts=[Artifact(data={"fact": "Paris"}, doc_id="doc-1")],
            artifact_count=1,
        )

        llm = _make_mock_llm(
            [
                _make_tool_decision("lookup", {"query": "capital of France"}),
                _make_final_decision("The capital of France is Paris."),
            ]
        )

        config = AgentConfig(tools=[mock_tool], system_prompt="You are helpful.", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("What is the capital of France?", ToolContext(db=db, kb_id="kb-1"))

        assert result.final_answer == "The capital of France is Paris."
        assert result.total_tool_calls == 1
        assert len(result.collected_artifacts) == 1
        assert result.collected_artifacts[0].data == {"fact": "Paris"}

    def test_multiple_tool_calls(self, db):
        """Agent calls multiple tools across rounds before answering."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search documents"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.side_effect = [
            ToolResult(
                summary="First search: found document A.",
                artifacts=[Artifact(data={"doc": "A"}, doc_id="a")],
                artifact_count=1,
            ),
            ToolResult(
                summary="Second search: found document B.",
                artifacts=[Artifact(data={"doc": "B"}, doc_id="b")],
                artifact_count=1,
            ),
        ]

        llm = _make_mock_llm(
            [
                _make_tool_decision("search", {"query": "first"}),
                _make_tool_decision("search", {"query": "second"}),
                _make_final_decision("Combined answer from A and B."),
            ]
        )

        config = AgentConfig(tools=[mock_tool], system_prompt="Search well.", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("Find info.", ToolContext(db=db, kb_id="kb-1"))

        assert result.total_tool_calls == 2
        assert len(result.collected_artifacts) == 2
        assert result.final_answer == "Combined answer from A and B."

    def test_early_stop(self, db):
        """Consecutive dry rounds should trigger early termination."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.return_value = ToolResult(
            summary="Nothing found.",
            artifacts=[],
            artifact_count=0,
        )

        # Return "search" decisions — after 2 dry rounds, should stop
        llm = _make_mock_llm(
            [
                _make_tool_decision("search", {"query": "q1"}),
                _make_tool_decision("search", {"query": "q2"}),
                _make_tool_decision("search", {"query": "q3"}),  # won't reach this
            ]
        )

        config = AgentConfig(
            tools=[mock_tool],
            system_prompt="Search.",
            max_rounds=10,
            early_stop_patience=2,
        )
        runner = AgentRunner(llm, config)

        result = runner.run("Find stuff.", ToolContext(db=db, kb_id="kb-1"))

        # Should stop after 2 dry rounds (early_stop_patience=2)
        assert result.total_tool_calls == 2
        assert result.final_answer is None  # No final answer emitted

    def test_early_stop_resets_on_info(self, db):
        """A round with results should reset the dry-round counter."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.side_effect = [
            ToolResult(
                summary="Found something.",
                artifacts=[Artifact(data={"x": 1}, doc_id="s1")],
                artifact_count=1,
            ),
            ToolResult(summary="Dry 1.", artifacts=[], artifact_count=0),
            ToolResult(summary="Dry 2.", artifacts=[], artifact_count=0),
        ]

        llm = _make_mock_llm(
            [
                _make_tool_decision("search", {"query": "q1"}),
                _make_tool_decision("search", {"query": "q2"}),
                _make_tool_decision("search", {"query": "q3"}),
            ]
        )

        config = AgentConfig(
            tools=[mock_tool],
            system_prompt="Search.",
            max_rounds=10,
            early_stop_patience=2,
        )
        runner = AgentRunner(llm, config)

        result = runner.run("Find.", ToolContext(db=db, kb_id="kb-1"))

        # Round 1 had results → counter reset. Rounds 2+3 dry → stop after 3.
        assert result.total_tool_calls == 3

    def test_max_rounds_limit(self, db):
        """Agent should stop when max_rounds is reached."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.return_value = ToolResult(
            summary="Found.",
            artifacts=[Artifact(data={"x": 1}, doc_id="s1")],
            artifact_count=1,
        )

        # Keep returning tool calls — should stop at max_rounds
        decisions = [_make_tool_decision("search", {"query": f"q{i}"}) for i in range(10)]
        llm = _make_mock_llm(decisions)

        config = AgentConfig(tools=[mock_tool], system_prompt="Search.", max_rounds=3, early_stop_patience=10)
        runner = AgentRunner(llm, config)

        result = runner.run("Search.", ToolContext(db=db, kb_id="kb-1"))

        assert result.total_tool_calls == 3  # capped at max_rounds

    def test_tool_execution_error(self, db):
        """Tool that raises should produce error ToolResult, not crash."""
        mock_tool = MagicMock()
        mock_tool.name = "broken"
        mock_tool.description = "Broken tool"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.side_effect = RuntimeError("Tool exploded")

        llm = _make_mock_llm(
            [
                _make_tool_decision("broken", {}),
                _make_final_decision("I handled the error."),
            ]
        )

        config = AgentConfig(tools=[mock_tool], system_prompt="test", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("Test.", ToolContext(db=db, kb_id="kb-1"))

        # Tool error should be caught, produce error ToolResult, and continue
        assert result.total_tool_calls == 1
        assert "failed" in result.steps[2].tool_result.summary.lower()  # type: ignore[union-attr]

    def test_llm_call_error(self, db):
        """LLM failure should emit error and stop."""
        mock = MagicMock()
        mock.generate_with_tools.side_effect = RuntimeError("API down")

        config = AgentConfig(tools=[], system_prompt="test", max_rounds=5)
        runner = AgentRunner(mock, config)

        result = runner.run("Test.", ToolContext(db=db, kb_id="kb-1"))

        # Should stop after the error
        assert result.final_answer is None
        assert len(result.steps) > 0  # At least the error step

    def test_no_tool_name_no_final_answer(self, db):
        """LLM returns neither final answer nor tool name → error."""
        decision = ToolCallDecision(
            is_final=False,
            thought="I'm confused.",
            tool_name=None,
            tool_args=None,
            content=None,
        )

        llm = _make_mock_llm([decision])
        config = AgentConfig(tools=[], system_prompt="test", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("Test.", ToolContext(db=db, kb_id="kb-1"))

        # Should emit error and stop
        error_steps = [s for s in result.steps if s.tool_result is None and not s.is_final]
        assert len(error_steps) > 0

    def test_collected_artifacts_aggregation(self, db):
        """All tool artifacts should be collected in AgentResult."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.side_effect = [
            ToolResult(
                summary="Found 2 docs.",
                artifacts=[
                    Artifact(data={"id": "a"}, doc_id="a"),
                    Artifact(data={"id": "b"}, doc_id="b"),
                ],
                artifact_count=2,
            ),
            ToolResult(
                summary="Found 1 doc.",
                artifacts=[Artifact(data={"id": "c"}, doc_id="c")],
                artifact_count=1,
            ),
        ]

        llm = _make_mock_llm(
            [
                _make_tool_decision("search", {"query": "q1"}),
                _make_tool_decision("search", {"query": "q2"}),
                _make_final_decision("Done."),
            ]
        )

        config = AgentConfig(tools=[mock_tool], system_prompt="test", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("Test.", ToolContext(db=db, kb_id="kb-1"))

        assert len(result.collected_artifacts) == 3
        assert {a.data["id"] for a in result.collected_artifacts} == {"a", "b", "c"}

    def test_step_trace_completeness(self, db):
        """Each step should have the correct is_final flag and new_info_count."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.return_value = ToolResult(
            summary="Found 1.",
            artifacts=[Artifact(data={"x": 1}, doc_id="s1")],
            artifact_count=1,
        )

        llm = _make_mock_llm(
            [
                _make_tool_decision("search", {"query": "q"}),
                _make_final_decision("Answer."),
            ]
        )

        config = AgentConfig(tools=[mock_tool], system_prompt="test", max_rounds=5)
        runner = AgentRunner(llm, config)

        result = runner.run("Test.", ToolContext(db=db, kb_id="kb-1"))

        # Steps: thought(not final) → tool_call → tool_result(not final) → thought(final) → final
        non_final = [s for s in result.steps if not s.is_final]
        final_steps = [s for s in result.steps if s.is_final]
        assert len(final_steps) >= 1  # At least the final event
        assert len(non_final) >= 1  # At least the thought event

        # The tool_result step should have new_info_count = 1
        tool_result_steps = [s for s in result.steps if s.tool_result and s.tool_name]
        assert tool_result_steps[0].new_info_count == 1


# ── Pre-built config tests ───────────────────────────────────────────────────


class TestPrebuiltConfigs:
    def test_search_agent_config(self):
        config = SEARCH_AGENT_CONFIG
        assert config.max_rounds == 4
        assert config.early_stop_patience == 2
        assert len(config.tools) == 3
        tool_names = {t.name for t in config.tools}
        assert tool_names == {"hybrid_search", "read_document", "list_documents"}

    def test_gather_agent_config(self):
        config = GATHER_AGENT_CONFIG
        assert config.max_rounds == 8
        assert config.early_stop_patience == 3
        assert len(config.tools) == 3
        tool_names = {t.name for t in config.tools}
        assert tool_names == {"hybrid_search", "read_document", "list_documents"}


# ── ToolSpec conversion test ─────────────────────────────────────────────────


class TestToolSpecConversion:
    def test_tools_to_specs(self):
        from app.services.agent.runner import _tools_to_specs

        mock_tool = MagicMock()
        mock_tool.name = "my_tool"
        mock_tool.description = "Does things."
        mock_tool.parameters = {"type": "object", "properties": {"q": {"type": "string"}}}

        specs = _tools_to_specs([mock_tool])
        assert len(specs) == 1
        assert isinstance(specs[0], ToolSpec)
        assert specs[0].name == "my_tool"
        assert specs[0].description == "Does things."
        assert specs[0].parameters["properties"]["q"]["type"] == "string"


# ── SSE streaming tests ──────────────────────────────────────────────────────


class TestAgentRunnerStream:
    @pytest.mark.anyio
    async def test_stream_yields_sse_json(self, db):
        """run_stream should yield valid SSE JSON event strings."""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search"
        mock_tool.parameters = {"type": "object", "properties": {}}
        mock_tool.execute.return_value = ToolResult(
            summary="Found 1.",
            artifacts=[Artifact(data={"x": 1}, doc_id="s1")],
            artifact_count=1,
        )

        llm = _make_mock_llm(
            [
                _make_tool_decision("search", {"query": "test"}),
                _make_final_decision("Final!"),
            ]
        )

        config = AgentConfig(tools=[mock_tool], system_prompt="test", max_rounds=5)
        runner = AgentRunner(llm, config)

        events: list[dict] = []
        async for event_json in runner.run_stream("Test.", ToolContext(db=db, kb_id="kb-1")):
            events.append(json.loads(event_json))

        # Should have: thought → tool_call → tool_result → thought → final
        event_types = [e["type"] for e in events]
        assert "thought" in event_types
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "final" in event_types

        # Verify event payloads
        final_event = events[-1]
        assert final_event["type"] == "final"
        assert final_event["answer"] == "Final!"

        tool_call_event = [e for e in events if e["type"] == "tool_call"][0]
        assert tool_call_event["tool"] == "search"
        assert tool_call_event["args"] == {"query": "test"}

    @pytest.mark.anyio
    async def test_stream_error_event(self, db):
        """LLM error should yield an error SSE event."""
        mock = MagicMock()
        mock.generate_with_tools.side_effect = RuntimeError("Boom!")

        config = AgentConfig(tools=[], system_prompt="test", max_rounds=5)
        runner = AgentRunner(mock, config)

        events: list[dict] = []
        async for event_json in runner.run_stream("Test.", ToolContext(db=db, kb_id="kb-1")):
            events.append(json.loads(event_json))

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) >= 1
        assert "Boom" in error_events[0]["message"] or "error" in error_events[0]["message"].lower()
