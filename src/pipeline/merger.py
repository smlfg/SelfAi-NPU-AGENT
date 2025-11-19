"""Result Synthesis Module - Merge Subtask Outputs into Final Answer.

This module implements the Merger phase of the SelfAI pipeline. It synthesizes
all subtask results into a coherent final answer using LLM-based or fallback
strategies.

Key Responsibilities:
    - Collect and organize subtask outputs
    - Synthesize results using configured merge strategy
    - Provide fallback summarization when LLM unavailable
    - Save merged results to memory
    - Track merge timing and metadata

Design Principles:
    - Decoupling: No UI dependencies (use callbacks)
    - Resilience: Fallback to internal summary if LLM fails
    - Type Safety: Pydantic models for all I/O
    - Flexibility: Support multiple merge backends
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from pydantic import BaseModel, Field

from .models import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    MergeResult,
)


# ============================================================================
# EXCEPTIONS
# ============================================================================


class MergeError(Exception):
    """Base exception for all merger-related errors."""
    pass


# ============================================================================
# PROTOCOLS
# ============================================================================


class MergeLLMInterface(Protocol):
    """Protocol for LLM interfaces used for merging.

    Merge LLMs may have different methods than execution LLMs.
    """

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a chat response.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            timeout: Request timeout (optional)
            max_tokens: Max tokens to generate (optional)

        Returns:
            Generated response
        """
        ...

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        """Generate a streaming chat response.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            timeout: Request timeout (optional)
            max_tokens: Max tokens to generate (optional)

        Yields:
            Response chunks
        """
        ...


class ExecutionLLMInterface(Protocol):
    """Protocol for standard execution LLM interfaces (fallback for merge)."""

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
    """Protocol for agent objects."""

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
        """Get agent by key."""
        ...

    @property
    def active_agent(self) -> Optional[AgentInterface]:
        """Current active agent."""
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
        """Load relevant conversation history."""
        ...

    def save_conversation(
        self,
        agent: AgentInterface,
        user_prompt: str,
        llm_response: str,
    ) -> Optional[Path]:
        """Save conversation to memory."""
        ...


class ProgressCallback(Protocol):
    """Protocol for merge progress callbacks."""

    def on_merge_start(self, subtask_count: int) -> None:
        """Called when merge starts.

        Args:
            subtask_count: Number of subtasks being merged
        """
        ...

    def on_streaming_chunk(self, chunk: str) -> None:
        """Called for each streaming response chunk.

        Args:
            chunk: Response chunk
        """
        ...

    def on_merge_complete(self, is_fallback: bool) -> None:
        """Called when merge completes.

        Args:
            is_fallback: Whether fallback merge was used
        """
        ...


# ============================================================================
# CONFIGURATION
# ============================================================================


class MergerConfig(BaseModel):
    """Configuration for the Merger.

    Attributes:
        backend: LLM backend interface for merge
        backend_name: Name of the backend (e.g., "merge-ollama")
        backend_type: Type of backend (e.g., "local_ollama")
        timeout_seconds: Request timeout in seconds (default: 180.0)
        max_tokens: Maximum output tokens (default: 2048)
        streaming_enabled: Enable streaming responses (default: True)
        fallback_on_error: Use fallback summary if LLM fails (default: True)
    """
    backend: Any = Field(..., description="LLM backend interface")
    backend_name: str = Field(..., description="Backend name")
    backend_type: str = Field(default="llm", description="Backend type")
    timeout_seconds: float = Field(default=180.0, gt=0, description="Request timeout")
    max_tokens: int = Field(default=2048, gt=0, description="Max output tokens")
    streaming_enabled: bool = Field(default=True, description="Enable streaming")
    fallback_on_error: bool = Field(default=True, description="Use fallback on error")

    model_config = {"arbitrary_types_allowed": True}


# ============================================================================
# MERGER IMPLEMENTATION
# ============================================================================


