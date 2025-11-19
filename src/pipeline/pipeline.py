"""Pipeline Orchestrator - High-Level Planner→Executor→Merger Coordination.

This module provides the main Pipeline class that coordinates the three-phase
execution flow using the refactored modular components.

Usage:
    from src.core.config import load_settings
    from src.core.providers import NPUProvider, CPUProvider
    from src.pipeline import Pipeline

    settings = load_settings()
    pipeline = Pipeline(settings)
    result = pipeline.run(goal="Analyze sales data")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from src.core.config import AppConfig, load_settings
from src.core.logger import get_logger
from src.core.providers import (
    NPUProvider,
    CPUProvider,
    QNNProvider,
    PlannerProvider,
    MergeProvider,
)

from .models import (
    AgentInfo,
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    MergeResult,
    PlannerContext,
)
from .planner import Planner, PlannerConfig, create_fallback_plan
from .executor import Executor, ExecutorConfig, BackendConfig
from .merger import Merger, MergerConfig

__all__ = ["Pipeline", "PipelineResult"]


logger = get_logger(__name__)


# ============================================================================
# PROTOCOLS
# ============================================================================


class AgentManagerInterface(Protocol):
    """Protocol for agent manager."""

    def list_agents(self) -> List[Any]:
        """List all available agents."""
        ...

    def get(self, key: str) -> Optional[Any]:
        """Get agent by key."""
        ...

    @property
    def active_agent(self) -> Optional[Any]:
        """Get active agent."""
        ...


class MemorySystemInterface(Protocol):
    """Protocol for memory system."""

    def save_plan(self, goal: str, plan_data: Dict[str, Any]) -> Path:
        """Save execution plan."""
        ...

    def save_conversation(
        self,
        agent: Any,
        user_prompt: str,
        llm_response: str,
    ) -> Optional[Path]:
        """Save conversation."""
        ...

    def load_relevant_context(
        self,
        agent: Any,
        query: str,
        *,
        limit: int = 2,
    ) -> List[Dict[str, str]]:
        """Load relevant context."""
        ...


class ProgressCallback(Protocol):
    """Protocol for progress updates."""

    def on_phase_start(self, phase: str, description: str) -> None:
        """Called when a phase starts."""
        ...

    def on_phase_complete(self, phase: str, success: bool) -> None:
        """Called when a phase completes."""
        ...

    def on_subtask_start(self, subtask_id: str, title: str) -> None:
        """Called when a subtask starts."""
        ...

    def on_subtask_complete(self, subtask_id: str, status: ExecutionStatus) -> None:
        """Called when a subtask completes."""
        ...

    def on_streaming_chunk(self, chunk: str) -> None:
        """Called for streaming chunks."""
        ...


# ============================================================================
# PIPELINE RESULT
# ============================================================================


class PipelineResult:
    """Complete result of a pipeline execution.

    Attributes:
        plan: Generated execution plan
        execution_result: Subtask execution results
        merge_result: Final merged output
        success: Whether pipeline completed successfully
        error: Error message if failed
    """

    def __init__(
        self,
        plan: Optional[ExecutionPlan] = None,
        execution_result: Optional[ExecutionResult] = None,
        merge_result: Optional[MergeResult] = None,
        success: bool = False,
        error: Optional[str] = None,
    ):
        """Initialize pipeline result.

        Args:
            plan: Execution plan
            execution_result: Execution results
            merge_result: Merge result
            success: Success status
            error: Error message
        """
        self.plan = plan
        self.execution_result = execution_result
        self.merge_result = merge_result
        self.success = success
        self.error = error

    @property
    def final_output(self) -> Optional[str]:
        """Get final output if available."""
        return self.merge_result.final_output if self.merge_result else None

    def __repr__(self) -> str:
        """String representation."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"PipelineResult(status={status}, phases_completed={self._phases_completed()})"

    def _phases_completed(self) -> str:
        """Get string of completed phases."""
        phases = []
        if self.plan:
            phases.append("PLAN")
        if self.execution_result:
            phases.append("EXECUTE")
        if self.merge_result:
            phases.append("MERGE")
        return "→".join(phases) if phases else "NONE"


# ============================================================================
# PIPELINE CLASS
# ============================================================================


