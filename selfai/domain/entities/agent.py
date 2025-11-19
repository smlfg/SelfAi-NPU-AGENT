"""Agent entity representing an AI assistant with specific capabilities."""

from dataclasses import dataclass
from typing import Optional

from selfai.domain.value_objects import AgentKey


@dataclass
class Agent:
    """Domain entity representing an AI agent.

    An agent encapsulates a specific personality, expertise, and memory
    configuration for handling particular types of tasks.

    Attributes:
        key: Unique identifier for this agent.
        display_name: Human-readable name shown in UI.
        system_prompt: Instructions defining the agent's behavior.
        memory_categories: List of memory categories for context retrieval.
        workspace_slug: Optional workspace identifier for AnythingLLM.
        description: Optional brief description of agent's purpose.

    Example:
        >>> from selfai.domain.value_objects import AgentKey
        >>> agent = Agent(
        ...     key=AgentKey("code_helper"),
        ...     display_name="Code Helper",
        ...     system_prompt="You are an expert Python developer.",
        ...     memory_categories=["coding", "python"],
        ...     description="Assists with code writing and debugging"
        ... )
        >>> print(agent.display_name)
        Code Helper
    """

    key: AgentKey
    display_name: str
    system_prompt: str
    memory_categories: list[str]
    workspace_slug: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate agent attributes after initialization.

        Raises:
            ValueError: If required fields are empty or invalid.
        """
        if not self.display_name or not self.display_name.strip():
            raise ValueError("Agent display_name cannot be empty")

        if not self.system_prompt or not self.system_prompt.strip():
            raise ValueError("Agent system_prompt cannot be empty")

        if not self.memory_categories:
            raise ValueError("Agent must have at least one memory category")

        # Validate memory categories are non-empty strings
        for category in self.memory_categories:
            if not category or not category.strip():
                raise ValueError("Memory categories cannot contain empty strings")

    def has_category(self, category: str) -> bool:
        """Check if agent uses a specific memory category.

        Args:
            category: Memory category name to check.

        Returns:
            True if agent has this category, False otherwise.

        Example:
            >>> agent = Agent(
            ...     key=AgentKey("code_helper"),
            ...     display_name="Helper",
            ...     system_prompt="Help",
            ...     memory_categories=["coding", "python"]
            ... )
            >>> agent.has_category("python")
            True
            >>> agent.has_category("java")
            False
        """
        return category in self.memory_categories

    def to_dict(self) -> dict[str, object]:
        """Convert agent to dictionary representation.

        Returns:
            Dictionary with all agent attributes.

        Example:
            >>> agent = Agent(
            ...     key=AgentKey("test"),
            ...     display_name="Test",
            ...     system_prompt="Testing",
            ...     memory_categories=["test"]
            ... )
            >>> data = agent.to_dict()
            >>> print(data["display_name"])
            Test
        """
        return {
            "key": str(self.key),
            "display_name": self.display_name,
            "system_prompt": self.system_prompt,
            "memory_categories": self.memory_categories,
            "workspace_slug": self.workspace_slug or "",
            "description": self.description or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Agent":
        """Create agent from dictionary representation.

        Args:
            data: Dictionary with agent attributes.

        Returns:
            Agent instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If validation fails.

        Example:
            >>> data = {
            ...     "key": "code_helper",
            ...     "display_name": "Code Helper",
            ...     "system_prompt": "You help with code.",
            ...     "memory_categories": ["coding"]
            ... }
            >>> agent = Agent.from_dict(data)
            >>> print(agent.display_name)
            Code Helper
        """
        return cls(
            key=AgentKey(str(data["key"])),
            display_name=str(data["display_name"]),
            system_prompt=str(data["system_prompt"]),
            memory_categories=[str(c) for c in data["memory_categories"]],  # type: ignore
            workspace_slug=str(data.get("workspace_slug") or ""),
            description=str(data.get("description") or ""),
        )

    def __eq__(self, other: object) -> bool:
        """Compare agents by identity (key).

        Agents are entities, so equality is based on identity, not attributes.

        Args:
            other: Object to compare with.

        Returns:
            True if other is an Agent with the same key.

        Example:
            >>> agent1 = Agent(
            ...     key=AgentKey("helper"),
            ...     display_name="Helper 1",
            ...     system_prompt="Help",
            ...     memory_categories=["test"]
            ... )
            >>> agent2 = Agent(
            ...     key=AgentKey("helper"),
            ...     display_name="Helper 2",  # Different name!
            ...     system_prompt="Help",
            ...     memory_categories=["test"]
            ... )
            >>> agent1 == agent2  # Same identity (key)
            True
        """
        if not isinstance(other, Agent):
            return False
        return self.key == other.key

    def __hash__(self) -> int:
        """Generate hash based on agent key.

        Returns:
            Hash value for this agent.
        """
        return hash(self.key)

    def __repr__(self) -> str:
        """Return developer-friendly representation.

        Returns:
            String showing agent key and display name.

        Example:
            >>> agent = Agent(
            ...     key=AgentKey("helper"),
            ...     display_name="Code Helper",
            ...     system_prompt="Help",
            ...     memory_categories=["test"]
            ... )
            >>> repr(agent)
            "Agent(key='helper', display_name='Code Helper')"
        """
        return f"Agent(key='{self.key}', display_name='{self.display_name}')"
