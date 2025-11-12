"""
Shared logging utilities for all agents.
"""

import logging
import sys
from typing import Optional


def setup_logging(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging for an agent.

    Args:
        name: Logger name (usually agent_id)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
