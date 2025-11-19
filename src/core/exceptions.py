"""Custom exception hierarchy for the AI NPU Agent project.

This module defines a comprehensive exception hierarchy following the principle of
specific, actionable error handling. Each exception type represents a distinct
failure mode with sufficient context for debugging and recovery.

Exception Hierarchy:
    SelfAIException (Base)
    ├── ConfigurationError
    │   ├── MissingConfigError
    │   ├── InvalidConfigError
    │   └── EnvironmentVariableError
    ├── BackendError
    │   ├── NPUConnectionError
    │   ├── AnythingLLMError
    │   ├── QNNError
    │   ├── CPUFallbackError
    │   └── BackendUnavailableError
    ├── InferenceError
    │   ├── ModelLoadError
    │   ├── TokenizationError
    │   ├── GenerationError
    │   └── StreamingError
    ├── PlanningError
    │   ├── PlanValidationError
    │   ├── PlanExecutionError
    │   ├── SubtaskError
    │   └── MergeError
    ├── AgentError
    │   ├── AgentNotFoundError
    │   ├── AgentLoadError
    │   └── ToolExecutionError
    └── MemoryError
        ├── MemoryLoadError
        ├── MemoryWriteError
        └── ContextFilterError

Usage:
    >>> from src.core.exceptions import NPUConnectionError, FallbackTriggered
    >>>
    >>> try:
    ...     connect_to_npu()
    ... except NPUConnectionError as e:
    ...     logger.error(f"NPU connection failed: {e.context}")
    ...     # Trigger fallback mechanism
    ...     raise FallbackTriggered("anythingllm", "qnn") from e
"""

from typing import Any, Dict, Optional


# =============================================================================
# BASE EXCEPTION
# =============================================================================


class SelfAIException(Exception):
    """Base exception for all SelfAI-related errors.

    All custom exceptions in the project inherit from this base class to
    enable unified exception handling and logging.

    Attributes:
        message: Human-readable error description.
        context: Additional context information (e.g., config keys, file paths).
        original_error: Optional wrapped exception from third-party libraries.
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        """Initialize the base exception.

        Args:
            message: Clear description of what went wrong.
            context: Dictionary with additional debugging information.
            original_error: The underlying exception, if this wraps another error.
        """
        self.message = message
        self.context = context or {}
        self.original_error = original_error
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the exception message with context information.

        Returns:
            Formatted error message including context details.
        """
        msg_parts = [self.message]

        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            msg_parts.append(f"Context: {context_str}")

        if self.original_error:
            msg_parts.append(f"Caused by: {type(self.original_error).__name__}: {self.original_error}")

        return " | ".join(msg_parts)


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================


class ConfigurationError(SelfAIException):
    """Base class for configuration-related errors."""
    pass


class MissingConfigError(ConfigurationError):
    """Raised when required configuration keys are missing.

    Example:
        >>> raise MissingConfigError(
        ...     "NPU base URL not configured",
        ...     context={"missing_key": "npu_provider.base_url"}
        ... )
    """
    pass


class InvalidConfigError(ConfigurationError):
    """Raised when configuration values fail validation.

    Example:
        >>> raise InvalidConfigError(
        ...     "Invalid timeout value",
        ...     context={"key": "planner.timeout", "value": -10}
        ... )
    """
    pass


class EnvironmentVariableError(ConfigurationError):
    """Raised when required environment variables are missing or invalid.

    Example:
        >>> raise EnvironmentVariableError(
        ...     "API_KEY environment variable not set",
        ...     context={"var_name": "API_KEY"}
        ... )
    """
    pass


# =============================================================================
# BACKEND ERRORS
# =============================================================================


class BackendError(SelfAIException):
    """Base class for LLM backend communication errors."""

    def __init__(
        self,
        message: str,
        backend_name: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        """Initialize backend error.

        Args:
            message: Error description.
            backend_name: Name of the backend that failed (e.g., "anythingllm", "qnn").
            context: Additional context information.
            original_error: Underlying exception.
        """
        self.backend_name = backend_name
        full_context = context or {}
        full_context["backend"] = backend_name
        super().__init__(message, full_context, original_error)


class NPUConnectionError(BackendError):
    """Raised when NPU/AnythingLLM connection fails.

    Example:
        >>> raise NPUConnectionError(
        ...     "Failed to connect to AnythingLLM server",
        ...     backend_name="anythingllm",
        ...     context={"url": "http://localhost:3001", "timeout": 30}
        ... )
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, "npu", context, original_error)


class AnythingLLMError(BackendError):
    """Raised for AnythingLLM-specific errors.

    Example:
        >>> raise AnythingLLMError(
        ...     "Workspace not found",
        ...     backend_name="anythingllm",
        ...     context={"workspace_slug": "main"}
        ... )
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, "anythingllm", context, original_error)


