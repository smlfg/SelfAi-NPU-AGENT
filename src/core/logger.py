"""Core Logging Module - Centralized Logger Management.

This module provides a standardized logging interface across the application,
with consistent formatting, log levels, and output handling.

Usage:
    from src.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Application started")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

__all__ = ["get_logger", "setup_logging", "LogLevel"]


class LogLevel:
    """Standard log levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# Default format with timestamp, logger name, level, and message
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


_logging_configured = False
_default_level = logging.INFO


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> None:
    """Configure application-wide logging.

    This should be called once at application startup to configure
    the root logger with the desired format and output handlers.

    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (default: timestamp + name + level + message)
        log_file: Optional file path to write logs to

    Example:
        ```python
        from src.core.logger import setup_logging, LogLevel

        # Basic setup
        setup_logging(level=LogLevel.DEBUG)

        # With file output
        setup_logging(
            level=LogLevel.INFO,
            log_file=Path("logs/app.log")
        )

        # Custom format
        setup_logging(
            level=LogLevel.DEBUG,
            format_string="%(levelname)s: %(message)s"
        )
        ```
    """
    global _logging_configured, _default_level

    if _logging_configured:
        return

    _default_level = level

    # Create formatter
    formatter = logging.Formatter(
        fmt=format_string or DEFAULT_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _logging_configured = True


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a logger instance for the specified module.

    This function returns a configured logger instance with the
    module name as the logger name. If logging hasn't been set up,
    it will configure it with default settings.

    Args:
        name: Logger name (typically __name__ of the calling module)
        level: Optional override for this logger's level

    Returns:
        logging.Logger: Configured logger instance

    Example:
        ```python
        from src.core.logger import get_logger

        logger = get_logger(__name__)

        logger.debug("Detailed debugging information")
        logger.info("General information message")
        logger.warning("Warning message")
        logger.error("Error occurred")
        logger.critical("Critical error!")

        # Log with context
        try:
            result = risky_operation()
        except Exception as exc:
            logger.error(f"Operation failed: {exc}", exc_info=True)
        ```
    """
    global _logging_configured

    # Ensure logging is configured
    if not _logging_configured:
        setup_logging(level=_default_level)

    # Get logger
    logger = logging.getLogger(name)

    # Override level if specified
    if level is not None:
        logger.setLevel(level)

    return logger


class LoggerAdapter(logging.LoggerAdapter):
    """Adapter to add contextual information to log messages.

    Example:
        ```python
        from src.core.logger import get_logger, LoggerAdapter

        base_logger = get_logger(__name__)
        logger = LoggerAdapter(base_logger, {"user_id": "12345"})

        logger.info("User action")
        # Output: ... - INFO - [user_id=12345] User action
        ```
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Add context to log message."""
        # Build context string
        context_parts = [f"{k}={v}" for k, v in self.extra.items()]
        context_str = ", ".join(context_parts)

        # Prepend context to message
        if context_str:
            msg = f"[{context_str}] {msg}"

        return msg, kwargs


def get_logger_with_context(
    name: str,
    context: dict[str, any],
    level: Optional[int] = None,
) -> LoggerAdapter:
    """Get a logger with contextual information.

    Args:
        name: Logger name
        context: Dictionary of context key-value pairs
        level: Optional log level override

    Returns:
        LoggerAdapter: Logger with context

    Example:
        ```python
        logger = get_logger_with_context(
            __name__,
            {"request_id": "abc123", "user": "alice"}
        )

        logger.info("Processing request")
        # Output: ... - INFO - [request_id=abc123, user=alice] Processing request
        ```
    """
    base_logger = get_logger(name, level=level)
    return LoggerAdapter(base_logger, context)


# Convenience function for quick logging without logger instance
def log(
    level: int,
    message: str,
    logger_name: str = "selfai",
    **kwargs,
) -> None:
    """Quick log function without creating logger instance.

    Args:
        level: Log level (use LogLevel constants)
        message: Log message
        logger_name: Logger name (default: "selfai")
        **kwargs: Additional logging kwargs (e.g., exc_info=True)

    Example:
        ```python
        from src.core.logger import log, LogLevel

        log(LogLevel.INFO, "Quick info message")
        log(LogLevel.ERROR, "Error occurred", exc_info=True)
        ```
    """
    logger = get_logger(logger_name)
    logger.log(level, message, **kwargs)
