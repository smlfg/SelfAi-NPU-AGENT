"""Core Configuration Module - Centralized Settings Management.

This module provides a clean interface to the application configuration,
abstracting away the complexity of config loading and validation.

Usage:
    from src.core.config import load_settings

    settings = load_settings()
    print(settings.npu_provider.base_url)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Import from root config_loader (legacy)
from config_loader import (
    AppConfig,
    NPUConfig,
    CPUConfig,
    SystemConfig,
    AgentConfig,
    PlannerConfig,
    MergeConfig,
    load_configuration as _load_legacy_config,
)

__all__ = [
    "load_settings",
    "AppConfig",
    "NPUConfig",
    "CPUConfig",
    "SystemConfig",
    "AgentConfig",
    "PlannerConfig",
    "MergeConfig",
]


_cached_settings: Optional[AppConfig] = None


def load_settings(
    config_path: Optional[Path] = None,
    force_reload: bool = False,
) -> AppConfig:
    """Load application settings from configuration files.

    This function loads and validates the application configuration,
    with caching to avoid redundant file I/O.

    Args:
        config_path: Optional path to config.yaml (defaults to ./config.yaml)
        force_reload: Force reload even if settings are cached

    Returns:
        AppConfig: Validated application configuration

    Raises:
        FileNotFoundError: If config.yaml or .env not found
        ValueError: If configuration is invalid

    Example:
        ```python
        from src.core.config import load_settings

        # Load default config
        settings = load_settings()

        # Access nested config
        print(settings.npu_provider.base_url)
        print(settings.system.streaming_enabled)

        # Force reload (useful for testing)
        settings = load_settings(force_reload=True)
        ```
    """
    global _cached_settings

    # Return cached settings if available
    if _cached_settings is not None and not force_reload:
        return _cached_settings

    # Determine config path
    if config_path is None:
        # Default to project root config.yaml
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "config.yaml"

    # Ensure config exists
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create config.yaml from config.yaml.template"
        )

    # Load using legacy loader (for now)
    # NOTE: This delegates to the existing config_loader.py
    # In the future, this could be replaced with a pure Pydantic implementation
    try:
        settings = _load_legacy_config()
        _cached_settings = settings
        return settings
    except Exception as exc:
        raise ValueError(f"Failed to load configuration: {exc}") from exc


def get_config_value(key_path: str, default: Optional[any] = None) -> any:
    """Get a specific config value by dot-notation path.

    Args:
        key_path: Dot-notation path (e.g., "npu_provider.base_url")
        default: Default value if key not found

    Returns:
        Config value or default

    Example:
        ```python
        base_url = get_config_value("npu_provider.base_url")
        timeout = get_config_value("system.stream_timeout", 60.0)
        ```
    """
    settings = load_settings()

    parts = key_path.split(".")
    value = settings

    for part in parts:
        if not hasattr(value, part):
            return default
        value = getattr(value, part)

    return value


def reload_settings() -> AppConfig:
    """Force reload settings from disk.

    Returns:
        AppConfig: Freshly loaded configuration
    """
    return load_settings(force_reload=True)