class QNNError(BackendError):
    """Raised for QNN (Qualcomm Neural Network) errors.

    Example:
        >>> raise QNNError(
        ...     "Failed to load QNN model",
        ...     backend_name="qnn",
        ...     context={"model_path": "models/Phi-3.5-Mini.qnn"}
        ... )
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, "qnn", context, original_error)


class CPUFallbackError(BackendError):
    """Raised when CPU fallback mechanism fails.

    Example:
        >>> raise CPUFallbackError(
        ...     "GGUF model file not found",
        ...     backend_name="cpu",
        ...     context={"model_path": "models/Phi-3-mini.gguf"}
        ... )
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, "cpu_fallback", context, original_error)


class BackendUnavailableError(BackendError):
    """Raised when all backends are exhausted.

    This is a critical error indicating complete system failure.

    Example:
        >>> raise BackendUnavailableError(
        ...     "All inference backends failed",
        ...     backend_name="all",
        ...     context={"attempted": ["anythingllm", "qnn", "cpu"]}
        ... )
    """
    pass


class FallbackTriggered(SelfAIException):
    """Informational exception indicating automatic backend fallback.

    This is not necessarily an error, but a state transition that may need
    logging or monitoring.

    Attributes:
        from_backend: The backend that failed.
        to_backend: The backend being switched to.

    Example:
        >>> raise FallbackTriggered(
        ...     "Falling back from AnythingLLM to QNN",
        ...     context={"from": "anythingllm", "to": "qnn", "reason": "timeout"}
        ... )
    """

    def __init__(
        self,
        from_backend: str,
        to_backend: str,
        reason: Optional[str] = None,
    ):
        """Initialize fallback notification.

        Args:
            from_backend: Backend that failed.
            to_backend: Backend being switched to.
            reason: Optional reason for fallback.
        """
        self.from_backend = from_backend
        self.to_backend = to_backend
        self.reason = reason

        context = {"from": from_backend, "to": to_backend}
        if reason:
            context["reason"] = reason

        message = f"Fallback triggered: {from_backend} → {to_backend}"
        super().__init__(message, context)


# =============================================================================
# INFERENCE ERRORS
# =============================================================================


class InferenceError(SelfAIException):
    """Base class for model inference errors."""
    pass


class ModelLoadError(InferenceError):
    """Raised when model loading fails.

    Example:
        >>> raise ModelLoadError(
        ...     "Failed to load GGUF model",
        ...     context={"model_path": "models/Phi-3.gguf", "n_ctx": 4096}
        ... )
    """
    pass


class TokenizationError(InferenceError):
    """Raised when input tokenization fails.

    Example:
        >>> raise TokenizationError(
        ...     "Input exceeds maximum token limit",
        ...     context={"input_tokens": 8192, "max_tokens": 4096}
        ... )
    """
    pass


class GenerationError(InferenceError):
    """Raised during text generation.

    Example:
        >>> raise GenerationError(
        ...     "Generation timed out",
        ...     context={"timeout": 60, "tokens_generated": 512}
        ... )
    """
    pass


class StreamingError(InferenceError):
    """Raised when streaming response fails.

    Example:
        >>> raise StreamingError(
        ...     "SSE stream interrupted",
        ...     context={"tokens_received": 42, "expected": 512}
        ... )
    """
    pass


# =============================================================================
# PLANNING ERRORS
# =============================================================================


class PlanningError(SelfAIException):
    """Base class for planning system errors."""
    pass


class PlanValidationError(PlanningError):
    """Raised when plan JSON fails validation.

    Example:
        >>> raise PlanValidationError(
        ...     "Missing required field 'subtasks'",
        ...     context={"plan_id": "plan_20250119_120000"}
        ... )
    """
    pass


class PlanExecutionError(PlanningError):
    """Raised during plan execution failures.

    Example:
        >>> raise PlanExecutionError(
        ...     "Subtask execution failed",
        ...     context={"subtask_id": "S3", "agent": "code_helfer"}
        ... )
    """
    pass


class SubtaskError(PlanningError):
    """Raised when individual subtask execution fails.

    Example:
        >>> raise SubtaskError(
        ...     "Subtask timed out",
        ...     context={"subtask_id": "S1", "timeout": 120}
        ... )
    """
    pass


