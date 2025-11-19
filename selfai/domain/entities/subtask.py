"""Subtask entity representing an individual task within a plan."""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from selfai.domain.value_objects import AgentKey, ExecutionStatus


@dataclass
class Subtask:
    """Domain entity representing a subtask within an execution plan.

    A subtask is an atomic unit of work that can be executed independently
    or as part of a dependency chain.

    Attributes:
        id: Unique identifier within the plan (e.g., "S1", "S2").
        title: Human-readable task name.
        objective: Detailed description of what to accomplish.
        agent_key: Agent responsible for executing this task.
        engine: Preferred LLM backend ("anythingllm", "qnn", "cpu").
        parallel_group: Group number for parallelization (higher = later).
        depends_on: List of subtask IDs that must complete first.
        status: Current execution status.
        result_path: Optional path to saved execution result.
        notes: Optional additional context or instructions.

    Example:
        >>> from selfai.domain.value_objects import AgentKey, ExecutionStatus
        >>> task = Subtask(
        ...     id="S1",
        ...     title="Analyze requirements",
        ...     objective="Review user requirements and identify key features",
        ...     agent_key=AgentKey("analyst"),
        ...     engine="anythingllm",
        ...     parallel_group=1,
        ...     depends_on=[]
        ... )
        >>> print(task.status)
        pending
    """

    id: str
    title: str
    objective: str
    agent_key: AgentKey
    engine: str
    parallel_group: int
    depends_on: list[str] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result_path: Optional[Path] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate subtask attributes.

        Raises:
            ValueError: If validation fails.
        """
        if not self.id or not self.id.strip():
            raise ValueError("Subtask ID cannot be empty")

        if not self.title or not self.title.strip():
            raise ValueError("Subtask title cannot be empty")

        if not self.objective or not self.objective.strip():
            raise ValueError("Subtask objective cannot be empty")

        if self.parallel_group < 1:
            raise ValueError("Parallel group must be >= 1")

        valid_engines = {"anythingllm", "qnn", "cpu", "ollama"}
        if self.engine.lower() not in valid_engines:
            raise ValueError(
                f"Invalid engine '{self.engine}'. "
                f"Must be one of: {valid_engines}"
            )

    def can_execute(self, completed_task_ids: set[str]) -> bool:
        """Check if this subtask can be executed now.

        A subtask can execute if all its dependencies are completed.

        Args:
            completed_task_ids: Set of subtask IDs that are completed.

        Returns:
            True if all dependencies are satisfied, False otherwise.

        Example:
            >>> task = Subtask(
            ...     id="S2", title="Design", objective="Create design",
            ...     agent_key=AgentKey("designer"), engine="anythingllm",
            ...     parallel_group=2, depends_on=["S1"]
            ... )
            >>> task.can_execute({"S1"})
            True
            >>> task.can_execute(set())
            False
        """
        return all(dep_id in completed_task_ids for dep_id in self.depends_on)

    def mark_running(self) -> None:
        """Mark subtask as currently running.

        Raises:
            RuntimeError: If task is not in PENDING status.

        Example:
            >>> task = Subtask(
            ...     id="S1", title="Test", objective="Testing",
            ...     agent_key=AgentKey("test"), engine="cpu",
            ...     parallel_group=1
            ... )
            >>> task.mark_running()
            >>> print(task.status)
            running
        """
        if self.status != ExecutionStatus.PENDING:
            raise RuntimeError(
                f"Cannot mark task '{self.id}' as running: "
                f"current status is {self.status}"
            )
        self.status = ExecutionStatus.RUNNING

    def mark_completed(self, result_path: Path) -> None:
        """Mark subtask as successfully completed.

        Args:
            result_path: Path where execution result was saved.

        Raises:
            RuntimeError: If task is not in RUNNING status.

        Example:
            >>> from pathlib import Path
            >>> task = Subtask(
            ...     id="S1", title="Test", objective="Testing",
            ...     agent_key=AgentKey("test"), engine="cpu",
            ...     parallel_group=1, status=ExecutionStatus.RUNNING
            ... )
            >>> task.mark_completed(Path("/memory/results/S1.txt"))
            >>> print(task.status)
            completed
        """
        if self.status != ExecutionStatus.RUNNING:
            raise RuntimeError(
                f"Cannot mark task '{self.id}' as completed: "
                f"current status is {self.status}"
            )
        self.status = ExecutionStatus.COMPLETED
        self.result_path = result_path

    def mark_failed(self, error_message: Optional[str] = None) -> None:
        """Mark subtask as failed.

        Args:
            error_message: Optional error description.

        Raises:
            RuntimeError: If task is not in RUNNING status.

        Example:
            >>> task = Subtask(
            ...     id="S1", title="Test", objective="Testing",
            ...     agent_key=AgentKey("test"), engine="cpu",
            ...     parallel_group=1, status=ExecutionStatus.RUNNING
            ... )
            >>> task.mark_failed("Connection timeout")
            >>> print(task.status)
            failed
        """
        if self.status != ExecutionStatus.RUNNING:
            raise RuntimeError(
                f"Cannot mark task '{self.id}' as failed: "
                f"current status is {self.status}"
            )
        self.status = ExecutionStatus.FAILED
        if error_message:
            self.notes = (
                f"{self.notes}\nError: {error_message}"
                if self.notes
                else f"Error: {error_message}"
            )

    def to_dict(self) -> dict[str, object]:
        """Convert subtask to dictionary representation.

        Returns:
            Dictionary with all subtask attributes.

        Example:
            >>> task = Subtask(
            ...     id="S1", title="Test", objective="Testing",
            ...     agent_key=AgentKey("test"), engine="cpu",
            ...     parallel_group=1
            ... )
            >>> data = task.to_dict()
            >>> print(data["title"])
            Test
        """
        return {
            "id": self.id,
            "title": self.title,
            "objective": self.objective,
            "agent_key": str(self.agent_key),
            "engine": self.engine,
            "parallel_group": self.parallel_group,
            "depends_on": self.depends_on,
            "status": str(self.status),
            "result_path": str(self.result_path) if self.result_path else None,
            "notes": self.notes or "",
        }

    def __eq__(self, other: object) -> bool:
        """Compare subtasks by ID.

        Args:
            other: Object to compare with.

        Returns:
            True if other is a Subtask with the same ID.
        """
        if not isinstance(other, Subtask):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Generate hash based on subtask ID.

        Returns:
            Hash value for this subtask.
        """
        return hash(self.id)

    def __repr__(self) -> str:
        """Return developer-friendly representation.

        Returns:
            String showing subtask ID and title.
        """
        return f"Subtask(id='{self.id}', title='{self.title}', status={self.status})"
