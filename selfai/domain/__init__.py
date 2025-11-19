"""Domain layer for SelfAI NPU Agent.

This package contains the core business logic, entities, and domain interfaces
(ports) that define the system's behavior independent of external dependencies.

The domain layer follows these principles:
1. No dependencies on infrastructure or frameworks
2. Pure business logic only
3. All entities are testable in isolation
4. Interfaces (protocols) define contracts for external implementations

Architecture:
    - entities/: Core domain objects (Agent, Plan, Subtask, etc.)
    - value_objects/: Immutable value types (AgentKey, ExecutionStatus, etc.)
    - interfaces/: Abstract protocols for dependency inversion

Example:
    >>> from selfai.domain.entities import Agent
    >>> from selfai.domain.value_objects import AgentKey
    >>> agent = Agent(
    ...     key=AgentKey("code_helper"),
    ...     display_name="Code Helper",
    ...     system_prompt="You are a helpful coding assistant."
    ... )
"""

from selfai.domain import entities, interfaces, value_objects

__all__ = ["entities", "interfaces", "value_objects"]

__version__ = "2.0.0"
__author__ = "SelfAI Team"
