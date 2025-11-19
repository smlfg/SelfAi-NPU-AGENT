"""Context Manager - Intelligent context retrieval with relevance scoring.

This module provides advanced context filtering and relevance scoring for
memory retrieval, improving the quality of conversation context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_manager import MemoryEntry, MemoryManager


class ContextManager:
    """Manages intelligent context retrieval with relevance scoring.

    This class implements smart context filtering to retrieve the most
    relevant conversation memories based on the current query.

    Attributes:
        memory_manager: The MemoryManager instance to query
        default_threshold: Minimum relevance score for inclusion (0.0-1.0)
    """

    def __init__(self, memory_manager: MemoryManager, default_threshold: float = 0.3):
        """Initialize the context manager.

        Args:
            memory_manager: MemoryManager instance
            default_threshold: Minimum relevance score (default: 0.3)
        """
        self.memory_manager = memory_manager
        self.default_threshold = default_threshold

    def calculate_relevance(
        self,
        query_tags: list[str],
        memory_tags: list[str],
    ) -> float:
        """Calculate relevance score between query and memory tags.

        Uses Jaccard similarity: intersection / union

        Args:
            query_tags: Tags extracted from current query
            memory_tags: Tags associated with a memory entry

        Returns:
            Relevance score between 0.0 and 1.0

        Examples:
            >>> manager = ContextManager(memory_manager)
            >>> score = manager.calculate_relevance(
            ...     ["python", "sorting"],
            ...     ["python", "sorting", "algorithms"]
            ... )
            >>> # score = 2/3 ≈ 0.67
        """
        if not query_tags or not memory_tags:
            return 0.0

        query_set = set(tag.lower() for tag in query_tags)
        memory_set = set(tag.lower() for tag in memory_tags)

        intersection = len(query_set & memory_set)
        union = len(query_set | memory_set)

        if union == 0:
            return 0.0

        return intersection / union

    def classify_query(self, query_text: str) -> tuple[str, list[str]]:
        """Classify a query and extract relevant tags.

        Args:
            query_text: The query text to analyze

        Returns:
            Tuple of (intent, tags)
            - intent: Primary intent category
            - tags: List of extracted tags

        Examples:
            >>> manager = ContextManager(memory_manager)
            >>> intent, tags = manager.classify_query("How do I sort a list in Python?")
            >>> # intent = "coding"
            >>> # tags = ["python", "sorting", "list"]
        """
        query_lower = query_text.lower()
        tags: list[str] = []

        # Programming languages
        languages = {
            "python": ["python", "py"],
            "javascript": ["javascript", "js", "node"],
            "typescript": ["typescript", "ts"],
            "java": ["java"],
            "rust": ["rust"],
            "go": ["golang", "go"],
            "cpp": ["c++", "cpp"],
            "csharp": ["c#", "csharp"],
        }

        for tag, keywords in languages.items():
            if any(kw in query_lower for kw in keywords):
                tags.append(tag)

        # Intent detection
        intent_patterns = {
            "coding": ["code", "program", "function", "class", "implement"],
            "debugging": ["debug", "error", "fix", "bug", "issue", "problem"],
            "documentation": ["explain", "what is", "how does", "document", "describe"],
            "refactoring": ["refactor", "clean", "improve", "optimize"],
            "testing": ["test", "unittest", "testing", "pytest"],
            "planning": ["plan", "design", "architecture", "structure"],
        }

        detected_intent = "general"
        for intent, keywords in intent_patterns.items():
            if any(kw in query_lower for kw in keywords):
                detected_intent = intent
                tags.append(intent)
                break

        # Extract key nouns (simple heuristic)
        common_topics = [
            "list", "dict", "array", "string", "file", "database", "api",
            "sorting", "search", "algorithm", "function", "class", "method",
            "async", "sync", "thread", "process", "network", "http"
        ]

        for topic in common_topics:
            if topic in query_lower:
                tags.append(topic)

        return detected_intent, list(set(tags))

    def get_relevant_context(
        self,
        agent_key: str,
        query_text: str,
        category: str | None = None,
        limit: int = 3,
        threshold: float | None = None,
    ) -> list[dict[str, str]]:
        """Get relevant conversation context for a query.

        This method:
        1. Classifies the query to extract tags
        2. Retrieves candidate memories
        3. Scores each memory for relevance
        4. Returns the most relevant context messages

        Args:
            agent_key: Agent identifier
            query_text: Current query text
            category: Optional category filter
            limit: Maximum number of conversations to include (default: 3)
            threshold: Minimum relevance score (default: use default_threshold)

        Returns:
            List of message dicts suitable for LLM chat APIs

        Examples:
            >>> manager = ContextManager(memory_manager)
            >>> context = manager.get_relevant_context(
            ...     agent_key="code_helper",
            ...     query_text="How do I sort a dictionary in Python?",
            ...     limit=3
            ... )
        """
        if threshold is None:
            threshold = self.default_threshold

        # Classify query and extract tags
        intent, query_tags = self.classify_query(query_text)

        # If category not specified, use intent as category hint
        if category is None:
            category = intent if intent != "general" else None

        # Retrieve candidate memories (get more than needed for scoring)
        candidates = self.memory_manager.query_memories(
            agent_key=agent_key,
            category=category,
            limit=limit * 3,  # Get 3x as many for better scoring
        )

        # Score each candidate
        scored_memories: list[tuple[MemoryEntry, float]] = []
        for memory in candidates:
            score = self.calculate_relevance(query_tags, memory.metadata.tags)
            scored_memories.append((memory, score))

        # Filter by threshold and sort by score
        relevant = [(m, s) for m, s in scored_memories if s >= threshold]

        # If no memories meet threshold, take top N anyway
        if not relevant:
            relevant = sorted(scored_memories, key=lambda x: x[1], reverse=True)[:limit]
        else:
            relevant = sorted(relevant, key=lambda x: x[1], reverse=True)[:limit]

        # Convert to chat messages (oldest first for context)
        messages: list[dict[str, str]] = []
        for memory, score in reversed(relevant):  # Reverse to get oldest first
            # Update relevance score in memory
            memory.relevance_score = score
            messages.append({"role": "user", "content": memory.user_message})
            messages.append({"role": "assistant", "content": memory.assistant_message})

        return messages

    def get_session_context(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Get all messages from a specific session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages (default: 10)

        Returns:
            List of message dicts in chronological order
        """
        # Get all memories (we'll filter manually since session_id isn't indexed)
        all_memories = self.memory_manager.query_memories(limit=1000)

        # Filter by session_id
        session_memories = [
            m for m in all_memories
            if m.metadata.session_id == session_id
        ]

        # Sort by timestamp (oldest first)
        session_memories.sort(key=lambda m: m.created_at)

        # Apply limit
        session_memories = session_memories[:limit]

        # Convert to messages
        messages: list[dict[str, str]] = []
        for memory in session_memories:
            messages.append({"role": "user", "content": memory.user_message})
            messages.append({"role": "assistant", "content": memory.assistant_message})

        return messages
