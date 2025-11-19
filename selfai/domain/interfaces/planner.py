"""Planner service interface for task decomposition.

This module defines the protocol for planning services that decompose
high-level goals into executable subtasks.
"""

from typing import Protocol, Callable, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerContext:
    """Context information provided to the planner.

    This immutable value object contains information the planner uses
    to create intelligent task decompositions.

    Attributes:
        agents: List of available agents with their capabilities.
        memory_summary: Summary of past planning history.
        tool_capabilities: Optional list of available tools.
    """

    agents: list[dict[str, str]]
    memory_summary: str
    tool_capabilities: Optional[list[str]] = None


class IPlannerService(Protocol):
    """Protocol defining the interface for planning services.

    Planning services decompose high-level user goals into structured
    execution plans (DPPM format) with subtasks and merge strategies.

    Methods:
        plan: Generate an execution plan from a goal.
        validate_plan: Check plan structure for correctness.
        healthcheck: Verify planner service availability.
    """

    def plan(
        self,
        goal: str,
        context: PlannerContext,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> dict[str, object]:
        """Generate an execution plan for the given goal.

        Creates a structured plan (DPPM format) decomposing the goal into
        subtasks, specifying dependencies, parallelization, and merge strategy.

        Args:
            goal: The user's high-level objective.
            context: Planning context with available agents and history.
            progress_callback: Optional callback for streaming progress updates.
                Called with each chunk of text as the plan is generated.

        Returns:
            Plan dictionary with structure:
            {
                "subtasks": [
                    {
                        "id": "S1",
                        "title": "Task name",
                        "objective": "What to accomplish",
                        "agent_key": "agent_identifier",
                        "engine": "anythingllm",
                        "parallel_group": 1,
                        "depends_on": []
                    },
                    ...
                ],
                "merge": {
                    "strategy": "How to combine results",
                    "steps": [...]
                }
            }

        Raises:
            PlannerError: If planning fails or service is unreachable.
            ValidationError: If generated plan is invalid.

        Example:
            >>> planner = OllamaPlannerAdapter(base_url="http://localhost:11434")
            >>> context = PlannerContext(
            ...     agents=[{"key": "code_helper", "display_name": "Code Helper"}],
            ...     memory_summary="No past plans"
            ... )
            >>> plan = planner.plan(
            ...     goal="Create a Python web scraper",
            ...     context=context
            ... )
            >>> print(len(plan["subtasks"]))
            3
        """
        ...

    def validate_plan(self, plan_data: dict[str, object]) -> list[str]:
        """Validate plan structure and return any issues.

        Checks for:
        - Required fields presence
        - Valid agent keys
        - Correct dependency references
        - Valid parallel groups
        - Circular dependencies

        Args:
            plan_data: Plan dictionary to validate.

        Returns:
            List of validation error/warning messages.
            Empty list if plan is valid.

        Example:
            >>> planner = OllamaPlannerAdapter()
            >>> plan = {"subtasks": [{"id": "S1"}]}  # Missing required fields
            >>> issues = planner.validate_plan(plan)
            >>> print(issues)
            ["Subtask S1 missing 'title' field", "Subtask S1 missing 'agent_key'"]
        """
        ...

    def healthcheck(self) -> bool:
        """Check if the planner service is available.

        Returns:
            True if service is reachable and functional, False otherwise.

        Example:
            >>> planner = OllamaPlannerAdapter(base_url="http://localhost:11434")
            >>> if planner.healthcheck():
            ...     print("Planner ready")
            ... else:
            ...     print("Planner unavailable")
        """
        ...
