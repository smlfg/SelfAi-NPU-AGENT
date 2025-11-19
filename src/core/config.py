"""Configuration management system using Pydantic BaseSettings.

This module provides a robust, type-safe configuration system with:
- Automatic validation using Pydantic models
- Environment variable interpolation and loading from .env files
- YAML configuration file support
- Comprehensive validation with helpful error messages
- Immutable configuration objects (by default)
- IDE autocomplete support through typed models

The configuration system follows the principle of "fail fast" - invalid
configuration is detected at startup rather than during runtime.

Architecture:
    The configuration is hierarchical and mirrors the structure in config.yaml:

    Settings (Root)
    ├── NPUProviderSettings
    ├── CPUFallbackSettings
    ├── SystemSettings
    ├── AgentSettings
    ├── PlannerSettings
    │   └── List[ProviderSettings]
    └── MergeSettings
        └── List[ProviderSettings]

Usage:
    >>> from src.core.config import load_settings, Settings
    >>>
    >>> # Load configuration (automatically reads config.yaml and .env)
    >>> settings = load_settings()
    >>>
    >>> # Access typed configuration
    >>> print(settings.npu_provider.base_url)  # IDE autocomplete works!
    >>> print(settings.cpu_fallback.n_ctx)
    >>>
    >>> # Configuration is validated
    >>> assert settings.planner.execution_timeout > 0
    >>>
    >>> # Access planner providers
    >>> for provider in settings.planner.providers:
    ...     print(f"Planner: {provider.name} @ {provider.base_url}")
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ValidationError,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.exceptions import (
    ConfigurationError,
    EnvironmentVariableError,
    InvalidConfigError,
    MissingConfigError,
)
from src.core.logger import get_logger


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================


logger = get_logger(__name__)

# Pattern for environment variable interpolation: ${VAR_NAME}
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

# Default configuration file path
DEFAULT_CONFIG_PATH = "config.yaml"


# =============================================================================
# PYDANTIC MODELS FOR CONFIGURATION
# =============================================================================


class ProviderSettings(BaseModel):
    """Configuration for an LLM provider (planner or merge).

    Attributes:
        name: Unique identifier for this provider.
        type: Provider type (e.g., "local_ollama", "remote_ollama").
        base_url: API endpoint URL.
        model: Model name to use.
        timeout: Request timeout in seconds.
        max_tokens: Maximum tokens to generate.
        headers: Optional HTTP headers (e.g., for authentication).

    Example:
        >>> provider = ProviderSettings(
        ...     name="local-ollama",
        ...     type="local_ollama",
        ...     base_url="http://localhost:11434",
        ...     model="gemma3:1b",
        ...     timeout=180.0,
        ...     max_tokens=768,
        ...     headers={}
        ... )
    """

    name: str = Field(
        ...,
        description="Unique provider name",
        min_length=1,
    )
    type: str = Field(
        ...,
        description="Provider type (local_ollama, remote_ollama, etc.)",
        min_length=1,
    )
    base_url: str = Field(
        ...,
        description="Provider API endpoint URL",
        min_length=1,
    )
    model: str = Field(
        ...,
        description="Model identifier",
        min_length=1,
    )
    timeout: float = Field(
        default=180.0,
        description="Request timeout in seconds",
        gt=0,
        le=600,
    )
    max_tokens: int = Field(
        default=768,
        description="Maximum tokens to generate",
        gt=0,
        le=32768,
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional HTTP headers",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate that base_url is a valid URL format.

        Args:
            v: The base_url value to validate.

        Returns:
            The validated URL.

        Raises:
            ValueError: If URL format is invalid.
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"base_url must start with http:// or https://, got: {v}")
        return v

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class NPUProviderSettings(BaseModel):
    """Configuration for NPU backend (AnythingLLM).

    Attributes:
        api_key: API key for authentication.
        base_url: AnythingLLM server base URL.
        workspace_slug: Workspace identifier in AnythingLLM.

    Example:
        >>> npu = NPUProviderSettings(
        ...     api_key="sk-abc123",
        ...     base_url="http://localhost:3001/api/v1",
        ...     workspace_slug="main"
        ... )
    """

    api_key: str = Field(
        ...,
        description="AnythingLLM API key",
        min_length=1,
    )
    base_url: str = Field(
        ...,
        description="AnythingLLM API base URL",
        min_length=1,
    )
    workspace_slug: str = Field(
        ...,
        description="AnythingLLM workspace identifier",
        min_length=1,
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key is not a placeholder.

        Args:
            v: The api_key value to validate.

        Returns:
            The validated API key.

        Raises:
            ValueError: If API key is a placeholder value.
        """
        placeholder_values = ["your-api-key", "your-anythingllm-api-key", ""]
        if v.lower() in placeholder_values:
            raise ValueError(
                "API_KEY must be set to a real value (not a placeholder). "
                "Set it in your .env file or as an environment variable."
            )
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base_url format.

        Args:
            v: The base_url value to validate.

        Returns:
            The validated URL.

        Raises:
            ValueError: If URL format is invalid.
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"base_url must start with http:// or https://, got: {v}")
        return v

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class CPUFallbackSettings(BaseModel):
    """Configuration for CPU fallback backend (llama-cpp-python).

    Attributes:
        model_path: Path to GGUF model file (relative to models/ directory).
        n_ctx: Context window size in tokens.
        n_gpu_layers: Number of layers to offload to GPU (0 for pure CPU).

    Example:
        >>> cpu = CPUFallbackSettings(
        ...     model_path="models/Phi-3-mini-4k-instruct.Q4_K_M.gguf",
        ...     n_ctx=4096,
        ...     n_gpu_layers=0
        ... )
    """

    model_path: str = Field(
        ...,
        description="Path to GGUF model file",
        min_length=1,
    )
    n_ctx: int = Field(
        default=4096,
        description="Context window size in tokens",
        gt=0,
        le=32768,
    )
    n_gpu_layers: int = Field(
        default=0,
        description="GPU layers to offload (0 for CPU-only)",
        ge=0,
    )

    @field_validator("model_path")
    @classmethod
    def validate_model_path(cls, v: str) -> str:
        """Ensure model_path points to models/ directory.

        Args:
            v: The model_path value to validate.

        Returns:
            Full path to model file.
        """
        # If path doesn't start with "models/", prepend it
        if not v.startswith("models/"):
            v = f"models/{v}"
        return v

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class SystemSettings(BaseModel):
    """General system configuration.

    Attributes:
        streaming_enabled: Enable streaming responses (word-by-word output).
        stream_timeout: Optional timeout for streaming requests in seconds.

    Example:
        >>> system = SystemSettings(
        ...     streaming_enabled=True,
        ...     stream_timeout=60.0
        ... )
    """

    streaming_enabled: bool = Field(
        default=True,
        description="Enable streaming output",
    )
    stream_timeout: Optional[float] = Field(
        default=None,
        description="Streaming timeout in seconds (None = no timeout)",
        gt=0,
    )

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class AgentSettings(BaseModel):
    """Agent configuration.

    Attributes:
        default_agent: Default agent to load on startup.

    Example:
        >>> agent = AgentSettings(default_agent="code_helfer")
    """

    default_agent: str = Field(
        default="code_helfer",
        description="Default agent to load on startup",
        min_length=1,
    )

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class PlannerSettings(BaseModel):
    """Planner system configuration.

    Attributes:
        enabled: Whether planning phase is enabled.
        execution_timeout: Timeout for each subtask execution in seconds.
        providers: List of available planner providers.

    Example:
        >>> planner = PlannerSettings(
        ...     enabled=True,
        ...     execution_timeout=120.0,
        ...     providers=[
        ...         ProviderSettings(
        ...             name="local-ollama",
        ...             type="local_ollama",
        ...             base_url="http://localhost:11434",
        ...             model="gemma3:1b",
        ...             timeout=180.0,
        ...             max_tokens=768,
        ...         )
        ...     ]
        ... )
    """

    enabled: bool = Field(
        default=False,
        description="Enable planning phase",
    )
    execution_timeout: float = Field(
        default=120.0,
        description="Timeout per subtask execution in seconds",
        gt=0,
        le=600,
    )
    providers: List[ProviderSettings] = Field(
        default_factory=list,
        description="Available planner providers",
    )

    @model_validator(mode="after")
    def validate_providers_if_enabled(self) -> "PlannerSettings":
        """Ensure at least one provider is configured if planner is enabled.

        Returns:
            Validated settings.

        Raises:
            ValueError: If enabled but no providers configured.
        """
        if self.enabled and not self.providers:
            raise ValueError(
                "Planner is enabled but no providers are configured. "
                "Add at least one provider in config.yaml under 'planner.providers'."
            )
        return self

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class MergeSettings(BaseModel):
    """Merge system configuration.

    Attributes:
        enabled: Whether merge phase is enabled.
        providers: List of available merge providers.

    Example:
        >>> merge = MergeSettings(
        ...     enabled=True,
        ...     providers=[
        ...         ProviderSettings(
        ...             name="merge-ollama",
        ...             type="local_ollama",
        ...             base_url="http://localhost:11434",
        ...             model="gemma3:3b",
        ...             timeout=180.0,
        ...             max_tokens=1536,
        ...         )
        ...     ]
        ... )
    """

    enabled: bool = Field(
        default=False,
        description="Enable merge phase",
    )
    providers: List[ProviderSettings] = Field(
        default_factory=list,
        description="Available merge providers",
    )

    @model_validator(mode="after")
    def validate_providers_if_enabled(self) -> "MergeSettings":
        """Ensure at least one provider is configured if merge is enabled.

        Returns:
            Validated settings.

        Raises:
            ValueError: If enabled but no providers configured.
        """
        if self.enabled and not self.providers:
            raise ValueError(
                "Merge is enabled but no providers are configured. "
                "Add at least one provider in config.yaml under 'merge.providers'."
            )
        return self

    model_config = SettingsConfigDict(frozen=False, extra="forbid")


