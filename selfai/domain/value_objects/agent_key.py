"""Agent key value object.

Represents a unique, validated agent identifier.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentKey:
    """Immutable value object representing an agent's unique identifier.

    Agent keys must be valid Python identifiers (alphanumeric + underscore,
    no leading digits) to ensure consistent usage across the system.

    Attributes:
        value: The string identifier (e.g., "code_helper", "project_manager").

    Raises:
        ValueError: If the identifier is invalid.

    Example:
        >>> key = AgentKey("code_helper")
        >>> print(key.value)
        code_helper
        >>> AgentKey("123invalid")  # Raises ValueError
        ValueError: Agent key must be a valid identifier: 123invalid
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the agent key after initialization.

        Raises:
            ValueError: If value is empty, contains invalid characters,
                or starts with a digit.
        """
        if not self.value:
            raise ValueError("Agent key cannot be empty")

        if not self.value.replace("_", "").isalnum():
            raise ValueError(
                f"Agent key must contain only alphanumeric characters "
                f"and underscores: {self.value}"
            )

        if self.value[0].isdigit():
            raise ValueError(
                f"Agent key cannot start with a digit: {self.value}"
            )

    def __str__(self) -> str:
        """Return string representation.

        Returns:
            The agent key value.
        """
        return self.value

    def __repr__(self) -> str:
        """Return developer-friendly representation.

        Returns:
            String in format: AgentKey('code_helper')
        """
        return f"AgentKey('{self.value}')"
