"""Pydantic Data Models for SelfAI Pipeline Communication.

This module defines strongly-typed data models for communication between pipeline
stages (Planner → Executor → Merger). All models use Pydantic for validation,
serialization, and type safety.

Key Design Principles:
    - Immutability: Use frozen=True where appropriate
    - Type Safety: Comprehensive type hints with strict validation
    - Serialization: JSON-compatible for storage and transmission
    - Documentation: Google-style docstrings for all models
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# ENUMERATIONS
# ============================================================================


class ExecutionStatus(str, Enum):
    """Status of a subtask or execution phase.

    Attributes:
        PENDING: Task has not started yet
        RUNNING: Task is currently executing
        COMPLETED: Task finished successfully
        FAILED: Task encountered an error and could not complete
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EngineType(str, Enum):
    """Supported execution engines for subtasks.

    Attributes:
        ANYTHINGLLM: AnythingLLM backend (NPU-accelerated)
        QNN: Qualcomm Neural Network (direct NPU)
        CPU: CPU-based inference (llama-cpp-python)
        SMOLAGENT: Tool-calling agent with smolagents
    """
    ANYTHINGLLM = "anythingllm"
    QNN = "qnn"
    CPU = "cpu"
    SMOLAGENT = "smolagent"


# ============================================================================
# PLANNER MODELS
# ============================================================================


class AgentInfo(BaseModel):
    """Information about a SelfAI agent available for task execution.

    Attributes:
        key: Unique identifier for the agent (e.g., "code_helfer")
        display_name: Human-readable name (e.g., "Code Helper")
        description: Brief description of agent capabilities
        memory_categories: Memory categories this agent uses
        workspace_slug: AnythingLLM workspace identifier
    """
    key: str = Field(..., min_length=1, description="Unique agent identifier")
    display_name: str = Field(..., min_length=1, description="Human-readable name")
    description: str = Field(default="", description="Agent capabilities description")
    memory_categories: List[str] = Field(default_factory=list, description="Memory categories")
    workspace_slug: str = Field(default="main", description="AnythingLLM workspace")

    model_config = ConfigDict(frozen=True)


class PlannerContext(BaseModel):
    """Context information provided to the planner for plan generation.

    This context helps the planner make informed decisions about task decomposition,
    agent selection, and resource allocation.

    Attributes:
        agents: List of available agents with their capabilities
        memory_summary: Summary of previous plans and executions
        available_tools: List of available tool names (for smolagent tasks)
        goal: The user's goal/request to be planned
    """
    agents: List[AgentInfo] = Field(..., min_length=1, description="Available agents")
    memory_summary: str = Field(default="", description="Historical context summary")
    available_tools: List[str] = Field(default_factory=list, description="Available tool names")
    goal: str = Field(..., min_length=1, description="User's goal to accomplish")

    @field_validator("agents")
    @classmethod
    def validate_agents_not_empty(cls, v: List[AgentInfo]) -> List[AgentInfo]:
        """Ensure at least one agent is available."""
        if not v:
            raise ValueError("At least one agent must be provided")
        return v


class MergeStep(BaseModel):
    """A single step in the merge strategy.

    Attributes:
        title: Brief title for this merge step
        description: Detailed description of what this step does
        depends_on: List of subtask IDs this step depends on
    """
    title: str = Field(..., min_length=1, max_length=160, description="Step title")
    description: str = Field(..., min_length=1, max_length=500, description="Step description")
    depends_on: List[str] = Field(default_factory=list, description="Dependency subtask IDs")


class MergeStrategy(BaseModel):
    """Strategy for merging subtask results into a final answer.

    Attributes:
        strategy: High-level description of the merge approach
        steps: Detailed steps for performing the merge
        agent_key: Agent to use for merge (default: "projektmanager")
    """
    strategy: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="High-level merge strategy description"
    )
    steps: List[MergeStep] = Field(default_factory=list, description="Merge execution steps")
    agent_key: Optional[str] = Field(default=None, description="Agent for merge execution")