class Merger:
    """Result synthesis orchestrator with LLM-based and fallback strategies.

    The Merger collects all subtask outputs and synthesizes them into a
    coherent final answer using the configured merge strategy and LLM backend.

    Example:
        ```python
        config = MergerConfig(
            backend=merge_ollama_interface,
            backend_name="merge-ollama",
            timeout_seconds=180.0
        )

        merger = Merger(
            config=config,
            agent_manager=agent_manager,
            memory_system=memory_system
        )

        result = merger.merge(
            plan=execution_plan,
            execution_result=execution_result,
            progress_callback=my_callback
        )
        print(f"Merge completed: {result.final_output[:100]}...")
        ```

    Attributes:
        config: Merger configuration
        agent_manager: Agent management interface
        memory_system: Memory persistence interface
    """

    def __init__(
        self,
        config: MergerConfig,
        agent_manager: AgentManagerInterface,
        memory_system: MemorySystemInterface,
    ) -> None:
        """Initialize the merger.

        Args:
            config: Merger configuration
            agent_manager: Agent manager interface
            memory_system: Memory system interface
        """
        self.config = config
        self.agent_manager = agent_manager
        self.memory_system = memory_system

    def merge(
        self,
        plan: ExecutionPlan,
        execution_result: ExecutionResult,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> MergeResult:
        """Merge all subtask results into a final answer.

        Args:
            plan: Original execution plan with merge strategy
            execution_result: Execution results to merge
            progress_callback: Optional progress callback

        Returns:
            Merge result with final synthesized output

        Raises:
            MergeError: If merge fails and fallback is disabled
        """
        started_at = datetime.now()

        if progress_callback:
            progress_callback.on_merge_start(len(execution_result.subtask_results))

        # Select merge agent
        merge_agent = self._select_merge_agent(plan)

        # Collect subtask outputs
        subtask_entries = self._collect_subtask_outputs(execution_result)

        if not subtask_entries:
            # No outputs to merge
            return self._create_empty_merge_result(
                merge_agent, started_at
            )

        # Try LLM merge
        try:
            final_output = self._merge_with_llm(
                plan, subtask_entries, merge_agent, progress_callback
            )

            # Save result
            result_path = self.memory_system.save_conversation(
                merge_agent,
                "Merge all subtask results",
                final_output,
            )

            completed_at = datetime.now()
            merge_time = (completed_at - started_at).total_seconds()

            if progress_callback:
                progress_callback.on_merge_complete(is_fallback=False)

            return MergeResult(
                final_output=final_output,
                strategy_used=plan.merge.strategy,
                agent_used=merge_agent.key,
                backend_used=self.config.backend_name,
                merge_time_seconds=merge_time,
                result_path=result_path,
                is_fallback=False,
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as exc:
            # LLM merge failed
            if not self.config.fallback_on_error:
                raise MergeError(f"Merge failed: {exc}") from exc

            # Use fallback
            final_output = self._fallback_merge(subtask_entries)

            result_path = self.memory_system.save_conversation(
                merge_agent,
                "Fallback merge summary",
                final_output,
            )

            completed_at = datetime.now()
            merge_time = (completed_at - started_at).total_seconds()

            if progress_callback:
                progress_callback.on_merge_complete(is_fallback=True)

            return MergeResult(
                final_output=final_output,
                strategy_used="Fallback internal summary",
                agent_used=merge_agent.key,
                backend_used="fallback",
                merge_time_seconds=merge_time,
                result_path=result_path,
                is_fallback=True,
                started_at=started_at,
                completed_at=completed_at,
            )

    def _select_merge_agent(self, plan: ExecutionPlan) -> AgentInterface:
        """Select the agent to perform the merge.

        Args:
            plan: Execution plan

        Returns:
            Agent for merge

        Raises:
            MergeError: If no suitable agent found
        """
        # Try agent from merge strategy
        merge_agent_key = plan.merge.agent_key
        if merge_agent_key:
            agent = self.agent_manager.get(merge_agent_key)
            if agent:
                return agent

        # Try "projektmanager" as default
        agent = self.agent_manager.get("projektmanager")
        if agent:
            return agent

        # Use active agent
        agent = self.agent_manager.active_agent
        if agent:
            return agent

        raise MergeError("No agent available for merge")

    def _collect_subtask_outputs(
        self,
        execution_result: ExecutionResult,
    ) -> List[Dict[str, str]]:
        """Collect outputs from all subtasks.

        Args:
            execution_result: Execution results

        Returns:
            List of subtask output entries
        """
        entries: List[Dict[str, str]] = []

        for result in execution_result.subtask_results:
            if result.status != ExecutionStatus.COMPLETED:
                continue

            if not result.output or not result.output.strip():
                continue

            entries.append({
                "id": result.subtask_id,
                "output": result.output,
            })

        return entries

    def _merge_with_llm(
        self,
        plan: ExecutionPlan,
        subtask_entries: List[Dict[str, str]],
        merge_agent: AgentInterface,
        progress_callback: Optional[ProgressCallback],
    ) -> str:
        """Merge using LLM backend.

        Args:
            plan: Execution plan with merge strategy
            subtask_entries: Subtask outputs
            merge_agent: Agent for merge
            progress_callback: Progress callback

        Returns:
            Merged output

        Raises:
            Exception: If LLM merge fails
        """
        # Build merge prompt
        combined_outputs = "\n\n".join(
            f"Subtask {entry['id']}:\n{entry['output']}"
            for entry in subtask_entries
        )

        steps_text = "\n".join(
            f"- {step.title}: {step.description}"
            for step in plan.merge.steps
        )

        final_prompt = (
            "You are the project manager. The following subtasks were executed:\n\n"
            f"{combined_outputs}\n\n"
            "TASK: Synthesize the results into a COHERENT answer that:\n"
            "1. Removes redundancy (don't just repeat everything)\n"
            "2. Identifies contradictions\n"
            "3. Provides a clear recommendation or summary\n\n"
            "If all subtasks say the same thing, summarize it in ONE sentence.\n"
        )

        if plan.merge.strategy:
            final_prompt += f"\nStrategy (suggested by planner): {plan.merge.strategy}\n"

        if steps_text:
            final_prompt += f"Suggested steps (from planner):\n{steps_text}\n"

        # Load context
        history = self.memory_system.load_relevant_context(
            merge_agent, final_prompt, limit=2
        )

        # Try streaming if available
        if self.config.streaming_enabled:
            if hasattr(self.config.backend, "stream_chat"):
                return self._stream_merge_chat(
                    merge_agent, final_prompt, progress_callback
                )
            elif hasattr(self.config.backend, "stream_generate_response"):
                return self._stream_merge_generate(
                    merge_agent, final_prompt, history, progress_callback
                )

        # Fallback to blocking
        if hasattr(self.config.backend, "chat"):
            return self.config.backend.chat(
                system_prompt=merge_agent.system_prompt,
                user_prompt=final_prompt,
                timeout=self.config.timeout_seconds,
                max_tokens=self.config.max_tokens,
            )
        else:
            return self.config.backend.generate_response(
                system_prompt=merge_agent.system_prompt,
                user_prompt=final_prompt,
                history=history,
                timeout=self.config.timeout_seconds,
                max_output_tokens=self.config.max_tokens,
            )

    def _stream_merge_chat(
        self,
        merge_agent: AgentInterface,
        prompt: str,
        progress_callback: Optional[ProgressCallback],
    ) -> str:
        """Stream merge using chat interface.

        Args:
            merge_agent: Agent for merge
            prompt: Merge prompt
            progress_callback: Progress callback

        Returns:
            Merged output
        """
        chunks: List[str] = []

        for chunk in self.config.backend.stream_chat(
            system_prompt=merge_agent.system_prompt,
            user_prompt=prompt,
            timeout=self.config.timeout_seconds,
            max_tokens=self.config.max_tokens,
        ):
            if chunk:
                chunks.append(chunk)
                if progress_callback:
                    progress_callback.on_streaming_chunk(chunk)

        return "".join(chunks)

    def _stream_merge_generate(
        self,
        merge_agent: AgentInterface,
        prompt: str,
        history: List[Dict[str, str]],
        progress_callback: Optional[ProgressCallback],
    ) -> str:
        """Stream merge using generate interface.

        Args:
            merge_agent: Agent for merge
            prompt: Merge prompt
            history: Conversation history
            progress_callback: Progress callback

        Returns:
            Merged output
        """
        chunks: List[str] = []

        for chunk in self.config.backend.stream_generate_response(
            system_prompt=merge_agent.system_prompt,
            user_prompt=prompt,
            history=history,
            timeout=self.config.timeout_seconds,
            max_output_tokens=self.config.max_tokens,
        ):
            if chunk:
                chunks.append(chunk)
                if progress_callback:
                    progress_callback.on_streaming_chunk(chunk)

        return "".join(chunks)

    def _fallback_merge(
        self,
        subtask_entries: List[Dict[str, str]],
    ) -> str:
        """Create fallback merge summary without LLM.

        Args:
            subtask_entries: Subtask outputs

        Returns:
            Fallback summary
        """
        if not subtask_entries:
            return "SelfAI could not find any subtask results."

        lines: List[str] = ["# Merge Summary (Fallback)", ""]

        for entry in subtask_entries:
            subtask_id = entry.get("id", "?")
            output = entry.get("output", "").strip()

            lines.append(f"## Subtask {subtask_id}")

            if output:
                snippet = (
                    output
                    if len(output) <= 600
                    else output[:600].rstrip() + "…"
                )
                lines.append("```")
                lines.append(snippet)
                lines.append("```")
            else:
                lines.append("(No output saved.)")

            lines.append("")

        return "\n".join(lines).strip()

    def _create_empty_merge_result(
        self,
        merge_agent: AgentInterface,
        started_at: datetime,
    ) -> MergeResult:
        """Create merge result for empty execution.

        Args:
            merge_agent: Merge agent
            started_at: Start timestamp

        Returns:
            Empty merge result
        """
        completed_at = datetime.now()
        merge_time = (completed_at - started_at).total_seconds()

        return MergeResult(
            final_output="No subtask results available for merge.",
            strategy_used="None (no results)",
            agent_used=merge_agent.key,
            backend_used="none",
            merge_time_seconds=merge_time,
            result_path=None,
            is_fallback=True,
            started_at=started_at,
            completed_at=completed_at,
        )