class MergeError(PlanningError):
    """Raised when result merging fails.

    Example:
        >>> raise MergeError(
        ...     "Failed to synthesize subtask results",
        ...     context={"subtask_count": 5, "merge_strategy": "sequential"}
        ... )
    """
    pass


# =============================================================================
# AGENT ERRORS
# =============================================================================


class AgentError(SelfAIException):
    """Base class for agent-related errors."""
    pass


class AgentNotFoundError(AgentError):
    """Raised when requested agent doesn't exist.

    Example:
        >>> raise AgentNotFoundError(
        ...     "Agent 'data_scientist' not found",
        ...     context={"agent_key": "data_scientist", "available": ["code_helfer", "projektmanager"]}
        ... )
    """
    pass


class AgentLoadError(AgentError):
    """Raised when agent configuration fails to load.

    Example:
        >>> raise AgentLoadError(
        ...     "Missing system_prompt.md file",
        ...     context={"agent_key": "code_helfer", "missing_file": "agents/code_helfer/system_prompt.md"}
        ... )
    """
    pass


class ToolExecutionError(AgentError):
    """Raised when agent tool execution fails.

    Example:
        >>> raise ToolExecutionError(
        ...     "Shell command failed",
        ...     context={"tool": "execute_shell", "command": "npm build", "exit_code": 1}
        ... )
    """
    pass


# =============================================================================
# MEMORY ERRORS
# =============================================================================


class MemoryError(SelfAIException):
    """Base class for memory system errors.

    Note: This shadows the built-in MemoryError, but only within this module's scope.
    """
    pass


class MemoryLoadError(MemoryError):
    """Raised when loading conversation memory fails.

    Example:
        >>> raise MemoryLoadError(
        ...     "Corrupted memory file",
        ...     context={"file_path": "memory/code_helfer/conv_001.txt"}
        ... )
    """
    pass


class MemoryWriteError(MemoryError):
    """Raised when writing to memory fails.

    Example:
        >>> raise MemoryWriteError(
        ...     "Disk space exhausted",
        ...     context={"category": "code_helfer", "required_bytes": 1024000}
        ... )
    """
    pass


class ContextFilterError(MemoryError):
    """Raised when context filtering fails.

    Example:
        >>> raise ContextFilterError(
        ...     "Failed to compute relevance scores",
        ...     context={"query": "debug authentication", "memory_files": 150}
        ... )
    """
    pass


# =============================================================================
# EXCEPTION REGISTRY
# =============================================================================


# Map error codes to exception classes for programmatic error handling
ERROR_REGISTRY: Dict[str, type[SelfAIException]] = {
    # Configuration
    "CONFIG_MISSING": MissingConfigError,
    "CONFIG_INVALID": InvalidConfigError,
    "ENV_MISSING": EnvironmentVariableError,

    # Backends
    "NPU_CONNECTION": NPUConnectionError,
    "ANYTHINGLLM_ERROR": AnythingLLMError,
    "QNN_ERROR": QNNError,
    "CPU_FALLBACK": CPUFallbackError,
    "ALL_BACKENDS_FAILED": BackendUnavailableError,

    # Inference
    "MODEL_LOAD": ModelLoadError,
    "TOKENIZATION": TokenizationError,
    "GENERATION": GenerationError,
    "STREAMING": StreamingError,

    # Planning
    "PLAN_VALIDATION": PlanValidationError,
    "PLAN_EXECUTION": PlanExecutionError,
    "SUBTASK": SubtaskError,
    "MERGE": MergeError,

    # Agents
    "AGENT_NOT_FOUND": AgentNotFoundError,
    "AGENT_LOAD": AgentLoadError,
    "TOOL_EXECUTION": ToolExecutionError,

    # Memory
    "MEMORY_LOAD": MemoryLoadError,
    "MEMORY_WRITE": MemoryWriteError,
    "CONTEXT_FILTER": ContextFilterError,
}


def get_exception_class(error_code: str) -> type[SelfAIException]:
    """Retrieve exception class by error code.

    Args:
        error_code: Standardized error code (e.g., "NPU_CONNECTION").

    Returns:
        The corresponding exception class.

    Raises:
        KeyError: If error code is not registered.

    Example:
        >>> ExceptionClass = get_exception_class("NPU_CONNECTION")
        >>> raise ExceptionClass("Connection failed", context={"url": "localhost:3001"})
    """
    return ERROR_REGISTRY[error_code]