class Subtask(BaseModel):
    """A single subtask in an execution plan.

    Attributes:
        id: Unique identifier (e.g., "S1", "S2")
        title: Brief, descriptive title
        objective: Clear statement of what this task should accomplish
        agent_key: Agent responsible for executing this task
        engine: Execution engine to use
        parallel_group: Group number for parallel execution (1-based)
        depends_on: List of subtask IDs that must complete before this one
        notes: Optional additional context or instructions
        tools: Tool names for smolagent tasks (only if engine=SMOLAGENT)
        max_steps: Maximum steps for smolagent execution
    """
    id: str = Field(..., pattern=r"^S\d+$", description="Subtask ID (e.g., S1)")
    title: str = Field(..., min_length=1, max_length=160, description="Subtask title")
    objective: str = Field(..., min_length=1, max_length=500, description="Task objective")
    agent_key: str = Field(..., min_length=1, description="Executing agent identifier")
    engine: EngineType = Field(..., description="Execution engine")
    parallel_group: int = Field(default=1, ge=1, description="Parallel execution group")
    depends_on: List[str] = Field(default_factory=list, description="Dependency subtask IDs")
    notes: str = Field(default="", max_length=500, description="Additional notes")
    tools: Optional[List[str]] = Field(default=None, description="Tools for smolagent")
    max_steps: Optional[int] = Field(default=None, ge=1, description="Max smolagent steps")

    @field_validator("tools")
    @classmethod
    def validate_tools_with_engine(cls, v: Optional[List[str]], info) -> Optional[List[str]]:
        """Ensure tools are only specified for smolagent engine."""
        if v is not None and info.data.get("engine") != EngineType.SMOLAGENT:
            raise ValueError("Tools can only be specified for smolagent engine")
        return v