class Settings(BaseSettings):
    """Root configuration settings.

    This is the main configuration object that aggregates all subsystem settings.
    It supports loading from YAML files and environment variables.

    Attributes:
        npu_provider: NPU/AnythingLLM backend configuration.
        cpu_fallback: CPU fallback backend configuration.
        system: General system settings.
        agent_config: Agent management settings.
        planner: Planning phase settings.
        merge: Merge phase settings.

    Example:
        >>> settings = Settings(
        ...     npu_provider=NPUProviderSettings(...),
        ...     cpu_fallback=CPUFallbackSettings(...),
        ...     system=SystemSettings(...),
        ...     agent_config=AgentSettings(...),
        ...     planner=PlannerSettings(...),
        ...     merge=MergeSettings(...),
        ... )
        >>>
        >>> # Access nested settings with full type safety
        >>> print(settings.npu_provider.api_key)
        >>> print(settings.planner.providers[0].model)
    """

    npu_provider: NPUProviderSettings = Field(
        ...,
        description="NPU provider configuration",
    )
    cpu_fallback: CPUFallbackSettings = Field(
        ...,
        description="CPU fallback configuration",
    )
    system: SystemSettings = Field(
        default_factory=SystemSettings,
        description="System configuration",
    )
    agent_config: AgentSettings = Field(
        default_factory=AgentSettings,
        description="Agent configuration",
    )
    planner: PlannerSettings = Field(
        default_factory=PlannerSettings,
        description="Planner configuration",
    )
    merge: MergeSettings = Field(
        default_factory=MergeSettings,
        description="Merge configuration",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",
    )


