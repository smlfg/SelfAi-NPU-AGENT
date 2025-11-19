"""Memory Manager - JSON-based structured memory storage for conversations.

This module implements a clean, queryable memory system that stores conversations
as structured JSON documents instead of fragile text files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class MemoryMetadata:
    """Metadata for a memory entry.

    Attributes:
        agent_key: Unique identifier for the agent
        agent_name: Display name of the agent
        workspace_slug: Workspace identifier for backend routing
        timestamp: ISO format timestamp of when memory was created
        tags: List of tags for categorization and search
        category: Primary category for the memory
        session_id: Optional session identifier for grouping related conversations
    """

    agent_key: str
    agent_name: str
    workspace_slug: str
    timestamp: str
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    session_id: str | None = None


@dataclass
class MemoryEntry:
    """A single conversation memory entry.

    Attributes:
        id: Unique identifier for this memory entry
        metadata: Metadata about the agent and context
        system_prompt: The system prompt used for this conversation
        user_message: The user's input
        assistant_message: The assistant's response
        created_at: ISO timestamp when entry was created
        relevance_score: Optional score for relevance ranking (0.0-1.0)
    """

    id: str
    metadata: MemoryMetadata
    system_prompt: str
    user_message: str
    assistant_message: str
    created_at: str
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert memory entry to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the memory entry
        """
        return {
            "id": self.id,
            "metadata": asdict(self.metadata),
            "system_prompt": self.system_prompt,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "created_at": self.created_at,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Create memory entry from dictionary.

        Args:
            data: Dictionary containing memory entry data

        Returns:
            MemoryEntry instance

        Raises:
            KeyError: If required fields are missing
            ValueError: If data format is invalid
        """
        metadata_dict = data["metadata"]
        metadata = MemoryMetadata(
            agent_key=metadata_dict["agent_key"],
            agent_name=metadata_dict["agent_name"],
            workspace_slug=metadata_dict["workspace_slug"],
            timestamp=metadata_dict["timestamp"],
            tags=metadata_dict.get("tags", []),
            category=metadata_dict.get("category", "general"),
            session_id=metadata_dict.get("session_id"),
        )

        return cls(
            id=data["id"],
            metadata=metadata,
            system_prompt=data["system_prompt"],
            user_message=data["user_message"],
            assistant_message=data["assistant_message"],
            created_at=data["created_at"],
            relevance_score=data.get("relevance_score", 0.0),
        )


class MemoryManager:
    """Manages structured conversation memory with JSON storage.

    This class provides a clean interface for storing and retrieving conversation
    memories using JSON files with an index for efficient querying.

    Storage Structure:
        memory_dir/
        ├── index.json          # Master index of all memories
        ├── entries/
        │   ├── {uuid}.json     # Individual memory entries
        │   └── ...
        └── plans/
            ├── {timestamp}_{goal}.json  # Execution plans
            └── ...

    Attributes:
        memory_dir: Root directory for memory storage
        entries_dir: Directory containing individual memory entries
        plan_dir: Directory containing execution plans
        index_path: Path to the master index file
    """

    def __init__(self, memory_dir: Path):
        """Initialize the memory manager.

        Args:
            memory_dir: Root directory for memory storage
        """
        self.memory_dir = Path(memory_dir)
        self.entries_dir = self.memory_dir / "entries"
        self.plan_dir = self.memory_dir / "plans"
        self.index_path = self.memory_dir / "index.json"

        # Create directory structure
        self.memory_dir.mkdir(exist_ok=True)
        self.entries_dir.mkdir(exist_ok=True)
        self.plan_dir.mkdir(exist_ok=True)

        # Initialize or load index
        self._index: dict[str, dict[str, Any]] = self._load_index()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load the memory index from disk.

        Returns:
            Dictionary mapping memory IDs to their metadata
        """
        if not self.index_path.exists():
            return {}

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[MemoryManager] Warning: Could not load index: {exc}")
            return {}

    def _save_index(self) -> None:
        """Save the memory index to disk."""
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[MemoryManager] Error: Could not save index: {exc}")

    def save_conversation(
        self,
        agent_key: str,
        agent_name: str,
        workspace_slug: str,
        system_prompt: str,
        user_message: str,
        assistant_message: str,
        category: str = "general",
        tags: list[str] | None = None,
        session_id: str | None = None,
    ) -> str | None:
        """Save a conversation to memory.

        Args:
            agent_key: Unique identifier for the agent
            agent_name: Display name of the agent
            workspace_slug: Workspace identifier
            system_prompt: System prompt used for this conversation
            user_message: User's input
            assistant_message: Assistant's response
            category: Primary category for organization (default: "general")
            tags: Optional list of tags for categorization
            session_id: Optional session identifier for grouping

        Returns:
            The unique ID of the saved memory entry, or None if save failed

        Examples:
            >>> manager = MemoryManager(Path("./memory"))
            >>> memory_id = manager.save_conversation(
            ...     agent_key="code_helper",
            ...     agent_name="Code Helper",
            ...     workspace_slug="main",
            ...     system_prompt="You are a helpful coding assistant.",
            ...     user_message="How do I sort a list in Python?",
            ...     assistant_message="You can use the sorted() function...",
            ...     category="coding",
            ...     tags=["python", "sorting"]
            ... )
        """
        try:
            # Generate unique ID and timestamp
            memory_id = uuid4().hex
            timestamp = datetime.now().isoformat()

            # Extract tags from content if not provided
            if tags is None:
                tags = self._extract_tags(user_message, assistant_message, category, agent_key)

            # Create memory entry
            metadata = MemoryMetadata(
                agent_key=agent_key,
                agent_name=agent_name,
                workspace_slug=workspace_slug,
                timestamp=timestamp,
                tags=tags,
                category=category,
                session_id=session_id,
            )

            entry = MemoryEntry(
                id=memory_id,
                metadata=metadata,
                system_prompt=system_prompt,
                user_message=user_message,
                assistant_message=assistant_message,
                created_at=timestamp,
            )

            # Save entry to file
            entry_path = self.entries_dir / f"{memory_id}.json"
            with open(entry_path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)

            # Update index
            self._index[memory_id] = {
                "agent_key": agent_key,
                "category": category,
                "tags": tags,
                "timestamp": timestamp,
                "path": str(entry_path.relative_to(self.memory_dir)),
            }
            self._save_index()

            return memory_id

        except Exception as exc:
            print(f"[MemoryManager] Error saving conversation: {exc}")
            return None

    def _extract_tags(
        self,
        user_message: str,
        assistant_message: str,
        category: str,
        agent_key: str,
    ) -> list[str]:
        """Extract tags from conversation content.

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            category: Category name
            agent_key: Agent identifier

        Returns:
            List of extracted tags
        """
        combined_text = f"{user_message} {assistant_message}"
        tags = {category, agent_key}

        # Extract common programming languages
        languages = ["python", "javascript", "typescript", "java", "rust", "go", "c++", "c#"]
        for lang in languages:
            if lang.lower() in combined_text.lower():
                tags.add(lang)

        # Extract common topics
        topics = {
            "debug": ["debug", "error", "fix", "bug"],
            "refactor": ["refactor", "clean", "improve"],
            "documentation": ["document", "explain", "describe"],
            "testing": ["test", "unit test", "integration"],
            "optimization": ["optimize", "performance", "speed"],
        }

        for tag, keywords in topics.items():
            if any(kw in combined_text.lower() for kw in keywords):
                tags.add(tag)

        return sorted(list(tags))

    def get_memory(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a specific memory by ID.

        Args:
            memory_id: Unique identifier of the memory

        Returns:
            MemoryEntry if found, None otherwise
        """
        if memory_id not in self._index:
            return None

        entry_path = self.entries_dir / f"{memory_id}.json"
        if not entry_path.exists():
            return None

        try:
            with open(entry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return MemoryEntry.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"[MemoryManager] Error loading memory {memory_id}: {exc}")
            return None

    def query_memories(
        self,
        agent_key: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        """Query memories with filters.

        Args:
            agent_key: Filter by agent (optional)
            category: Filter by category (optional)
            tags: Filter by tags - returns memories with ANY of these tags (optional)
            limit: Maximum number of results to return (default: 10)
            offset: Number of results to skip (default: 0)

        Returns:
            List of matching memory entries, sorted by timestamp (newest first)

        Examples:
            >>> # Get last 5 coding-related memories
            >>> memories = manager.query_memories(
            ...     category="coding",
            ...     tags=["python"],
            ...     limit=5
            ... )
        """
        matching_ids: list[str] = []

        for memory_id, index_entry in self._index.items():
            # Filter by agent
            if agent_key and index_entry.get("agent_key") != agent_key:
                continue

            # Filter by category
            if category and index_entry.get("category") != category:
                continue

            # Filter by tags (ANY match)
            if tags:
                entry_tags = set(index_entry.get("tags", []))
                if not any(tag in entry_tags for tag in tags):
                    continue

            matching_ids.append(memory_id)

        # Sort by timestamp (newest first)
        matching_ids.sort(
            key=lambda mid: self._index[mid].get("timestamp", ""),
            reverse=True,
        )

        # Apply pagination
        paginated_ids = matching_ids[offset : offset + limit]

        # Load full entries
        memories: list[MemoryEntry] = []
        for memory_id in paginated_ids:
            entry = self.get_memory(memory_id)
            if entry:
                memories.append(entry)

        return memories

    def get_context_messages(
        self,
        agent_key: str,
        category: str | None = None,
        limit: int = 3,
    ) -> list[dict[str, str]]:
        """Get conversation context in chat format for LLM.

        Args:
            agent_key: Agent identifier
            category: Optional category filter
            limit: Maximum number of conversations to include

        Returns:
            List of message dicts with 'role' and 'content' keys,
            suitable for passing to LLM chat APIs

        Examples:
            >>> messages = manager.get_context_messages(
            ...     agent_key="code_helper",
            ...     category="coding",
            ...     limit=3
            ... )
            >>> # messages = [
            >>> #     {"role": "user", "content": "..."},
            >>> #     {"role": "assistant", "content": "..."},
            >>> #     ...
            >>> # ]
        """
        memories = self.query_memories(
            agent_key=agent_key,
            category=category,
            limit=limit,
        )

        # Build message list (oldest first for context)
        messages: list[dict[str, str]] = []
        for memory in reversed(memories):  # Reverse to get oldest first
            messages.append({"role": "user", "content": memory.user_message})
            messages.append({"role": "assistant", "content": memory.assistant_message})

        return messages

    def save_plan(self, goal: str, plan_data: dict[str, Any]) -> Path:
        """Save an execution plan as JSON.

        Args:
            goal: Description of the plan's goal
            plan_data: Plan data dictionary

        Returns:
            Path to the saved plan file

        Raises:
            OSError: If file cannot be written
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        goal_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", goal.strip()).strip("-") or "plan"
        filename = f"{timestamp}_{goal_slug}.json"
        filepath = self.plan_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[MemoryManager] Error: Could not save plan: {exc}")
            raise

        return filepath

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dictionary with statistics about stored memories

        Examples:
            >>> stats = manager.get_statistics()
            >>> print(f"Total memories: {stats['total_entries']}")
            >>> print(f"Categories: {stats['categories']}")
        """
        categories: dict[str, int] = {}
        agents: dict[str, int] = {}
        tag_counts: dict[str, int] = {}

        for index_entry in self._index.values():
            category = index_entry.get("category", "unknown")
            categories[category] = categories.get(category, 0) + 1

            agent = index_entry.get("agent_key", "unknown")
            agents[agent] = agents.get(agent, 0) + 1

            for tag in index_entry.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "total_entries": len(self._index),
            "categories": categories,
            "agents": agents,
            "top_tags": dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "storage_path": str(self.memory_dir),
        }

    def clear_category(self, category: str, keep_last: int = 0) -> int:
        """Clear memories from a specific category.

        Args:
            category: Category to clear
            keep_last: Number of most recent entries to keep (default: 0 = delete all)

        Returns:
            Number of entries deleted
        """
        # Find all entries in category
        category_ids = [
            mid for mid, entry in self._index.items()
            if entry.get("category") == category
        ]

        # Sort by timestamp
        category_ids.sort(
            key=lambda mid: self._index[mid].get("timestamp", ""),
            reverse=True,
        )

        # Determine which to delete
        if keep_last > 0:
            to_delete = category_ids[keep_last:]
        else:
            to_delete = category_ids

        # Delete entries
        deleted_count = 0
        for memory_id in to_delete:
            entry_path = self.entries_dir / f"{memory_id}.json"
            try:
                if entry_path.exists():
                    entry_path.unlink()
                del self._index[memory_id]
                deleted_count += 1
            except OSError:
                pass

        # Save updated index
        if deleted_count > 0:
            self._save_index()

        return deleted_count

    def list_categories(self) -> list[str]:
        """List all available memory categories.

        Returns:
            Sorted list of category names
        """
        categories = {entry.get("category", "unknown") for entry in self._index.values()}
        return sorted(list(categories))
