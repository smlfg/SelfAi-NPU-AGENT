"""SelfAI Refactored Package - Clean Architecture Implementation.

This package provides a modular, type-safe, testable implementation of the
SelfAI system with clean separation of concerns and SOLID principles.

Quick Start:
    ```python
    from src.core import load_settings, setup_logging, LogLevel
    from src.pipeline import Pipeline

    # Setup
    setup_logging(level=LogLevel.INFO)
    settings = load_settings()

    # Initialize pipeline
    pipeline = Pipeline(settings, agent_manager, memory_system)

    # Run
    result = pipeline.run(goal="Analyze sales data")
    if result.success:
        print(result.final_output)
    ```

Packages:
    core: Configuration, logging, and provider wrappers
    pipeline: Task planning, execution, and result synthesis
"""

from .core import (
    load_settings,
    setup_logging,
    LogLevel,
    get_logger,
    AppConfig,
)

from .pipeline import (
    Pipeline,
    PipelineResult,
    ExecutionPlan,
    ExecutionResult,
    MergeResult,
)

__all__ = [
    # Core
    "load_settings",
    "setup_logging",
    "LogLevel",
    "get_logger",
    "AppConfig",
    # Pipeline
    "Pipeline",
    "PipelineResult",
    "ExecutionPlan",
    "ExecutionResult",
    "MergeResult",
]
