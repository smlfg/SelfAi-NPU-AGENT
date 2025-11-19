"""Plan metadata value object.

Contains immutable metadata about a plan's creation and execution.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class PlanMetadata:
    """Immutable metadata about a plan.

    Attributes:
        goal: The original user goal for this plan.
        planner_provider: Name of the planner that created this plan.
        planner_model: Model used for planning (e.g., "gemma3:1b").
        created_at: Timestamp when plan was created.
        merge_agent: Optional agent key for merge phase.
        merge_provider: Optional merge service provider name.

    Example:
        >>> from datetime import datetime
        >>> metadata = PlanMetadata(
        ...     goal="Create a web scraper",
        ...     planner_provider="local-ollama",
        ...     planner_model="gemma3:1b",
        ...     created_at=datetime.now()
        ... )
        >>> print(metadata.goal)
        Create a web scraper
    """

    goal: str
    planner_provider: str
    planner_model: str
    created_at: datetime
    merge_agent: Optional[str] = None
    merge_provider: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate metadata after initialization.

        Raises:
            ValueError: If goal is empty or whitespace-only.
        """
        if not self.goal or not self.goal.strip():
            raise ValueError("Plan goal cannot be empty")

        if not self.planner_provider:
            raise ValueError("Planner provider cannot be empty")

        if not self.planner_model:
            raise ValueError("Planner model cannot be empty")

    def to_dict(self) -> dict[str, str]:
        """Convert metadata to dictionary for serialization.

        Returns:
            Dictionary representation with ISO-formatted timestamp.

        Example:
            >>> metadata = PlanMetadata(
            ...     goal="Test",
            ...     planner_provider="ollama",
            ...     planner_model="gemma",
            ...     created_at=datetime.now()
            ... )
            >>> data = metadata.to_dict()
            >>> print(data["goal"])
            Test
        """
        return {
            "goal": self.goal,
            "planner_provider": self.planner_provider,
            "planner_model": self.planner_model,
            "created_at": self.created_at.isoformat(),
            "merge_agent": self.merge_agent or "",
            "merge_provider": self.merge_provider or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "PlanMetadata":
        """Create metadata from dictionary.

        Args:
            data: Dictionary with metadata fields.

        Returns:
            PlanMetadata instance.

        Raises:
            ValueError: If required fields are missing.
            KeyError: If required keys are not in dictionary.

        Example:
            >>> data = {
            ...     "goal": "Test goal",
            ...     "planner_provider": "ollama",
            ...     "planner_model": "gemma",
            ...     "created_at": "2025-01-19T12:00:00"
            ... }
            >>> metadata = PlanMetadata.from_dict(data)
            >>> print(metadata.goal)
            Test goal
        """
        return cls(
            goal=data["goal"],
            planner_provider=data["planner_provider"],
            planner_model=data["planner_model"],
            created_at=datetime.fromisoformat(data["created_at"]),
            merge_agent=data.get("merge_agent") or None,
            merge_provider=data.get("merge_provider") or None,
        )
