"""Task Planning Module - DPPM Plan Generation.

This module implements the Planner phase of the SelfAI pipeline. It generates
task decomposition plans using the DPPM (Decompose-Parallel Plan-Merge) methodology.

Key Responsibilities:
    - Generate execution plans from user goals
    - Validate plan structure and dependencies
    - Provide plan optimization and fallback strategies
    - Decouple planning logic from UI/orchestration concerns

Design Principles:
    - Single Responsibility: Focus solely on plan generation
    - Dependency Injection: Accept external interfaces via constructor
    - Type Safety: Use Pydantic models for all I/O
    - Testability: No global state, pure functional core
"""

from __future__ import annotations

import json
import textwrap
from typing import Any, Callable, Dict, List, Optional, Protocol

import httpx
from pydantic import BaseModel, Field

from .models import (
    AgentInfo,
    EngineType,
    ExecutionPlan,
    MergeStep,
    MergeStrategy,
    PlannerContext,
    Subtask,
)


# ============================================================================
# EXCEPTIONS
# ============================================================================


class PlannerError(Exception):
    """Base exception for all planner-related errors."""
    pass


class PlanValidationError(PlannerError):
    """Raised when a generated plan fails validation."""

    def __init__(self, message: str, plan_data: Optional[Dict[str, Any]] = None):
        """Initialize validation error with optional plan data.

        Args:
            message: Error description
            plan_data: The invalid plan data (for debugging)
        """
        super().__init__(message)
        self.plan_data = plan_data


class PlanGenerationError(PlannerError):
    """Raised when plan generation fails (network, API, timeout, etc.)."""
    pass


# ============================================================================
# PROTOCOLS
# ============================================================================


class ProgressCallback(Protocol):
    """Protocol for plan generation progress callbacks.

    Implementations can display streaming plan generation progress without
    coupling the planner to specific UI frameworks.
    """

    def __call__(self, chunk: str) -> None:
        """Called for each chunk of streaming plan generation.

        Args:
            chunk: A piece of the generated plan text
        """
        ...


# ============================================================================
# CONFIGURATION
# ============================================================================


class PlannerConfig(BaseModel):
    """Configuration for the Planner.

    Attributes:
        base_url: Ollama API base URL
        model: Model name to use for planning (e.g., "gemma3:1b")
        timeout: Request timeout in seconds
        max_tokens: Maximum tokens for plan generation
        temperature: Sampling temperature (lower = more focused)
        headers: Additional HTTP headers for authentication
    """
    base_url: str = Field(..., description="Ollama API base URL")
    model: str = Field(..., description="Model name for planning")
    timeout: float = Field(default=180.0, gt=0, description="Request timeout")
    max_tokens: int = Field(default=768, gt=0, description="Max generation tokens")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Sampling temperature")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")


# ============================================================================
# PLANNER IMPLEMENTATION
# ============================================================================


