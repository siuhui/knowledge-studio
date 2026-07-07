from collections.abc import Callable
from typing import Any, Protocol


class Workflow(Protocol):
    """Protocol for studio task workflows.

    Each concrete workflow (Report, PPT, etc.) implements this interface.
    The progress callback receives (0.0-1.0 fraction, human-readable status message).
    """

    def __init__(self, update_progress: Callable[[float, str], None]) -> None: ...

    def execute(self, db: Any, *, config: dict[str, object], kb_id: str) -> tuple[str, int]:
        """Run the full pipeline. Returns (output, chapter_count)."""
        ...