class Pipeline:
    """High-level pipeline orchestrator for Planner→Executor→Merger flow.

    This class provides a clean interface to the complete SelfAI pipeline,
    automatically configuring all components from settings and coordinating
    the three-phase execution flow.

    Example:
        ```python
        from src.core.config import load_settings
        from src.pipeline import Pipeline

        # Initialize pipeline from settings
        settings = load_settings()
        pipeline = Pipeline(settings, agent_manager, memory_system)

        # Run complete pipeline
        result = pipeline.run(
            goal="Analyze quarterly sales data and identify trends",
            progress_callback=my_callback
        )

        if result.success:
            print(f"Final answer: {result.final_output}")
        else:
            print(f"Pipeline failed: {result.error}")
        ```

    Attributes:
        settings: Application configuration
        agent_manager: Agent management interface
        memory_system: Memory persistence interface
        planner: Planner instance
        executor: Executor instance
        merger: Merger instance (optional)
    """

    def __init__(
        self,
        settings: AppConfig,
        agent_manager: AgentManagerInterface,
        memory_system: MemorySystemInterface,
    ):
        """Initialize pipeline from settings.

        Args:
            settings: Application configuration
            agent_manager: Agent manager instance
            memory_system: Memory system instance

        Raises:
            ValueError: If configuration invalid or required components unavailable
        """
        self.settings = settings
        self.agent_manager = agent_manager
        self.memory_system = memory_system

        logger.info("Initializing SelfAI Pipeline")

        # Initialize backends
        self._init_backends()

        # Initialize planner (optional)
        self.planner: Optional[Planner] = self._init_planner()

        # Initialize executor
        self.executor: Executor = self._init_executor()

        # Initialize merger (optional)
        self.merger: Optional[Merger] = self._init_merger()

        logger.info(
            f"Pipeline initialized "
            f"(planner={'enabled' if self.planner else 'disabled'}, "
            f"merger={'enabled' if self.merger else 'disabled'})"
        )

    def _init_backends(self) -> None:
        """Initialize LLM backends in priority order."""
        self.backends: List[BackendConfig] = []

        logger.info("Initializing LLM backends...")

        # 1. Try NPU (AnythingLLM)
        try:
            npu = NPUProvider(self.settings)
            self.backends.append(
                BackendConfig(
                    interface=npu.interface,
                    name="npu",
                    label="NPU",
                    type="npu",
                )
            )
            logger.info("✓ NPU backend initialized")
        except Exception as exc:
            logger.warning(f"NPU backend unavailable: {exc}")

        # 2. Try QNN (direct NPU)
        try:
            # Auto-discover QNN models
            models_root = Path(__file__).resolve().parent.parent.parent / "models"
            if models_root.exists():
                qnn_models = list(models_root.glob("*.qnn"))
                if qnn_models:
                    qnn = QNNProvider(self.settings, str(qnn_models[0]))
                    self.backends.append(
                        BackendConfig(
                            interface=qnn.interface,
                            name="qnn",
                            label="QNN",
                            type="qnn",
                        )
                    )
                    logger.info(f"✓ QNN backend initialized ({qnn_models[0].name})")
        except Exception as exc:
            logger.warning(f"QNN backend unavailable: {exc}")

        # 3. CPU fallback (required)
        try:
            cpu = CPUProvider(self.settings)
            self.backends.append(
                BackendConfig(
                    interface=cpu.interface,
                    name="cpu",
                    label="CPU",
                    type="cpu",
                )
            )
            logger.info("✓ CPU backend initialized")
        except Exception as exc:
            logger.error(f"CPU backend initialization failed: {exc}")
            raise ValueError("No LLM backends available") from exc

        if not self.backends:
            raise ValueError("No LLM backends could be initialized")

        logger.info(f"Initialized {len(self.backends)} LLM backend(s)")

    def _init_planner(self) -> Optional[Planner]:
        """Initialize planner if enabled."""
        if not self.settings.planner or not self.settings.planner.enabled:
            logger.info("Planner disabled in configuration")
            return None

        try:
            planner_provider = PlannerProvider(self.settings)
            logger.info("✓ Planner initialized")
            return planner_provider.interface
        except Exception as exc:
            logger.warning(f"Planner initialization failed: {exc}")
            return None

    def _init_executor(self) -> Executor:
        """Initialize executor with configured backends."""
        config = ExecutorConfig(
            backends=self.backends,
            retry_attempts=2,
            retry_delay_seconds=5.0,
            timeout_seconds=self.settings.planner.execution_timeout
            if self.settings.planner
            else 120.0,
            max_output_tokens=1024,
            streaming_enabled=self.settings.system.streaming_enabled,
        )

        return Executor(
            config=config,
            agent_manager=self.agent_manager,
            memory_system=self.memory_system,
        )

    def _init_merger(self) -> Optional[Merger]:
        """Initialize merger if enabled."""
        if not self.settings.merge or not self.settings.merge.enabled:
            logger.info("Merger disabled in configuration")
            return None

        try:
            merge_provider = MergeProvider(self.settings)

            config = MergerConfig(
                backend=merge_provider.interface,
                backend_name=merge_provider.provider_name,
                backend_type="ollama",
                timeout_seconds=self.settings.planner.execution_timeout
                if self.settings.planner
                else 180.0,
                max_tokens=2048,
                streaming_enabled=self.settings.system.streaming_enabled,
                fallback_on_error=True,
            )

            merger = Merger(
                config=config,
                agent_manager=self.agent_manager,
                memory_system=self.memory_system,
            )

            logger.info("✓ Merger initialized")
            return merger

        except Exception as exc:
            logger.warning(f"Merger initialization failed: {exc}")
            return None

    def run(
        self,
        goal: str,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> PipelineResult:
        """Run the complete pipeline for the given goal.

        Args:
            goal: User's goal/request
            progress_callback: Optional progress callback

        Returns:
            PipelineResult with complete execution details

        Example:
            ```python
            result = pipeline.run(
                goal="Analyze sales trends",
                progress_callback=my_callback
            )

            if result.success:
                print(result.final_output)
            else:
                print(f"Error: {result.error}")
            ```
        """
        logger.info(f"Starting pipeline for goal: {goal}")

        try:
            # Phase 1: Plan
            if progress_callback:
                progress_callback.on_phase_start("PLAN", "Generating execution plan")

            plan = self._plan(goal, progress_callback)

            if progress_callback:
                progress_callback.on_phase_complete("PLAN", True)

            # Phase 2: Execute
            if progress_callback:
                progress_callback.on_phase_start("EXECUTE", "Executing subtasks")

            execution_result = self._execute(plan, progress_callback)

            if progress_callback:
                progress_callback.on_phase_complete("EXECUTE", True)

            # Phase 3: Merge
            merge_result = None
            if self.merger:
                if progress_callback:
                    progress_callback.on_phase_start("MERGE", "Synthesizing results")

                merge_result = self._merge(plan, execution_result, progress_callback)

                if progress_callback:
                    progress_callback.on_phase_complete("MERGE", True)

            logger.info("Pipeline completed successfully")

            return PipelineResult(
                plan=plan,
                execution_result=execution_result,
                merge_result=merge_result,
                success=True,
            )

        except Exception as exc:
            logger.error(f"Pipeline failed: {exc}", exc_info=True)
            return PipelineResult(success=False, error=str(exc))

    def _plan(
        self,
        goal: str,
        progress_callback: Optional[ProgressCallback],
    ) -> ExecutionPlan:
        """Generate execution plan.

        Args:
            goal: User's goal
            progress_callback: Progress callback

        Returns:
            ExecutionPlan
        """
        # Build planner context
        agents = self.agent_manager.list_agents()
        agent_infos = [
            AgentInfo(
                key=agent.key,
                display_name=agent.display_name,
                description=agent.description or "",
                memory_categories=agent.memory_categories,
                workspace_slug=agent.workspace_slug,
            )
            for agent in agents
        ]

        context = PlannerContext(
            agents=agent_infos,
            memory_summary="",  # TODO: Implement memory summary
            available_tools=[],  # TODO: Get from tool registry
            goal=goal,
        )

        # Generate plan
        if self.planner:
            try:
                plan = self.planner.generate_plan(
                    context,
                    progress_callback=lambda chunk: (
                        progress_callback.on_streaming_chunk(chunk)
                        if progress_callback
                        else None
                    ),
                )
            except Exception as exc:
                logger.warning(f"Planner failed, using fallback: {exc}")
                plan = create_fallback_plan(goal, agents[0].key if agents else "default")
        else:
            # No planner, use fallback
            plan = create_fallback_plan(goal, agents[0].key if agents else "default")

        # Save plan
        self.memory_system.save_plan(goal, plan.model_dump())

        return plan

    def _execute(
        self,
        plan: ExecutionPlan,
        progress_callback: Optional[ProgressCallback],
    ) -> ExecutionResult:
        """Execute subtasks.

        Args:
            plan: Execution plan
            progress_callback: Progress callback

        Returns:
            ExecutionResult
        """
        return self.executor.execute(plan, progress_callback=progress_callback)

    def _merge(
        self,
        plan: ExecutionPlan,
        execution_result: ExecutionResult,
        progress_callback: Optional[ProgressCallback],
    ) -> MergeResult:
        """Merge results.

        Args:
            plan: Execution plan
            execution_result: Execution results
            progress_callback: Progress callback

        Returns:
            MergeResult
        """
        if not self.merger:
            raise ValueError("Merger not initialized")

        return self.merger.merge(
            plan=plan,
            execution_result=execution_result,
            progress_callback=progress_callback,
        )