class ExecutionPlan(BaseModel):
    """Complete execution plan generated by the planner.

    This is the primary output of the Planner phase and the input to the Executor phase.

    Attributes:
        subtasks: List of all subtasks to execute
        merge: Strategy for merging results
        metadata: Additional metadata (planner info, timestamps, etc.)
    """
    subtasks: List[Subtask] = Field(..., min_length=1, description="Subtasks to execute")
    merge: MergeStrategy = Field(..., description="Result merge strategy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Plan metadata")

    @field_validator("subtasks")
    @classmethod
    def validate_subtask_ids_unique(cls, v: List[Subtask]) -> List[Subtask]:
        """Ensure all subtask IDs are unique."""
        ids = [task.id for task in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Subtask IDs must be unique")
        return v

    @field_validator("subtasks")
    @classmethod
    def validate_dependencies_exist(cls, v: List[Subtask]) -> List[Subtask]:
        """Ensure all dependencies reference existing subtasks."""
        valid_ids = {task.id for task in v}
        for task in v:
            for dep_id in task.depends_on:
                if dep_id not in valid_ids:
                    raise ValueError(
                        f"Subtask {task.id} depends on non-existent task {dep_id}"
                    )
        return v


# ============================================================================
# EXECUTOR MODELS
# ============================================================================


class SubtaskResult(BaseModel):
    """Result of executing a single subtask.

    Attributes:
        subtask_id: ID of the subtask that was executed
        status: Execution status
        output: Generated output/response from the LLM
        error: Error message if status is FAILED
        result_path: Path to saved result file (optional)
        backend_used: Name of the LLM backend that executed this task
        execution_time_seconds: Time taken to execute
        started_at: Execution start timestamp
        completed_at: Execution completion timestamp
    """
    subtask_id: str = Field(..., description="Subtask ID")
    status: ExecutionStatus = Field(..., description="Execution status")
    output: str = Field(default="", description="Generated output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    result_path: Optional[Path] = Field(default=None, description="Path to result file")
    backend_used: str = Field(..., description="LLM backend name")
    execution_time_seconds: float = Field(default=0.0, ge=0, description="Execution duration")
    started_at: datetime = Field(default_factory=datetime.now, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ExecutionResult(BaseModel):
    """Complete result of executing all subtasks in a plan.

    This is the output of the Executor phase and the input to the Merger phase.

    Attributes:
        plan_id: Identifier for the executed plan
        subtask_results: Results for each executed subtask
        overall_status: Overall execution status
        total_execution_time_seconds: Total time for all subtasks
        started_at: Overall execution start timestamp
        completed_at: Overall execution completion timestamp
        failed_subtasks: List of subtask IDs that failed
    """
    plan_id: str = Field(..., description="Plan identifier")
    subtask_results: List[SubtaskResult] = Field(..., description="All subtask results")
    overall_status: ExecutionStatus = Field(..., description="Overall execution status")
    total_execution_time_seconds: float = Field(default=0.0, ge=0, description="Total duration")
    started_at: datetime = Field(default_factory=datetime.now, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    failed_subtasks: List[str] = Field(default_factory=list, description="Failed subtask IDs")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("overall_status")
    @classmethod
    def validate_overall_status_consistency(cls, v: ExecutionStatus, info) -> ExecutionStatus:
        """Ensure overall status matches subtask statuses."""
        results = info.data.get("subtask_results", [])
        if not results:
            return v

        statuses = {result.status for result in results}

        if ExecutionStatus.FAILED in statuses and v != ExecutionStatus.FAILED:
            raise ValueError("Overall status must be FAILED if any subtask failed")

        if ExecutionStatus.RUNNING in statuses and v == ExecutionStatus.COMPLETED:
            raise ValueError("Overall status cannot be COMPLETED if subtasks are RUNNING")

        return v


# ============================================================================
# MERGER MODELS
# ============================================================================


class MergeResult(BaseModel):
    """Result of merging all subtask outputs into a final answer.

    This is the final output of the Merger phase.

    Attributes:
        final_output: Synthesized final answer
        strategy_used: Description of the merge strategy applied
        agent_used: Agent that performed the merge
        backend_used: LLM backend used for merge
        merge_time_seconds: Time taken for merge
        result_path: Path to saved merge result (optional)
        is_fallback: Whether this is a fallback merge (no LLM used)
        started_at: Merge start timestamp
        completed_at: Merge completion timestamp
    """
    final_output: str = Field(..., min_length=1, description="Final synthesized answer")
    strategy_used: str = Field(..., description="Merge strategy description")
    agent_used: str = Field(..., description="Agent identifier")
    backend_used: str = Field(..., description="LLM backend name")
    merge_time_seconds: float = Field(default=0.0, ge=0, description="Merge duration")
    result_path: Optional[Path] = Field(default=None, description="Path to result file")
    is_fallback: bool = Field(default=False, description="Is fallback merge")
    started_at: datetime = Field(default_factory=datetime.now, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ============================================================================
# CONFIGURATION MODELS
# ============================================================================


class LLMBackendConfig(BaseModel):
    """Configuration for an LLM backend.

    Attributes:
        name: Backend name (e.g., "anythingllm", "qnn", "cpu")
        type: Backend type/category
        base_url: API base URL (for HTTP backends)
        model_path: Path to model file (for local backends)
        timeout: Request timeout in seconds
        max_tokens: Maximum output tokens
        headers: HTTP headers (for API backends)
    """
    name: str = Field(..., min_length=1, description="Backend name")
    type: str = Field(..., min_length=1, description="Backend type")
    base_url: Optional[str] = Field(default=None, description="API base URL")
    model_path: Optional[Path] = Field(default=None, description="Model file path")
    timeout: float = Field(default=60.0, gt=0, description="Request timeout")
    max_tokens: int = Field(default=2048, gt=0, description="Max output tokens")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")

    model_config = ConfigDict(arbitrary_types_allowed=True)
