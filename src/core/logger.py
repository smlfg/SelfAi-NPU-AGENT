"""Centralized logging configuration for the AI NPU Agent project.

This module provides a structured, production-ready logging system with:
- JSON-formatted logs for machine parsing
- Human-readable console output with colors
- Configurable log levels per module
- Automatic context injection (timestamp, module, process info)
- Performance-oriented file rotation

The logging system follows the principle of structured logging, making it easy
to parse logs programmatically while maintaining human readability during development.

Usage:
    >>> from src.core.logger import get_logger, setup_logging
    >>>
    >>> # Initialize logging system (do this once at application startup)
    >>> setup_logging(log_level="INFO", log_file="logs/selfai.log")
    >>>
    >>> # Get logger for your module
    >>> logger = get_logger(__name__)
    >>>
    >>> # Use structured logging
    >>> logger.info("Inference started", extra={
    ...     "backend": "anythingllm",
    ...     "model": "Phi-3.5-Mini",
    ...     "tokens": 512
    ... })
    >>>
    >>> # Log exceptions with context
    >>> try:
    ...     connect_to_npu()
    ... except NPUConnectionError as e:
    ...     logger.error("NPU connection failed", exc_info=e, extra={
    ...         "url": "http://localhost:3001",
    ...         "retry_attempt": 3
    ...     })
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import colorama for colored console output (optional)
try:
    from colorama import Fore, Style, init as colorama_init
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================


# Default log format for file output (JSON structured logging)
JSON_LOG_FORMAT = {
    "timestamp": "%(asctime)s",
    "level": "%(levelname)s",
    "logger": "%(name)s",
    "message": "%(message)s",
    "module": "%(module)s",
    "function": "%(funcName)s",
    "line": "%(lineno)d",
    "process": "%(process)d",
    "thread": "%(thread)d",
}

# Human-readable format for console output
CONSOLE_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
)

# ISO 8601 timestamp format
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


# =============================================================================
# CUSTOM LOG FORMATTERS
# =============================================================================


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs as JSON.

    This formatter converts log records to JSON format, making them easy to
    parse by log aggregation systems (e.g., ELK, Splunk, CloudWatch).

    The JSON output includes:
    - Standard fields: timestamp, level, logger, message
    - Contextual fields: module, function, line number
    - Custom fields: Any extra fields passed via the `extra` parameter

    Example Output:
        {
            "timestamp": "2025-01-19 12:30:45",
            "level": "INFO",
            "logger": "selfai.core.agent",
            "message": "Agent initialized",
            "module": "agent",
            "function": "__init__",
            "line": 42,
            "process": 1234,
            "thread": 5678,
            "agent_key": "code_helfer",
            "backend": "anythingllm"
        }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log entry as a string.
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }

        # Include exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include stack trace if present
        if record.stack_info:
            log_data["stack_info"] = self.formatStack(record.stack_info)

        # Merge any extra fields passed via logger.info(..., extra={...})
        # Avoid overwriting standard fields
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in log_data and not key.startswith("_"):
                    # Only include JSON-serializable values
                    try:
                        json.dumps(value)
                        log_data[key] = value
                    except (TypeError, ValueError):
                        log_data[key] = str(value)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """Custom formatter with color-coded log levels for console output.

    This formatter adds ANSI color codes to log messages based on their severity,
    improving visual scanning of logs during development.

    Color Scheme:
        - DEBUG: Cyan
        - INFO: Green
        - WARNING: Yellow
        - ERROR: Red
        - CRITICAL: Red + Bold
    """

    # Color mappings for different log levels
    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN if COLORAMA_AVAILABLE else "",
        logging.INFO: Fore.GREEN if COLORAMA_AVAILABLE else "",
        logging.WARNING: Fore.YELLOW if COLORAMA_AVAILABLE else "",
        logging.ERROR: Fore.RED if COLORAMA_AVAILABLE else "",
        logging.CRITICAL: (Fore.RED + Style.BRIGHT) if COLORAMA_AVAILABLE else "",
    }

    RESET = Style.RESET_ALL if COLORAMA_AVAILABLE else ""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with color codes.

        Args:
            record: The log record to format.

        Returns:
            Colored log message string.
        """
        # Apply color to the entire log message
        color = self.LEVEL_COLORS.get(record.levelno, "")
        formatted = super().format(record)
        return f"{color}{formatted}{self.RESET}"


