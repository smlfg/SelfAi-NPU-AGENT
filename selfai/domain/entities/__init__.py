"""Domain entities for SelfAI.

Entities are objects with identity and lifecycle. Unlike value objects,
two entities are considered different even if their attributes match.

Entities:
    - Agent: AI agent with specific capabilities and personality
    - Subtask: Individual task within an execution plan
    - Plan: Complete execution plan with subtasks and merge strategy
    - Conversation: User-AI interaction exchange
    - ExecutionResult: Result of executing a subtask

Example:
    >>> from selfai.domain.entities import Agent
    >>> from selfai.domain.value_objects import AgentKey
    >>> agent = Agent(
    ...     key=AgentKey("code_helper"),
    ...     display_name="Code Helper",
    ...     system_prompt="You are a coding assistant.",
    ...     memory_categories=["coding", "python"]
    ... )
"""

from selfai.domain.entities.agent import Agent
from selfai.domain.entities.subtask import Subtask
from selfai.domain.entities.plan import Plan
from selfai.domain.entities.conversation import Conversation
from selfai.domain.entities.execution_result import ExecutionResult

__all__ = ["Agent", "Subtask", "Plan", "Conversation", "ExecutionResult"]
