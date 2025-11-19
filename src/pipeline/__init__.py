"""SelfAI Pipeline Package - Modular Planner-Executor-Merger Implementation.

This package implements a clean, decoupled pipeline architecture for task planning,
execution, and result synthesis. Each phase operates independently and communicates
via well-defined Pydantic data models.

Modules:
    models: Pydantic data models for pipeline communication
    planner: Task decomposition and planning
    executor: Subtask execution orchestration
    merger: Result synthesis and aggregation
    pipeline: High-level orchestrator for complete pipeline flow
"""

from .models import (
    ExecutionPlan,
    Subtask,
    MergeStrategy,
    ExecutionResult,
    SubtaskResult,
    MergeResult,
    PlannerContext,
    ExecutionStatus,
)
from .planner import Planner, PlannerConfig, create_fallback_plan
from .executor import Executor, ExecutorConfig, BackendConfig
from .merger import Merger, MergerConfig
from .pipeline import Pipeline, PipelineResult
from .agent_pipeline import AgentPipeline

__all__ = [
    # Data Models
    "ExecutionPlan",
    "Subtask",
    "MergeStrategy",
    "ExecutionResult",
    "SubtaskResult",
    "MergeResult",
    "PlannerContext",
    "ExecutionStatus",
    # Pipeline Components
    "Planner",
    "PlannerConfig",
    "create_fallback_plan",
    "Executor",
    "ExecutorConfig",
    "BackendConfig",
    "Merger",
    "MergerConfig",
    # Orchestrators
    "Pipeline",
    "PipelineResult",
    "AgentPipeline",  # CLI-compatible interface
]
