"""Integration tests for agent tools that execute against a real database.

The ReAct loop, config, artifact, and streaming logic are unit-tested in
``tests/unit/services/test_agent_runner.py`` with a mock DB.  These two tests
exercise the tool ``execute`` paths that actually query the Chunk/Document
tables, so they need a live session.
"""

from app.services.agent.tools import list_documents, read_document
from app.services.agent.types import ToolContext, ToolResult


class TestToolExecution:
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