class Planner:
    """Task decomposition planner using DPPM methodology.

    The Planner generates execution plans by communicating with an Ollama LLM endpoint.
    It converts user goals into structured task decompositions with dependencies,
    parallel execution groups, and merge strategies.

    Example:
        ```python
        config = PlannerConfig(
            base_url="http://localhost:11434",
            model="gemma3:1b",
            timeout=180.0
        )

        planner = Planner(config)

        context = PlannerContext(
            agents=[AgentInfo(key="analyst", display_name="Analyst", ...)],
            memory_summary="Previous analysis completed",
            goal="Analyze market trends"
        )

        plan = planner.generate_plan(context)
        print(f"Generated {len(plan.subtasks)} subtasks")
        ```

    Attributes:
        config: Planner configuration
        generate_url: Full URL for Ollama generate endpoint
    """

    def __init__(self, config: PlannerConfig) -> None:
        """Initialize the planner with configuration.

        Args:
            config: Planner configuration settings
        """
        self.config = config
        self.generate_url = f"{config.base_url.rstrip('/')}/api/generate"

    def healthcheck(self) -> bool:
        """Check if the Ollama server is reachable.

        Returns:
            True if server is healthy, False otherwise

        Raises:
            PlannerError: If healthcheck fails
        """
        try:
            with httpx.Client(timeout=min(5.0, self.config.timeout)) as client:
                response = client.get(
                    f"{self.config.base_url.rstrip('/')}/api/tags",
                    headers=self.config.headers or None,
                )
                response.raise_for_status()
                return True
        except Exception as exc:
            raise PlannerError(f"Ollama healthcheck failed: {exc}") from exc

    def generate_plan(
        self,
        context: PlannerContext,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ExecutionPlan:
        """Generate an execution plan from the given context.

        Args:
            context: Planning context with agents, memory, and goal
            progress_callback: Optional callback for streaming progress

        Returns:
            Validated execution plan ready for execution

        Raises:
            PlanGenerationError: If plan generation fails
            PlanValidationError: If generated plan is invalid
        """
        prompt = self._build_prompt(context)

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": bool(progress_callback),
            "format": "json",
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        raw_response = ""

        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                if progress_callback:
                    raw_response = self._stream_request(
                        client, payload, progress_callback
                    )
                else:
                    raw_response = self._blocking_request(client, payload)
        except httpx.TimeoutException as exc:
            raise PlanGenerationError(
                f"Ollama did not respond within {self.config.timeout} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise PlanGenerationError(
                f"Ollama HTTP error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise PlanGenerationError(
                f"Error contacting Ollama: {exc}"
            ) from exc

        if not raw_response:
            raise PlanGenerationError("Ollama returned no data")

        return self._parse_and_validate_plan(raw_response, context)

    def _build_prompt(self, context: PlannerContext) -> str:
        """Build the planning prompt from context.

        Args:
            context: Planning context

        Returns:
            Formatted prompt string
        """
        # Build agent list
        agent_lines = []
        for agent in context.agents:
            agent_lines.append(
                f"- {agent.key}: {agent.display_name} – {agent.description or 'No description'}"
            )
        agents_text = "\n".join(agent_lines) if agent_lines else "- No agents available"

        # Build tools list
        if context.available_tools:
            tools_text = "\n".join(f"- {tool}" for tool in context.available_tools)
            tools_text += "\n- final_answer"
        else:
            tools_text = "- final_answer"

        # Template
        template = textwrap.dedent(
            """
            You are a DPPM planner (Decompose–Parallel Plan–Merge) for SelfAI. Generate ONLY JSON in this schema:
            {{
              "subtasks": [
                {{
                  "id": "S1",
                  "title": "short title",
                  "objective": "clear objective (max 160 chars)",
                  "agent_key": "code_helfer",
                  "engine": "anythingllm",
                  "parallel_group": 1,
                  "depends_on": [],
                  "notes": "optional notes (max 160 chars)"
                }}
              ],
              "merge": {{
                "strategy": "Brief merge description (max 160 chars)",
                "steps": [
                  {{
                    "title": "Step",
                    "description": "concrete merge action (max 160 chars)",
                    "depends_on": ["S1", "S2"]
                  }}
                ]
              }}
            }}

            DPPM Rules:
            1. Decompose – break goal into max 5 independent subtasks
            2. Parallel Plan – assign parallel_group for concurrent execution
            3. Merge – define consistent result synthesis

            Constraints:
            - Return ONLY pure JSON, no markdown, no backticks
            - All strings must be single-line, ≤160 chars
            - Use only available agent_key values
            - Use only these engines: anythingllm, qnn, cpu, smolagent
            - Create 2-5 subtasks minimum
            - End with END_OF_PLAN marker
            - For research/file/calculation tasks: use engine "smolagent"
            - For smolagent tasks: add "tools": ["tool_name"] field
            - Use ONLY these tool names (do not invent):
{tool_names}
            - For pure text/planning: use "anythingllm"

            Available Agents:
{agent_overview}

            Memory Summary:
{memory_summary}

            Goal:
{goal}
            """
        ).strip()

        return template.format(
            agent_overview=agents_text,
            memory_summary=context.memory_summary or "(no memory available)",
            tool_names=tools_text,
            goal=context.goal.strip(),
        )

    def _stream_request(
        self,
        client: httpx.Client,
        payload: Dict[str, Any],
        progress_callback: ProgressCallback,
    ) -> str:
        """Execute streaming request to Ollama.

        Args:
            client: HTTP client
            payload: Request payload
            progress_callback: Callback for streaming chunks

        Returns:
            Complete aggregated response
        """
        aggregated = ""
        buffer = ""

        with client.stream(
            "POST",
            self.generate_url,
            json=payload,
            headers=self.config.headers or None,
        ) as response:
            response.raise_for_status()

            for chunk in response.iter_text():
                if not chunk:
                    continue

                buffer += chunk

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    if not line:
                        continue

                    if line.startswith("data:"):
                        line = line[len("data:"):].strip()

                    if not line or line in ("[DONE]", "DONE"):
                        continue

                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if "response" in parsed and parsed["response"]:
                        part = parsed["response"]
                        aggregated += part
                        progress_callback(part)

                    if parsed.get("done"):
                        if parsed.get("response"):
                            aggregated += parsed["response"]
                        return aggregated

        return aggregated

    def _blocking_request(
        self,
        client: httpx.Client,
        payload: Dict[str, Any],
    ) -> str:
        """Execute blocking request to Ollama.

        Args:
            client: HTTP client
            payload: Request payload

        Returns:
            Complete response
        """
        response = client.post(
            self.generate_url,
            json=payload,
            headers=self.config.headers or None,
        )
        response.raise_for_status()

        body = response.json()
        raw_response = body.get("response") or body.get("thinking")

        if not raw_response:
            raise PlanGenerationError(
                f"Ollama response missing 'response' field: {body}"
            )

        return raw_response

    def _parse_and_validate_plan(
        self,
        raw_response: str,
        context: PlannerContext,
    ) -> ExecutionPlan:
        """Parse raw JSON response and validate as ExecutionPlan.

        Args:
            raw_response: Raw JSON string from Ollama
            context: Planning context for validation

        Returns:
            Validated ExecutionPlan

        Raises:
            PlanValidationError: If plan is invalid
        """
        # Strip markdown code fences
        cleaned = self._strip_code_fences(raw_response)

        # Strip END_OF_PLAN marker
        if "END_OF_PLAN" in cleaned:
            cleaned = cleaned.split("END_OF_PLAN", 1)[0].strip()

        # Parse JSON
        try:
            plan_data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(
                f"Planner output is not valid JSON: {exc}. "
                f"Raw response: {cleaned[:300]}"
            ) from exc

        # Normalize and validate
        plan_data = self._normalize_plan_data(plan_data, context)

        # Convert to Pydantic model (performs validation)
        try:
            return ExecutionPlan(**plan_data)
        except Exception as exc:
            raise PlanValidationError(
                f"Plan validation failed: {exc}",
                plan_data=plan_data
            ) from exc

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from text.

        Args:
            text: Text potentially containing ```json ... ```

        Returns:
            Cleaned text
        """
        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.strip()

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        return cleaned

    @staticmethod
    def _normalize_plan_data(
        plan_data: Dict[str, Any],
        context: PlannerContext,
    ) -> Dict[str, Any]:
        """Normalize and sanitize plan data.

        Args:
            plan_data: Raw plan dictionary
            context: Planning context

        Returns:
            Normalized plan dictionary
        """
        # Get allowed agent keys
        allowed_agents = {agent.key for agent in context.agents}
        default_agent = context.agents[0].key if context.agents else "code_helfer"

        # Normalize subtasks
        for task in plan_data.get("subtasks", []) or []:
            # Fix agent_key
            if not isinstance(task.get("agent_key"), str) or not task.get("agent_key"):
                task["agent_key"] = default_agent
            elif task["agent_key"] not in allowed_agents:
                task["agent_key"] = default_agent

            # Fix parallel_group
            try:
                pg_value = int(task.get("parallel_group", 1))
                task["parallel_group"] = max(1, pg_value)
            except (TypeError, ValueError):
                task["parallel_group"] = 1

            # Ensure notes is string
            if not isinstance(task.get("notes"), str):
                task["notes"] = ""

        # Ensure merge exists
        if "merge" not in plan_data or not plan_data["merge"]:
            plan_data["merge"] = {
                "strategy": "Combine all subtask results",
                "steps": []
            }

        return plan_data


# ============================================================================
# FALLBACK PLAN GENERATOR
# ============================================================================


def create_fallback_plan(goal: str, agent_key: str) -> ExecutionPlan:
    """Create a simple fallback plan when planner fails.

    This generates a basic 2-subtask plan for emergency situations.

    Args:
        goal: User's goal
        agent_key: Agent to use for all subtasks

    Returns:
        Basic execution plan
    """
    sanitized_goal = goal.strip()[:500]  # Limit length

    subtasks = [
        Subtask(
            id="S1",
            title="Analyze goal",
            objective=f"Analyze the goal: {sanitized_goal}",
            agent_key=agent_key,
            engine=EngineType.ANYTHINGLLM,
            parallel_group=1,
            depends_on=[],
            notes="Auto-generated fallback plan – review critically",
        ),
        Subtask(
            id="S2",
            title="Formulate answer",
            objective=f"Formulate detailed answer for: {sanitized_goal}",
            agent_key=agent_key,
            engine=EngineType.ANYTHINGLLM,
            parallel_group=2,
            depends_on=["S1"],
            notes="Auto-generated fallback plan",
        ),
    ]

    merge = MergeStrategy(
        strategy="Combine analysis and answer into consistent result",
        steps=[
            MergeStep(
                title="Synthesis",
                description="Merge analysis and answer into final recommendation",
                depends_on=["S2"],
            )
        ],
    )

    return ExecutionPlan(
        subtasks=subtasks,
        merge=merge,
        metadata={
            "planner_provider": "fallback",
            "goal": sanitized_goal,
        },
    )
