"""Plan entity representing a complete execution plan."""

from dataclasses import dataclass, field
from typing import Optional

from selfai.domain.entities.subtask import Subtask
from selfai.domain.value_objects import PlanMetadata


@dataclass
class Plan:
    """Domain entity representing a complete execution plan.

    A plan contains a collection of subtasks and a merge strategy
    for combining their results.

    Attributes:
        metadata: Plan metadata (goal, planner info, timestamps).
        subtasks: List of subtasks to execute.
        merge_strategy: Optional strategy for combining results.
        merge_steps: Optional list of merge steps.

    Example:
        >>> from selfai.domain.value_objects import PlanMetadata, AgentKey
        >>> from selfai.domain.entities import Subtask
        >>> from datetime import datetime
        >>> metadata = PlanMetadata(
        ...     goal="Create web app",
        ...     planner_provider="ollama",
        ...     planner_model="gemma3:1b",
        ...     created_at=datetime.now()
        ... )
        >>> task = Subtask(
        ...     id="S1", title="Setup", objective="Initialize project",
        ...     agent_key=AgentKey("code_helper"), engine="cpu",
        ...     parallel_group=1
        ... )
        >>> plan = Plan(metadata=metadata, subtasks=[task])
        >>> print(len(plan.subtasks))
        1
    """

    metadata: PlanMetadata
    subtasks: list[Subtask] = field(default_factory=list)
    merge_strategy: Optional[str] = None
    merge_steps: Optional[list[dict[str, str]]] = None

    def __post_init__(self) -> None:
        """Validate plan after initialization."""
        if not self.subtasks:
            raise ValueError("Plan must contain at least one subtask")

    def get_subtask(self, subtask_id: str) -> Optional[Subtask]:
        """Retrieve a subtask by ID.

        Args:
            subtask_id: Subtask identifier.

        Returns:
            Subtask if found, None otherwise.
        """
        for task in self.subtasks:
            if task.id == subtask_id:
                return task
        return None

    def get_executable_subtasks(self, completed_ids: set[str]) -> list[Subtask]:
        """Get all subtasks that can execute now.

        Args:
            completed_ids: Set of completed subtask IDs.

        Returns:
            List of subtasks whose dependencies are satisfied.
        """
        return [
            task
            for task in self.subtasks
            if task.can_execute(completed_ids)
            and not task.status.is_terminal()
        ]

    def to_dict(self) -> dict[str, object]:
        """Convert plan to dictionary representation.

        Returns:
            Dictionary with all plan data.
        """
        return {
            "metadata": self.metadata.to_dict(),
            "subtasks": [task.to_dict() for task in self.subtasks],
            "merge": {
                "strategy": self.merge_strategy or "",
                "steps": self.merge_steps or [],
            },
        }