# =============================================================================
# LOGGER SETUP FUNCTIONS
# =============================================================================


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    json_output: bool = True,
    console_colors: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """Configure the global logging system.

    This function should be called once at application startup to initialize
    the logging system. It configures both console and file handlers with
    appropriate formatters.

    Args:
        log_level: Minimum log level to capture (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to log file. If None, only console logging is enabled.
        json_output: If True, file logs use JSON format. If False, use plain text.
        console_colors: If True, use colored output for console logs.
        max_bytes: Maximum size of log file before rotation (default: 10 MB).
        backup_count: Number of rotated log files to keep (default: 5).

    Example:
        >>> # Development setup: colored console, INFO level
        >>> setup_logging(log_level="INFO", console_colors=True)
        >>>
        >>> # Production setup: JSON logs to file, WARNING level
        >>> setup_logging(
        ...     log_level="WARNING",
        ...     log_file="logs/selfai.log",
        ...     json_output=True,
        ...     console_colors=False
        ... )
    """
    # Initialize colorama for Windows compatibility
    if COLORAMA_AVAILABLE and console_colors:
        colorama_init(autoreset=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if console_colors and COLORAMA_AVAILABLE:
        console_formatter = ColoredConsoleFormatter(
            fmt=CONSOLE_LOG_FORMAT,
            datefmt=TIMESTAMP_FORMAT,
        )
    else:
        console_formatter = logging.Formatter(
            fmt=CONSOLE_LOG_FORMAT,
            datefmt=TIMESTAMP_FORMAT,
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # --- File Handler (if log_file is specified) ---
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use RotatingFileHandler to prevent unbounded log file growth
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if json_output:
            file_formatter = JSONFormatter(datefmt=TIMESTAMP_FORMAT)
        else:
            file_formatter = logging.Formatter(
                fmt=CONSOLE_LOG_FORMAT,
                datefmt=TIMESTAMP_FORMAT,
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Log initial setup confirmation
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging system initialized",
        extra={
            "log_level": log_level,
            "log_file": log_file or "console-only",
            "json_output": json_output,
            "console_colors": console_colors,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.

    This is the primary function for obtaining loggers throughout the codebase.
    Always use `__name__` as the name parameter to automatically namespace logs
    by module.

    Args:
        name: Logger name, typically `__name__` of the calling module.

    Returns:
        Configured logger instance.

    Example:
        >>> # In your module
        >>> logger = get_logger(__name__)
        >>>
        >>> logger.info("Starting inference")
        >>> logger.debug("Token count: 512")
        >>> logger.error("Connection failed", extra={"url": "localhost:3001"})
    """
    return logging.getLogger(name)


def set_log_level(logger_name: str, level: str) -> None:
    """Dynamically change log level for a specific logger.

    This is useful for enabling debug logging for specific modules without
    flooding logs from other parts of the application.

    Args:
        logger_name: Name of the logger to modify (e.g., "selfai.core.agent").
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Example:
        >>> # Enable debug logging for the agent module only
        >>> set_log_level("selfai.core.agent", "DEBUG")
        >>>
        >>> # Reduce logging noise from the memory system
        >>> set_log_level("selfai.core.memory_system", "WARNING")
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.info(f"Log level changed to {level.upper()}", extra={"logger": logger_name})


def log_performance(
    logger: logging.Logger,
    operation: str,
    duration_seconds: float,
    **metadata: Any,
) -> None:
    """Log performance metrics in a structured format.

    This is a convenience function for logging performance-critical operations
    with consistent formatting.

    Args:
        logger: Logger instance to use.
        operation: Name of the operation being measured.
        duration_seconds: Time taken in seconds.
        **metadata: Additional context (e.g., model name, token count).

    Example:
        >>> import time
        >>> logger = get_logger(__name__)
        >>>
        >>> start = time.time()
        >>> result = generate_response(prompt)
        >>> duration = time.time() - start
        >>>
        >>> log_performance(
        ...     logger,
        ...     operation="inference",
        ...     duration_seconds=duration,
        ...     backend="anythingllm",
        ...     tokens=512,
        ...     model="Phi-3.5-Mini"
        ... )
    """
    logger.info(
        f"Performance: {operation} completed in {duration_seconds:.3f}s",
        extra={
            "operation": operation,
            "duration_seconds": round(duration_seconds, 3),
            **metadata,
        },
    )


# =============================================================================
# CONTEXT MANAGERS FOR SCOPED LOGGING
# =============================================================================


class LogContext:
    """Context manager for adding temporary context to logs.

    This allows you to inject additional fields into all log messages within
    a specific scope without manually passing `extra` to every log call.

    Example:
        >>> logger = get_logger(__name__)
        >>>
        >>> with LogContext(logger, agent="code_helfer", request_id="req_123"):
        ...     logger.info("Processing request")  # Includes agent and request_id
        ...     logger.debug("Loaded memory")      # Includes agent and request_id
    """

    def __init__(self, logger: logging.Logger, **context: Any):
        """Initialize the log context.

        Args:
            logger: Logger instance to modify.
            **context: Key-value pairs to inject into log messages.
        """
        self.logger = logger
        self.context = context
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self) -> "LogContext":
        """Enter the context and install custom log record factory."""
        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context and restore original log record factory."""
        logging.setLogRecordFactory(self.old_factory)


# =============================================================================
# MODULE-LEVEL INITIALIZATION
# =============================================================================


# Ensure logging doesn't fail silently
logging.captureWarnings(True)

# Create a default logger for this module
_module_logger = get_logger(__name__)