# =============================================================================
# CONFIGURATION LOADING FUNCTIONS
# =============================================================================


def resolve_env_variables(data: Any) -> Any:
    """Recursively resolve environment variable placeholders in configuration.

    Replaces ${VAR_NAME} placeholders with actual environment variable values.

    Args:
        data: Configuration data (dict, list, str, or other).

    Returns:
        Configuration data with resolved environment variables.

    Example:
        >>> os.environ["API_KEY"] = "secret123"
        >>> config = {"key": "${API_KEY}"}
        >>> resolve_env_variables(config)
        {'key': 'secret123'}
    """
    if isinstance(data, dict):
        return {k: resolve_env_variables(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_env_variables(item) for item in data]
    elif isinstance(data, str):
        def replace_match(match: re.Match) -> str:
            var_name = match.group(1)
            env_value = os.getenv(var_name)
            if env_value is None:
                logger.warning(
                    f"Environment variable ${{{var_name}}} not found, keeping placeholder",
                    extra={"var_name": var_name},
                )
                return match.group(0)
            return env_value
        return ENV_VAR_PATTERN.sub(replace_match, data)
    else:
        return data


def load_yaml_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load and parse YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        MissingConfigError: If config file doesn't exist.
        InvalidConfigError: If YAML parsing fails.

    Example:
        >>> config_data = load_yaml_config("config.yaml")
        >>> print(config_data["npu_provider"]["base_url"])
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise MissingConfigError(
            f"Configuration file '{config_path}' not found. "
            f"Please copy 'config.yaml.template' to '{config_path}' and configure it.",
            context={"config_path": config_path},
        )

    try:
        with config_file.open("r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise InvalidConfigError(
            f"Failed to parse YAML configuration file",
            context={"config_path": config_path},
            original_error=e,
        )

    if not isinstance(raw_config, dict):
        raise InvalidConfigError(
            "Configuration file must contain a YAML mapping (key-value pairs)",
            context={"config_path": config_path, "actual_type": type(raw_config).__name__},
        )

    # Resolve environment variable placeholders
    resolved_config = resolve_env_variables(raw_config)

    return resolved_config


def normalize_legacy_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy configuration format to modern structure.

    This function provides backward compatibility with older config formats
    that may have used different key names or structures.

    Args:
        raw_config: Raw configuration dictionary from YAML.

    Returns:
        Normalized configuration dictionary.

    Example:
        >>> legacy = {"model_server_base_url": "http://localhost:3001"}
        >>> normalized = normalize_legacy_config(legacy)
        >>> print(normalized["npu_provider"]["base_url"])
        'http://localhost:3001'
    """
    # If already in modern format, return as-is
    if "npu_provider" in raw_config:
        return raw_config

    # Handle legacy format (simple chatbot configuration)
    logger.warning("Detected legacy configuration format, normalizing to modern structure")

    base_url = raw_config.get("model_server_base_url") or raw_config.get("base_url")
    workspace_slug = raw_config.get("workspace_slug") or raw_config.get("workspace")
    stream_enabled = raw_config.get("stream")

    normalized = {
        "npu_provider": {
            "base_url": base_url or "http://localhost:3001/api/v1",
            "workspace_slug": workspace_slug or "default",
        },
        "cpu_fallback": raw_config.get("cpu_fallback") or {
            "model_path": "Phi-3-mini-4k-instruct.Q4_K_M.gguf",
            "n_ctx": 4096,
            "n_gpu_layers": 0,
        },
        "system": {
            "streaming_enabled": True if stream_enabled is None else bool(stream_enabled),
            "stream_timeout": raw_config.get("stream_timeout"),
        },
        "agent_config": {
            "default_agent": raw_config.get("default_agent", "code_helfer"),
        },
        "planner": {
            "enabled": bool(raw_config.get("planner_enabled", False)),
            "execution_timeout": raw_config.get("planner_execution_timeout", 120.0),
            "providers": [],
        },
        "merge": {
            "enabled": bool(raw_config.get("merge_enabled", False)),
            "providers": [],
        },
    }

    return normalized


def inject_api_key_from_env(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inject API_KEY from environment into npu_provider configuration.

    Args:
        config_data: Configuration dictionary.

    Returns:
        Configuration with API key injected.

    Raises:
        EnvironmentVariableError: If API_KEY is not set.

    Example:
        >>> os.environ["API_KEY"] = "sk-test123"
        >>> config = {"npu_provider": {"base_url": "http://localhost:3001"}}
        >>> updated = inject_api_key_from_env(config)
        >>> print(updated["npu_provider"]["api_key"])
        'sk-test123'
    """
    # Try to get API key from environment or config file
    env_api_key = os.getenv("API_KEY")
    file_api_key = config_data.get("npu_provider", {}).get("api_key")

    api_key = env_api_key or file_api_key

    if not api_key or api_key.lower() in ["your-api-key", "your-anythingllm-api-key"]:
        raise EnvironmentVariableError(
            "API_KEY environment variable is not set or is a placeholder. "
            "Set it in your .env file (copy from .env.example).",
            context={"var_name": "API_KEY"},
        )

    # Inject API key into config
    if "npu_provider" not in config_data:
        config_data["npu_provider"] = {}

    config_data["npu_provider"]["api_key"] = api_key

    return config_data


def load_settings(config_path: str = DEFAULT_CONFIG_PATH) -> Settings:
    """Load, validate, and return application settings.

    This is the main entry point for configuration loading. It handles:
    1. Loading .env file
    2. Loading YAML configuration
    3. Normalizing legacy formats
    4. Injecting environment variables
    5. Validating with Pydantic models

    Args:
        config_path: Path to the configuration YAML file.

    Returns:
        Validated Settings object with full type safety.

    Raises:
        ConfigurationError: For any configuration-related errors.
        ValidationError: If configuration fails Pydantic validation.

    Example:
        >>> from src.core.config import load_settings
        >>>
        >>> # Load configuration (reads config.yaml and .env)
        >>> settings = load_settings()
        >>>
        >>> # Access configuration with full IDE support
        >>> print(f"NPU URL: {settings.npu_provider.base_url}")
        >>> print(f"Planner enabled: {settings.planner.enabled}")
        >>>
        >>> # Type-safe access to nested settings
        >>> for provider in settings.planner.providers:
        ...     print(f"{provider.name}: {provider.model}")
    """
    logger.info("Loading configuration", extra={"config_path": config_path})

    # Load .env file for secrets
    from dotenv import load_dotenv
    load_dotenv()

    try:
        # Load and parse YAML
        raw_config = load_yaml_config(config_path)

        # Normalize legacy formats
        normalized_config = normalize_legacy_config(raw_config)

        # Inject API key from environment
        final_config = inject_api_key_from_env(normalized_config)

        # Validate and construct Settings object
        settings = Settings(**final_config)

        logger.info(
            "Configuration loaded successfully",
            extra={
                "npu_enabled": bool(settings.npu_provider.api_key),
                "cpu_fallback_model": settings.cpu_fallback.model_path,
                "planner_enabled": settings.planner.enabled,
                "merge_enabled": settings.merge.enabled,
                "default_agent": settings.agent_config.default_agent,
            },
        )

        return settings

    except ValidationError as e:
        # Convert Pydantic validation errors to our custom exceptions
        error_messages = []
        for error in e.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            error_messages.append(f"{field_path}: {error['msg']}")

        raise InvalidConfigError(
            "Configuration validation failed",
            context={
                "config_path": config_path,
                "errors": error_messages,
            },
            original_error=e,
        )

    except (MissingConfigError, InvalidConfigError, EnvironmentVariableError):
        # Re-raise our custom exceptions
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        raise ConfigurationError(
            "Unexpected error during configuration loading",
            context={"config_path": config_path},
            original_error=e,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_config_summary(settings: Settings) -> Dict[str, Any]:
    """Generate a summary of the current configuration.

    Useful for logging or debugging configuration issues.

    Args:
        settings: Loaded settings object.

    Returns:
        Dictionary with configuration summary (excluding secrets).

    Example:
        >>> settings = load_settings()
        >>> summary = get_config_summary(settings)
        >>> print(json.dumps(summary, indent=2))
    """
    return {
        "npu_provider": {
            "base_url": settings.npu_provider.base_url,
            "workspace_slug": settings.npu_provider.workspace_slug,
            "api_key_set": bool(settings.npu_provider.api_key),
        },
        "cpu_fallback": {
            "model_path": settings.cpu_fallback.model_path,
            "n_ctx": settings.cpu_fallback.n_ctx,
            "n_gpu_layers": settings.cpu_fallback.n_gpu_layers,
        },
        "system": {
            "streaming_enabled": settings.system.streaming_enabled,
            "stream_timeout": settings.system.stream_timeout,
        },
        "agent_config": {
            "default_agent": settings.agent_config.default_agent,
        },
        "planner": {
            "enabled": settings.planner.enabled,
            "execution_timeout": settings.planner.execution_timeout,
            "providers_count": len(settings.planner.providers),
            "providers": [
                {"name": p.name, "type": p.type, "model": p.model}
                for p in settings.planner.providers
            ],
        },
        "merge": {
            "enabled": settings.merge.enabled,
            "providers_count": len(settings.merge.providers),
            "providers": [
                {"name": p.name, "type": p.type, "model": p.model}
                for p in settings.merge.providers
            ],
        },
    }


# =============================================================================
# MODULE-LEVEL EXAMPLE/TEST
# =============================================================================


if __name__ == "__main__":
    """Example usage and configuration validation."""
    import sys
    from src.core.logger import setup_logging

    # Setup logging
    setup_logging(log_level="INFO", console_colors=True)

    try:
        # Load configuration
        settings = load_settings()

        # Display configuration summary
        print("\n" + "=" * 60)
        print("CONFIGURATION LOADED SUCCESSFULLY")
        print("=" * 60)

        print("\n--- NPU Provider ---")
        print(f"Base URL: {settings.npu_provider.base_url}")
        print(f"Workspace: {settings.npu_provider.workspace_slug}")
        print(f"API Key Set: {'Yes' if settings.npu_provider.api_key else 'No'}")

        print("\n--- CPU Fallback ---")
        print(f"Model Path: {settings.cpu_fallback.model_path}")
        print(f"Context Size: {settings.cpu_fallback.n_ctx}")
        print(f"GPU Layers: {settings.cpu_fallback.n_gpu_layers}")

        print("\n--- System ---")
        print(f"Streaming Enabled: {settings.system.streaming_enabled}")
        print(f"Stream Timeout: {settings.system.stream_timeout or 'None'}")

        print("\n--- Agent ---")
        print(f"Default Agent: {settings.agent_config.default_agent}")

        print("\n--- Planner ---")
        print(f"Enabled: {settings.planner.enabled}")
        print(f"Execution Timeout: {settings.planner.execution_timeout}s")
        print(f"Providers: {len(settings.planner.providers)}")
        for provider in settings.planner.providers:
            print(f"  - {provider.name} ({provider.type}): {provider.model} @ {provider.base_url}")

        print("\n--- Merge ---")
        print(f"Enabled: {settings.merge.enabled}")
        print(f"Providers: {len(settings.merge.providers)}")
        for provider in settings.merge.providers:
            print(f"  - {provider.name} ({provider.type}): {provider.model} @ {provider.base_url}")

        print("\n" + "=" * 60)
        print("✓ Configuration validation passed!")
        print("=" * 60 + "\n")

    except ConfigurationError as e:
        print("\n" + "=" * 60)
        print("❌ CONFIGURATION ERROR")
        print("=" * 60)
        print(f"\n{e}\n")
        print("=" * 60 + "\n")
        sys.exit(1)
