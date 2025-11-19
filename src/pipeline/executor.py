"""Task Execution Module - Subtask Orchestration and LLM Invocation.

This module implements the Executor phase of the SelfAI pipeline. It executes
planned subtasks using configured LLM backends with automatic fallback and
retry logic.

Key Responsibilities:
    - Execute subtasks from execution plans
    - Manage LLM backend fallback (AnythingLLM → QNN → CPU)
    - Handle retry logic and error recovery
    - Save results to memory system
    - Track execution status and timing

Design Principles:
    - Decoupling: No UI dependencies (use callbacks)
    - Resilience: Multi-backend fallback with retries
    - Observability: Progress callbacks and detailed results
    - Type Safety: Pydantic models for all I/O
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from pydantic import BaseModel, Field

from .models import (
    EngineType,
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    SubtaskResult,
)


# ============================================================================
# EXCEPTIONS
# ============================================================================


class ExecutionError(Exception):
    """Base exception for all executor-related errors."""
    pass


class SubtaskExecutionError(ExecutionError):
    """Raised when a subtask fails to execute."""

    def __init__(self, subtask_id: str, message: str):
        """Initialize subtask execution error.

        Args:
            subtask_id: ID of the failed subtask
            message: Error description
        """
        super().__init__(f"Subtask {subtask_id}: {message}")
        self.subtask_id = subtask_id


# ============================================================================
# PROTOCOLS
# ============================================================================


class LLMInterface(Protocol):
    """Protocol for LLM backend interfaces.

    Any LLM backend (AnythingLLM, QNN, CPU) must implement this interface
    to be usable by the executor.
    """

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Optional[Iterable[Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            history: Conversation history (optional)
            timeout: Request timeout (optional)
            max_output_tokens: Max tokens to generate (optional)

        Returns:
            Generated response text
        """
        ...

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Optional[Iterable[Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        """Generate a streaming response from the LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            history: Conversation history (optional)
            timeout: Request timeout (optional)
            max_output_tokens: Max tokens to generate (optional)

        Yields:
            Response chunks
        """
        ...


class AgentInterface(Protocol):
    """Protocol for agent objects.

    Agents provide system prompts and identity information for LLM execution.
    """

    @property
    def key(self) -> str:
        """Agent unique identifier."""
        ...

    @property
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable agent name."""
        ...


class AgentManagerInterface(Protocol):
    """Protocol for agent manager."""

    def get(self, key: str) -> Optional[AgentInterface]:
        """Get agent by key.

        Args:
            key: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        ...


class MemorySystemInterface(Protocol):
    """Protocol for memory system."""

    def load_relevant_context(
        self,
        agent: AgentInterface,
        query: str,
        *,
        limit: int = 2,
    ) -> List[Dict[str, str]]:
        """Load relevant conversation history.

        Args:
            agent: Agent to load context for
            query: Query to find relevant context
            limit: Maximum number of context entries

        Returns:
            List of conversation history entries
        """
        ...

    def save_conversation(
        self,
        agent: AgentInterface,
        user_prompt: str,
        llm_response: str,
    ) -> Optional[Path]:
        """Save conversation to memory.

        Args:
            agent: Agent that handled the conversation
            user_prompt: User's input
            llm_response: LLM's response

        Returns:
            Path to saved file or None
        """
        ...


class ProgressCallback(Protocol):
    """Protocol for execution progress callbacks."""

    def on_subtask_start(self, subtask_id: str, title: str) -> None:
        """Called when a subtask starts.

        Args:
            subtask_id: Subtask identifier
            title: Subtask title
        """
        ...

    def on_subtask_complete(self, subtask_id: str, status: ExecutionStatus) -> None:
        """Called when a subtask completes.

        Args:
            subtask_id: Subtask identifier
            status: Final status
        """
        ...

    def on_streaming_chunk(self, chunk: str) -> None:
        """Called for each streaming response chunk.

        Args:
            chunk: Response chunk
        """
        ...

    def on_backend_switch(self, backend_name: str) -> None:
        """Called when switching to a different backend.

        Args:
            backend_name: Name of the new backend
        """
        ...


# ============================================================================
# CONFIGURATION
# ============================================================================


class BackendConfig(BaseModel):
    """Configuration for a single LLM backend.

    Attributes:
        interface: LLM interface instance
        name: Backend name (e.g., "anythingllm", "qnn", "cpu")
        label: Display label for this backend
        type: Backend type/category
    """
    interface: Any = Field(..., description="LLM interface instance")
    name: str = Field(..., description="Backend name")
    label: str = Field(..., description="Display label")
    type: str = Field(default="llm", description="Backend type")

    model_config = {"arbitrary_types_allowed": True}


class ExecutorConfig(BaseModel):
    """Configuration for the Executor.

    Attributes:
        backends: List of available LLM backends (in priority order)
        retry_attempts: Number of retries per backend (default: 2)
        retry_delay_seconds: Delay between retries in seconds (default: 5.0)
        timeout_seconds: Request timeout in seconds (default: 120.0)
        max_output_tokens: Maximum output tokens (default: 1024)
        streaming_enabled: Enable streaming responses (default: True)
    """
    backends: List[BackendConfig] = Field(..., min_length=1, description="LLM backends")
    retry_attempts: int = Field(default=2, ge=0, description="Retry attempts per backend")
    retry_delay_seconds: float = Field(default=5.0, ge=0, description="Retry delay")
    timeout_seconds: float = Field(default=120.0, gt=0, description="Request timeout")
    max_output_tokens: int = Field(default=1024, gt=0, description="Max output tokens")
    streaming_enabled: bool = Field(default=True, description="Enable streaming")

    model_config = {"arbitrary_types_allowed": True}


# ============================================================================
# EXECUTOR IMPLEMENTATION
# ============================================================================


class Executor:
    """Subtask execution orchestrator with multi-backend fallback.

    The Executor takes an execution plan and executes each subtask using
    configured LLM backends. It handles backend fallback, retry logic,
    memory management, and result tracking.

    Example:
        ```python
        config = ExecutorConfig(
            backends=[
                BackendConfig(interface=anythingllm, name="anythingllm", label="NPU"),
                BackendConfig(interface=cpu_llm, name="cpu", label="CPU"),
            ],
            retry_attempts=2,
            timeout_seconds=120.0
        )

        executor = Executor(
            config=config,
            agent_manager=agent_manager,
            memory_system=memory_system
        )

        result = executor.execute(plan, progress_callback=my_callback)
        print(f"Execution completed: {result.overall_status}")
        ```

    Attributes:
        config: Executor configuration
        agent_manager: Agent management interface
        memory_system: Memory persistence interface
    """

    def __init__(
        self,
        config: ExecutorConfig,
        agent_manager: AgentManagerInterface,
        memory_system: MemorySystemInterface,
    ) -> None:
        """Initialize the executor.

        Args:
            config: Executor configuration
            agent_manager: Agent manager interface
            memory_system: Memory system interface
        """
        self.config = config
        self.agent_manager = agent_manager
        self.memory_system = memory_system

        self._active_backend_index = 0

    def execute(
        self,
        plan: ExecutionPlan,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ExecutionResult:
        """Execute all subtasks in the plan.

        Args:
            plan: Execution plan to run
            progress_callback: Optional progress callback

        Returns:
            Execution result with all subtask results

        Raises:
            ExecutionError: If execution fails critically
        """
        started_at = datetime.now()
        subtask_results: List[SubtaskResult] = []
        failed_subtasks: List[str] = []

        for subtask in plan.subtasks:
            if progress_callback:
                progress_callback.on_subtask_start(subtask.id, subtask.title)

            try:
                result = self._execute_subtask(subtask, progress_callback)
                subtask_results.append(result)

                if result.status == ExecutionStatus.FAILED:
                    failed_subtasks.append(subtask.id)

                if progress_callback:
                    progress_callback.on_subtask_complete(subtask.id, result.status)

            except SubtaskExecutionError as exc:
                # Create failed result
                result = SubtaskResult(
                    subtask_id=subtask.id,
                    status=ExecutionStatus.FAILED,
                    error=str(exc),
                    backend_used="none",
                    started_at=datetime.now(),
                )
                subtask_results.append(result)
                failed_subtasks.append(subtask.id)

                if progress_callback:
                    progress_callback.on_subtask_complete(
                        subtask.id, ExecutionStatus.FAILED
                    )

                # Fail fast if critical error
                raise ExecutionError(f"Subtask {subtask.id} failed: {exc}") from exc

        completed_at = datetime.now()
        total_time = (completed_at - started_at).total_seconds()

        overall_status = (
            ExecutionStatus.FAILED
            if failed_subtasks
            else ExecutionStatus.COMPLETED
        )

        return ExecutionResult(
            plan_id=plan.metadata.get("plan_id", "unknown"),
            subtask_results=subtask_results,
            overall_status=overall_status,
            total_execution_time_seconds=total_time,
            started_at=started_at,
            completed_at=completed_at,
            failed_subtasks=failed_subtasks,
        )

    def _execute_subtask(
        self,
        subtask,
        progress_callback: Optional[ProgressCallback],
    ) -> SubtaskResult:
        """Execute a single subtask.

        Args:
            subtask: Subtask to execute
            progress_callback: Progress callback

        Returns:
            Subtask result

        Raises:
            SubtaskExecutionError: If subtask execution fails
        """
        started_at = datetime.now()

        # Get agent
        agent = self.agent_manager.get(subtask.agent_key)
        if agent is None:
            raise SubtaskExecutionError(
                subtask.id,
                f"Agent '{subtask.agent_key}' not found"
            )

        # Load context
        context_hint = f"{subtask.objective}\n{subtask.notes}".strip()
        history = self.memory_system.load_relevant_context(
            agent, context_hint, limit=2
        )

        # Build prompt
        prompt = (
            f"Subtask {subtask.id}: {subtask.objective}\n"
            f"NOTES: {subtask.notes}"
        )

        # Execute based on engine
        if subtask.engine == EngineType.SMOLAGENT:
            output, backend_name = self._execute_with_smolagent(
                subtask, agent, prompt, history, progress_callback
            )
        else:
            output, backend_name = self._execute_with_llm(
                agent, prompt, history, progress_callback
            )

        # Save to memory
        result_path = self.memory_system.save_conversation(agent, prompt, output)

        completed_at = datetime.now()
        execution_time = (completed_at - started_at).total_seconds()

        return SubtaskResult(
            subtask_id=subtask.id,
            status=ExecutionStatus.COMPLETED,
            output=output,
            error=None,
            result_path=result_path,
            backend_used=backend_name,
            execution_time_seconds=execution_time,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _execute_with_llm(
        self,
        agent: AgentInterface,
        prompt: str,
        history: List[Dict[str, str]],
        progress_callback: Optional[ProgressCallback],
    ) -> tuple[str, str]:
        """Execute with LLM backend (with fallback).

        Args:
            agent: Agent to use
            prompt: User prompt
            history: Conversation history
            progress_callback: Progress callback

        Returns:
            Tuple of (output, backend_name)

        Raises:
            SubtaskExecutionError: If all backends fail
        """
        last_error: Optional[Exception] = None

        # Try all backends in order
        backend_order = [self._active_backend_index] + [
            i for i in range(len(self.config.backends))
            if i != self._active_backend_index
        ]

        for backend_index in backend_order:
            backend = self.config.backends[backend_index]

            # Switch backend if needed
            if backend_index != self._active_backend_index:
                self._active_backend_index = backend_index
                if progress_callback:
                    progress_callback.on_backend_switch(backend.name)

            try:
                output = self._call_backend(
                    backend, agent, prompt, history, progress_callback
                )
                return output, backend.name

            except Exception as exc:
                last_error = exc
                continue

        # All backends failed
        raise SubtaskExecutionError(
            "unknown",
            f"All LLM backends failed. Last error: {last_error}"
        ) from last_error

    def _call_backend(
        self,
        backend: BackendConfig,
        agent: AgentInterface,
        prompt: str,
        history: List[Dict[str, str]],
        progress_callback: Optional[ProgressCallback],
    ) -> str:
        """Call a single backend with retry logic.

        Args:
            backend: Backend to call
            agent: Agent to use
            prompt: User prompt
            history: Conversation history
            progress_callback: Progress callback

        Returns:
            Generated output

        Raises:
            Exception: If backend fails after all retries
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.config.retry_attempts + 1):
            try:
                # Try streaming if enabled
                if self.config.streaming_enabled and hasattr(
                    backend.interface, "stream_generate_response"
                ):
                    chunks: List[str] = []
                    for chunk in backend.interface.stream_generate_response(
                        system_prompt=agent.system_prompt,
                        user_prompt=prompt,
                        history=history,
                        timeout=self.config.timeout_seconds,
                        max_output_tokens=self.config.max_output_tokens,
                    ):
                        if chunk:
                            chunks.append(chunk)
                            if progress_callback:
                                progress_callback.on_streaming_chunk(chunk)
                    return "".join(chunks)

                # Fallback to blocking
                return backend.interface.generate_response(
                    system_prompt=agent.system_prompt,
                    user_prompt=prompt,
                    history=history,
                    timeout=self.config.timeout_seconds,
                    max_output_tokens=self.config.max_output_tokens,
                )

            except Exception as exc:
                last_exception = exc

                # Retry if attempts remaining
                if attempt < self.config.retry_attempts:
                    time.sleep(self.config.retry_delay_seconds)
                    continue

                # All retries exhausted
                raise exc from last_exception

        # Should never reach here, but for type safety
        raise last_exception or Exception("Backend call failed")

    def _execute_with_smolagent(
        self,
        subtask,
        agent: AgentInterface,
        prompt: str,
        history: List[Dict[str, str]],
        progress_callback: Optional[ProgressCallback],
    ) -> tuple[str, str]:
        """Execute with smolagent (tool-calling).

        Args:
            subtask: Subtask configuration
            agent: Agent to use
            prompt: User prompt
            history: Conversation history
            progress_callback: Progress callback

        Returns:
            Tuple of (output, backend_name)

        Raises:
            SubtaskExecutionError: If smolagent fails
        """
        # NOTE: This is a placeholder. The actual implementation would import
        # and use SmolAgentRunner from the legacy code. For now, we raise
        # an error to indicate it's not yet implemented in the refactored version.
        raise SubtaskExecutionError(
            subtask.id,
            "Smolagent execution not yet implemented in refactored executor. "
            "Use legacy execution_dispatcher.py for smolagent tasks."
        )
