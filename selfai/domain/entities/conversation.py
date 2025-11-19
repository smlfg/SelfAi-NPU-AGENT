"""Conversation entity representing a user-AI interaction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from selfai.domain.value_objects import AgentKey


@dataclass
class Conversation:
    """Domain entity representing a conversation exchange.

    Attributes:
        agent_key: Agent that participated in this conversation.
        user_prompt: User's input message.
        llm_response: AI's generated response.
        timestamp: When this conversation occurred.
        tags: Optional tags for categorization.

    Example:
        >>> from selfai.domain.value_objects import AgentKey
        >>> from datetime import datetime
        >>> conv = Conversation(
        ...     agent_key=AgentKey("code_helper"),
        ...     user_prompt="How do I use async?",
        ...     llm_response="Async allows concurrent execution...",
        ...     timestamp=datetime.now(),
        ...     tags=["python", "async"]
        ... )
        >>> print(conv.agent_key)
        code_helper
    """

    agent_key: AgentKey
    user_prompt: str
    llm_response: str
    timestamp: datetime
    tags: Optional[list[str]] = None

    def __post_init__(self) -> None:
        """Validate conversation after initialization."""
        if not self.user_prompt.strip():
            raise ValueError("User prompt cannot be empty")
        if not self.llm_response.strip():
            raise ValueError("LLM response cannot be empty")

    def to_messages(self) -> list[dict[str, str]]:
        """Convert to message format for LLM context.

        Returns:
            List of message dictionaries in OpenAI format.

        Example:
            >>> conv = Conversation(
            ...     agent_key=AgentKey("test"),
            ...     user_prompt="Hello",
            ...     llm_response="Hi there!",
            ...     timestamp=datetime.now()
            ... )
            >>> messages = conv.to_messages()
            >>> print(messages[0]["role"])
            user
        """
        return [
            {"role": "user", "content": self.user_prompt},
            {"role": "assistant", "content": self.llm_response},
        ]
