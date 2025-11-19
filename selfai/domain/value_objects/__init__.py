"""Value objects for the SelfAI domain.

Value objects are immutable, self-validating objects that represent
domain concepts without identity. They are compared by value, not reference.

Value Objects:
    - AgentKey: Unique agent identifier
    - ExecutionStatus: Status of task execution
    - PlanMetadata: Plan metadata information

Example:
    >>> from selfai.domain.value_objects import AgentKey
    >>> key1 = AgentKey("code_helper")
    >>> key2 = AgentKey("code_helper")
    >>> assert key1 == key2  # Value equality
"""

from selfai.domain.value_objects.agent_key import AgentKey
from selfai.domain.value_objects.execution_status import ExecutionStatus
from selfai.domain.value_objects.plan_metadata import PlanMetadata

__all__ = ["AgentKey", "ExecutionStatus", "PlanMetadata"]
