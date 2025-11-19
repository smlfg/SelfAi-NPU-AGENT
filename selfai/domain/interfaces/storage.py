"""Storage repository interface for persistent data operations.

This module defines the protocol for all storage implementations,
enabling dependency inversion and decoupling from specific storage backends.
"""

from typing import Protocol, Optional
from pathlib import Path


class IStorageRepository(Protocol):
    """Protocol defining the interface for persistent storage operations.

    This protocol abstracts away the details of how conversations, plans,
    and state are stored, allowing different implementations (filesystem,
    database, cloud storage, etc.) to be swapped seamlessly.

    Methods:
        save_conversation: Store a conversation exchange.
        load_relevant_context: Retrieve relevant past conversations.
        save_plan: Persist a plan to storage.
        load_plan: Retrieve a plan by identifier.
        clear_category: Remove conversations from a category.
        list_categories: List all active memory categories.
    """

    def save_conversation(
        self,
        agent_key: str,
        user_prompt: str,
        llm_response: str,
        tags: Optional[list[str]] = None,
    ) -> Path:
        """Save a conversation exchange to persistent storage.

        Args:
            agent_key: Unique identifier for the agent (e.g., "code_helper").
            user_prompt: The user's input message.
            llm_response: The LLM's generated response.
            tags: Optional list of tags for categorization and retrieval.

        Returns:
            Path to the saved conversation file.

        Raises:
            OSError: If file write operation fails.
            ValueError: If agent_key is invalid or empty.

        Example:
            >>> repo = FileSystemRepository(base_dir=Path("memory"))
            >>> path = repo.save_conversation(
            ...     agent_key="code_helper",
            ...     user_prompt="How do I use async/await?",
            ...     llm_response="Async/await is used for...",
            ...     tags=["python", "async"]
            ... )
            >>> print(path)
            memory/code_helper/conv_20250119_120000.txt
        """
        ...

    def load_relevant_context(
        self,
        agent_key: str,
        current_prompt: str,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        """Load relevant past conversations for context.

        Retrieves the most relevant historical conversations based on
        similarity to the current prompt, enabling context-aware responses.

        Args:
            agent_key: Unique identifier for the agent.
            current_prompt: The current user input (for relevance matching).
            limit: Maximum number of past conversations to retrieve.

        Returns:
            List of conversation dictionaries in chronological order:
            [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]

        Raises:
            ValueError: If agent_key is invalid.

        Example:
            >>> repo = FileSystemRepository(base_dir=Path("memory"))
            >>> history = repo.load_relevant_context(
            ...     agent_key="code_helper",
            ...     current_prompt="How do I handle exceptions?",
            ...     limit=3
            ... )
            >>> print(len(history))
            6  # 3 conversations = 6 messages (user + assistant)
        """
        ...

    def save_plan(
        self,
        goal: str,
        plan_data: dict[str, object],
    ) -> Path:
        """Persist an execution plan to storage.

        Args:
            goal: The user's goal or objective for this plan.
            plan_data: Structured plan data (subtasks, merge strategy, etc.)
                Must be JSON-serializable.

        Returns:
            Path to the saved plan file.

        Raises:
            OSError: If file write operation fails.
            ValueError: If plan_data is not JSON-serializable.

        Example:
            >>> repo = FileSystemRepository(base_dir=Path("memory"))
            >>> plan = {
            ...     "subtasks": [{"id": "S1", "title": "Analyze"}],
            ...     "merge": {"strategy": "Combine results"}
            ... }
            >>> path = repo.save_plan(goal="Create web app", plan_data=plan)
            >>> print(path)
            memory/plans/plan_20250119_120000_create-web-app.json
        """
        ...

    def load_plan(self, plan_path: Path) -> dict[str, object]:
        """Retrieve a plan from storage.

        Args:
            plan_path: Path to the plan file.

        Returns:
            Deserialized plan data as a dictionary.

        Raises:
            FileNotFoundError: If the plan file doesn't exist.
            json.JSONDecodeError: If the plan file is corrupted.

        Example:
            >>> repo = FileSystemRepository(base_dir=Path("memory"))
            >>> plan_path = Path("memory/plans/plan_20250119_120000.json")
            >>> plan = repo.load_plan(plan_path)
            >>> print(plan["subtasks"][0]["title"])
            "Analyze requirements"
        """
        ...

    def clear_category(
        self,
        category: str,
        keep_last: Optional[int] = None,
    ) -> int:
        """Remove conversations from a memory category.

        Args:
            category: The memory category to clear (e.g., "code_helper").
            keep_last: If specified, keeps the N most recent conversations
                and deletes older ones. If None, deletes all.

        Returns:
            Number of conversations removed.

        Raises:
            ValueError: If category is invalid.

        Example:
            >>> repo = FileSystemRepository(base_dir=Path("memory"))
            >>> removed = repo.clear_category("code_helper", keep_last=5)
            >>> print(f"Removed {removed} old conversations")
            Removed 15 old conversations
        """
        ...

    def list_categories(self) -> list[str]:
        """List all active memory categories.

        Returns:
            List of category names that have stored conversations.

        Example:
            >>> repo = FileSystemRepository(base_dir=Path("memory"))
            >>> categories = repo.list_categories()
            >>> print(categories)
            ["code_helper", "project_manager", "analyst"]
        """
        ...
