"""Agent Pipeline - CLI-Compatible Pipeline Wrapper.

This module provides the AgentPipeline class that satisfies the CLI contract
for the SelfAI system. It wraps the modular Planner→Executor→Merger pipeline
with a simple run() interface.

Usage:
    from src.core.config import load_settings
    from src.pipeline import AgentPipeline

    settings = load_settings()
    pipeline = AgentPipeline(backend_manager, system_prompt="You are helpful.")

    response = pipeline.run("What is Python?")
    print(response)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import load_settings
from src.core.logger import get_logger

from .models import (
    AgentInfo,
    ExecutionPlan,
    PlannerContext,
)
from .planner import Planner, PlannerConfig, create_fallback_plan
from .executor import Executor, ExecutorConfig, BackendConfig
from .merger import Merger, MergerConfig

__all__ = ["AgentPipeline"]


logger = get_logger(__name__)


class AgentPipeline:
    """CLI-compatible agent pipeline wrapper.

    This class provides a simple interface to the complete Planner→Executor→Merger
    pipeline, matching the CLI contract expected by src/cli.py.

    The pipeline flow:
        1. User input received via run()
        2. Planner decomposes into subtasks (optional)
        3. Executor runs subtasks with tools/LLM backends
        4. Merger synthesizes results (optional)
        5. Final answer returned as string

    Example:
        ```python
        from src.pipeline import AgentPipeline

        # Initialize with backend manager
        pipeline = AgentPipeline(
            backend_manager=my_backend_manager,
            system_prompt="You are a helpful coding assistant."
        )

        # Run pipeline
        response = pipeline.run("Explain Python decorators")
        print(response)

        # Clear memory
        pipeline.clear_memory_global()
        ```

    Attributes:
        backend_manager: Backend manager instance (provides LLM interfaces)
        system_prompt: Default system prompt for LLM interactions
        conversation_history: In-memory conversation history
        planner: Optional planner instance
        executor: Executor instance
        merger: Optional merger instance
    """

    def __init__(
        self,
        backend_manager: Any,
        system_prompt: str = "You are a helpful AI assistant.",
    ) -> None:
        """Initialize the agent pipeline.

        Args:
            backend_manager: Backend manager providing LLM interfaces
            system_prompt: Default system prompt for interactions

        Example:
            ```python
            pipeline = AgentPipeline(
                backend_manager=backend_manager,
                system_prompt="You are a Python expert."
            )
            ```
        """
        self.backend_manager = backend_manager
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, str]] = []

        logger.info("Initializing AgentPipeline")

        # Load settings
        try:
            self.settings = load_settings()
        except Exception as exc:
            logger.warning(f"Could not load settings: {exc}. Using defaults.")
            self.settings = None

        # Initialize pipeline components
        self._init_planner()
        self._init_executor()
        self._init_merger()

        logger.info(
            f"AgentPipeline initialized "
            f"(planner={'enabled' if self.planner else 'disabled'}, "
            f"merger={'enabled' if self.merger else 'disabled'})"
        )

    def _init_planner(self) -> None:
        """Initialize planner if enabled in config."""
        self.planner: Optional[Planner] = None

        if not self.settings:
            logger.info("No settings available, planner disabled")
            return

        if not self.settings.planner or not self.settings.planner.enabled:
            logger.info("Planner disabled in configuration")
            return

        try:
            # Get first planner provider
            provider_config = self.settings.planner.providers[0]

            planner_config = PlannerConfig(
                base_url=provider_config.base_url,
                model=provider_config.model,
                timeout=provider_config.timeout,
                max_tokens=provider_config.max_tokens,
                headers=provider_config.headers,
            )

            self.planner = Planner(planner_config)
            logger.info("✓ Planner initialized")
        except Exception as exc:
            logger.warning(f"Planner initialization failed: {exc}")
            self.planner = None

    def _init_executor(self) -> None:
        """Initialize executor with backend manager."""
        # Extract backends from backend_manager
        backends: List[BackendConfig] = []

        # If backend_manager has a list of backends
        if hasattr(self.backend_manager, 'backends'):
            for backend in self.backend_manager.backends:
                backends.append(
                    BackendConfig(
                        interface=backend.get('interface'),
                        name=backend.get('name', 'unknown'),
                        label=backend.get('label', 'Backend'),
                        type=backend.get('type', 'llm'),
                    )
                )
        # If backend_manager is itself an interface
        elif hasattr(self.backend_manager, 'generate_response'):
            backends.append(
                BackendConfig(
                    interface=self.backend_manager,
                    name='default',
                    label='Default Backend',
                    type='llm',
                )
            )
        else:
            raise ValueError("Invalid backend_manager: no backends found")

        # Create executor config
        config = ExecutorConfig(
            backends=backends,
            retry_attempts=2,
            retry_delay_seconds=5.0,
            timeout_seconds=120.0,
            max_output_tokens=1024,
            streaming_enabled=False,  # Simple mode for CLI
        )

        # Create simple agent manager wrapper
        class SimpleAgentManager:
            """Simple agent manager for standalone pipeline."""

            def __init__(self, system_prompt: str):
                self.system_prompt = system_prompt

            def get(self, key: str):
                """Return a simple agent object."""
                class SimpleAgent:
                    def __init__(self, system_prompt: str):
                        self.key = key
                        self.system_prompt = system_prompt
                        self.display_name = "Agent"

                return SimpleAgent(self.system_prompt)

            @property
            def active_agent(self):
                return self.get("default")

        # Create simple memory system wrapper
        class SimpleMemorySystem:
            """Simple memory system for standalone pipeline."""

            def __init__(self):
                self.history: List[Dict[str, str]] = []

            def load_relevant_context(self, agent, query, limit=2):
                """Return recent history."""
                return self.history[-limit:] if self.history else []

            def save_conversation(self, agent, user_prompt, llm_response):
                """Save to history."""
                self.history.append({"role": "user", "content": user_prompt})
                self.history.append({"role": "assistant", "content": llm_response})
                return None

        self.agent_manager = SimpleAgentManager(self.system_prompt)
        self.memory_system = SimpleMemorySystem()

        self.executor = Executor(
            config=config,
            agent_manager=self.agent_manager,
            memory_system=self.memory_system,
        )

        logger.info("✓ Executor initialized")

    def _init_merger(self) -> None:
        """Initialize merger if enabled in config."""
        self.merger: Optional[Merger] = None

        if not self.settings:
            logger.info("No settings available, merger disabled")
            return

        if not self.settings.merge or not self.settings.merge.enabled:
            logger.info("Merger disabled in configuration")
            return

        try:
            # Import merge interface
            from selfai.core.merge_ollama_interface import MergeOllamaInterface

            # Get first merge provider
            provider_config = self.settings.merge.providers[0]

            merge_interface = MergeOllamaInterface(
                base_url=provider_config.base_url,
                model=provider_config.model,
                timeout=provider_config.timeout,
                max_tokens=provider_config.max_tokens,
                headers=provider_config.headers,
            )

            merger_config = MergerConfig(
                backend=merge_interface,
                backend_name=provider_config.name,
                backend_type=provider_config.type,
                timeout_seconds=provider_config.timeout,
                max_tokens=provider_config.max_tokens,
                streaming_enabled=False,
                fallback_on_error=True,
            )

            self.merger = Merger(
                config=merger_config,
                agent_manager=self.agent_manager,
                memory_system=self.memory_system,
            )

            logger.info("✓ Merger initialized")
        except Exception as exc:
            logger.warning(f"Merger initialization failed: {exc}")
            self.merger = None

    def run(self, user_input: str) -> str:
        """Run the pipeline for the given user input.

        This is the main entry point matching the CLI contract.

        Args:
            user_input: User's question or request

        Returns:
            str: Final answer from the pipeline

        Example:
            ```python
            response = pipeline.run("What is Python?")
            print(response)
            ```
        """
        logger.info(f"Pipeline run started: {user_input[:50]}...")

        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        try:
            # Determine if we should use full pipeline or simple execution
            use_full_pipeline = (
                self.planner is not None
                and len(user_input.split()) > 10  # Only plan for complex requests
            )

            if use_full_pipeline:
                # Full pipeline: Plan → Execute → Merge
                result = self._run_full_pipeline(user_input)
            else:
                # Simple execution: Direct LLM call
                result = self._run_simple(user_input)

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": result
            })

            logger.info("Pipeline run completed successfully")
            return result

        except Exception as exc:
            logger.error(f"Pipeline run failed: {exc}", exc_info=True)
            error_msg = f"Sorry, I encountered an error: {exc}"

            self.conversation_history.append({
                "role": "assistant",
                "content": error_msg
            })

            return error_msg

    def _run_full_pipeline(self, user_input: str) -> str:
        """Run full Planner→Executor→Merger pipeline.

        Args:
            user_input: User's input

        Returns:
            Final answer string
        """
        logger.info("Running full pipeline (Planner→Executor→Merger)")

        # Phase 1: Plan
        plan = self._plan(user_input)

        # Phase 2: Execute
        execution_result = self.executor.execute(plan)

        # Phase 3: Merge (optional)
        if self.merger:
            merge_result = self.merger.merge(plan, execution_result)
            return merge_result.final_output
        else:
            # Fallback: Just return first subtask result
            if execution_result.subtask_results:
                return execution_result.subtask_results[0].output
            else:
                return "No results generated."

    def _plan(self, user_input: str) -> ExecutionPlan:
        """Generate execution plan.

        Args:
            user_input: User's input

        Returns:
            ExecutionPlan
        """
        # Build planner context
        agent_info = AgentInfo(
            key="default",
            display_name="Agent",
            description="General-purpose assistant",
            memory_categories=[],
            workspace_slug="main",
        )

        context = PlannerContext(
            agents=[agent_info],
            memory_summary="",
            available_tools=[],
            goal=user_input,
        )

        # Generate plan
        if self.planner:
            try:
                plan = self.planner.generate_plan(context)
                return plan
            except Exception as exc:
                logger.warning(f"Planner failed, using fallback: {exc}")
                return create_fallback_plan(user_input, "default")
        else:
            return create_fallback_plan(user_input, "default")

    def _run_simple(self, user_input: str) -> str:
        """Run simple direct LLM call (no planning).

        Args:
            user_input: User's input

        Returns:
            LLM response string
        """
        logger.info("Running simple execution (direct LLM)")

        # Get first backend
        backend = self.executor.config.backends[0]

        # Build history
        history = [
            msg for msg in self.conversation_history
            if msg["role"] in ("user", "assistant")
        ]

        # Call LLM
        try:
            if hasattr(backend.interface, 'generate_response'):
                response = backend.interface.generate_response(
                    system_prompt=self.system_prompt,
                    user_prompt=user_input,
                    history=history[-4:],  # Last 2 exchanges
                    timeout=120.0,
                    max_output_tokens=1024,
                )
                return response
            else:
                # Fallback: just echo
                return f"Backend does not support generate_response. Input was: {user_input}"

        except Exception as exc:
            logger.error(f"Simple execution failed: {exc}")
            raise

    def clear_memory_global(self) -> None:
        """Clear conversation history and memory.

        This matches the CLI contract for memory management.

        Example:
            ```python
            pipeline.clear_memory_global()
            print("Memory cleared!")
            ```
        """
        logger.info("Clearing global memory")
        self.conversation_history.clear()

        if hasattr(self.memory_system, 'history'):
            self.memory_system.history.clear()

        logger.info("✓ Memory cleared")
