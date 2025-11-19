"""Core infrastructure modules for the AI NPU Agent project.

This package provides foundational components:
- Configuration management (config.py)
- Logging system (logger.py)
- Exception hierarchy (exceptions.py)

Public API:
    Configuration:
        - load_settings(): Load and validate configuration
        - Settings: Main configuration model
        - get_config_summary(): Get configuration summary

    Logging:
        - setup_logging(): Initialize logging system
        - get_logger(): Get logger for a module
        - set_log_level(): Change log level dynamically
        - log_performance(): Log performance metrics
        - LogContext: Context manager for scoped logging

    Exceptions:
        - SelfAIException: Base exception class
        - ConfigurationError, MissingConfigError, InvalidConfigError
        - BackendError, NPUConnectionError, AnythingLLMError, QNNError
        - InferenceError, ModelLoadError, GenerationError, StreamingError
        - PlanningError, PlanValidationError, PlanExecutionError
        - AgentError, AgentNotFoundError, ToolExecutionError
        - MemoryError, MemoryLoadError, ContextFilterError

Usage:
    >>> # Configuration
    >>> from src.core import load_settings, Settings
    >>> settings = load_settings()
    >>> print(settings.npu_provider.base_url)
    >>>
    >>> # Logging
    >>> from src.core import setup_logging, get_logger
    >>> setup_logging(log_level="INFO", log_file="logs/app.log")
    >>> logger = get_logger(__name__)
    >>> logger.info("Application started")
    >>>
    >>> # Exceptions
    >>> from src.core import NPUConnectionError, FallbackTriggered
    >>> try:
    ...     connect_to_npu()
    ... except NPUConnectionError as e:
    ...     logger.error(f"Connection failed: {e}")
    ...     raise FallbackTriggered("anythingllm", "qnn") from e
"""

# Configuration
from src.core.config import (
    Settings,
    NPUProviderSettings,
    CPUFallbackSettings,
    SystemSettings,
    AgentSettings,
    PlannerSettings,
    MergeSettings,
    ProviderSettings,
    load_settings,
    get_config_summary,
)

# Logging
from src.core.logger import (
    setup_logging,
    get_logger,
    set_log_level,
    log_performance,
    LogContext,
    JSONFormatter,
    ColoredConsoleFormatter,
)

# Exceptions
from src.core.exceptions import (
    # Base
    SelfAIException,

    # Configuration
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    EnvironmentVariableError,

    # Backend
    BackendError,
    NPUConnectionError,
    AnythingLLMError,
    QNNError,
    CPUFallbackError,
    BackendUnavailableError,
    FallbackTriggered,

    # Inference
    InferenceError,
    ModelLoadError,
    TokenizationError,
    GenerationError,
    StreamingError,

    # Planning
    PlanningError,
    PlanValidationError,
    PlanExecutionError,
    SubtaskError,
    MergeError,

    # Agent
    AgentError,
    AgentNotFoundError,
    AgentLoadError,
    ToolExecutionError,

    # Memory (Note: Shadows built-in MemoryError)
    MemoryLoadError,
    MemoryWriteError,
    ContextFilterError,

    # Registry
    ERROR_REGISTRY,
    get_exception_class,
)


__all__ = [
    # Configuration
    "Settings",
    "NPUProviderSettings",
    "CPUFallbackSettings",
    "SystemSettings",
    "AgentSettings",
    "PlannerSettings",
    "MergeSettings",
    "ProviderSettings",
    "load_settings",
    "get_config_summary",

    # Logging
    "setup_logging",
    "get_logger",
    "set_log_level",
    "log_performance",
    "LogContext",
    "JSONFormatter",
    "ColoredConsoleFormatter",

    # Exceptions
    "SelfAIException",
    "ConfigurationError",
    "MissingConfigError",
    "InvalidConfigError",
    "EnvironmentVariableError",
    "BackendError",
    "NPUConnectionError",
    "AnythingLLMError",
    "QNNError",
    "CPUFallbackError",
    "BackendUnavailableError",
    "FallbackTriggered",
    "InferenceError",
    "ModelLoadError",
    "TokenizationError",
    "GenerationError",
    "StreamingError",
    "PlanningError",
    "PlanValidationError",
    "PlanExecutionError",
    "SubtaskError",
    "MergeError",
    "AgentError",
    "AgentNotFoundError",
    "AgentLoadError",
    "ToolExecutionError",
    "MemoryLoadError",
    "MemoryWriteError",
    "ContextFilterError",
    "ERROR_REGISTRY",
    "get_exception_class",
]

# Package metadata
__version__ = "2.0.0"
__author__ = "AI NPU Agent Team"
__description__ = "Core infrastructure for AI NPU Agent with multi-backend inference"
