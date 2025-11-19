"""Execution status value object.

Represents the status of a subtask or plan execution.
"""

from enum import Enum, auto


class ExecutionStatus(Enum):
    """Enumeration of possible execution statuses.

    This enum represents the lifecycle states of a subtask or plan execution.

    Values:
        PENDING: Task has not started yet.
        RUNNING: Task is currently being executed.
        COMPLETED: Task finished successfully.
        FAILED: Task failed with an error.
        SKIPPED: Task was skipped due to dependencies or conditions.

    Example:
        >>> status = ExecutionStatus.PENDING
        >>> print(status.name)
        PENDING
        >>> status = ExecutionStatus.COMPLETED
        >>> if status.is_terminal():
        ...     print("Execution finished")
        Execution finished
    """

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()

    def is_terminal(self) -> bool:
        """Check if this status represents a terminal state.

        Terminal states are those from which no further transitions occur.

        Returns:
            True if status is COMPLETED, FAILED, or SKIPPED.

        Example:
            >>> ExecutionStatus.COMPLETED.is_terminal()
            True
            >>> ExecutionStatus.RUNNING.is_terminal()
            False
        """
        return self in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.SKIPPED,
        )

    def is_successful(self) -> bool:
        """Check if this status represents successful completion.

        Returns:
            True if status is COMPLETED.

        Example:
            >>> ExecutionStatus.COMPLETED.is_successful()
            True
            >>> ExecutionStatus.FAILED.is_successful()
            False
        """
        return self == ExecutionStatus.COMPLETED

    def __str__(self) -> str:
        """Return human-readable string representation.

        Returns:
            Lowercase status name.

        Example:
            >>> str(ExecutionStatus.RUNNING)
            'running'
        """
        return self.name.lower()
