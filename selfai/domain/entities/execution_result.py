"""Execution result entity for subtask execution outcomes."""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class ExecutionResult:
    """Domain entity representing the result of a subtask execution.

    Attributes:
        subtask_id: ID of the executed subtask.
        output: Generated output from the LLM.
        result_path: Path where result was saved.
        backend_used: Which LLM backend generated this result.
        error: Optional error message if execution failed.

    Example:
        >>> from pathlib import Path
        >>> result = ExecutionResult(
        ...     subtask_id="S1",
        ...     output="Task completed successfully",
        ...     result_path=Path("/memory/results/S1.txt"),
        ...     backend_used="anythingllm"
        ... )
        >>> print(result.is_success())
        True
    """

    subtask_id: str
    output: str
    result_path: Path
    backend_used: str
    error: Optional[str] = None

    def is_success(self) -> bool:
        """Check if execution was successful.

        Returns:
            True if no error occurred, False otherwise.
        """
        return self.error is None

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with result data.
        """
        return {
            "subtask_id": self.subtask_id,
            "output": self.output,
            "result_path": str(self.result_path),
            "backend_used": self.backend_used,
            "error": self.error or "",
        }
