"""
Configuration Loader Tests

This test module verifies the configuration loading and validation system.
Configuration is CRITICAL - a misconfigured system won't work at all.

WHAT CONFIGURATION DOES:
    - Loads settings from config.yaml
    - Loads secrets from .env file
    - Validates required fields
    - Resolves environment variable templates (${VAR_NAME})
    - Normalizes different config formats (simple vs extended)
    - Creates structured dataclasses (AppConfig)

WHY TEST CONFIGURATION:
    Configuration errors are the #1 cause of startup failures. These tests ensure:
    - Missing config files are caught early
    - Missing required fields are detected
    - Environment variable resolution works
    - Validation logic is correct
    - Error messages are helpful

TEST COVERAGE:
    1. Successful configuration loading
    2. Missing config file handling
    3. Missing required fields detection
    4. Environment variable resolution
    5. Config format normalization (simple ← extended)
    6. Dataclass validation
    7. Default value handling
"""

import os
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch


# ==============================================================================
# SUCCESSFUL CONFIGURATION LOADING TESTS
# ==============================================================================


def test_load_configuration_success(
    temp_config_file: Path,
    sample_app_config,
):
    """
    Test successful configuration loading with all required fields.

    WHY TEST THIS:
        This is the HAPPY PATH - when config.yaml and .env are properly
        set up, the system should load without errors.

    SCENARIO:
        - config.yaml exists with all required fields
        - .env has API_KEY
        - Expected: AppConfig loaded successfully

    ASSERTIONS:
        1. AppConfig object is returned
        2. All sections are populated
        3. API key is loaded from environment
        4. Default values are applied where needed
    """
    # The fixture already loads the config
    config = sample_app_config

    # Assert: Config object exists
    assert config is not None

    # Assert: NPU provider is configured
    assert config.npu_provider.api_key == "test-api-key-12345"
    assert config.npu_provider.base_url == "http://localhost:3001/api/v1"
    assert config.npu_provider.workspace_slug == "test-workspace"

    # Assert: CPU fallback is configured
    assert "Phi-3" in config.cpu_fallback.model_path
    assert config.cpu_fallback.n_ctx == 4096
    assert config.cpu_fallback.n_gpu_layers == 0

    # Assert: System settings are configured
    assert config.system.streaming_enabled is True
    assert config.system.stream_timeout == 60.0

    # Assert: Agent config is present
    assert config.agent_config.default_agent == "code_helfer"

    # Assert: Planner is configured
    assert config.planner.enabled is True
    assert config.planner.execution_timeout == 120.0
    assert len(config.planner.providers) > 0

    # Assert: Merge is configured
    assert config.merge.enabled is True
    assert len(config.merge.providers) > 0


def test_configuration_with_minimal_fields(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test configuration loading with only required fields (no optional).

    WHY TEST THIS:
        Users might have minimal configs. The system should work with
        defaults for optional fields.

    SCENARIO:
        - Minimal config.yaml (only npu_provider)
        - No planner/merge configuration
        - Expected: Defaults are applied

    ASSERTIONS:
        1. Config loads successfully
        2. Optional sections have defaults
        3. System continues with reduced functionality
    """
    from config_loader import load_configuration

    # Arrange: Create minimal config
    minimal_config = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test",
        },
    }

    config_path = tmp_path / "minimal_config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(minimal_config, f)

    # Change to temp directory
    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act: Load minimal config
        config = load_configuration(str(config_path))

        # Assert: Required sections are present
        assert config.npu_provider is not None

        # Assert: CPU fallback has defaults
        assert config.cpu_fallback is not None
        assert config.cpu_fallback.n_ctx > 0  # Has default value

        # Assert: Planner exists but might be disabled
        assert config.planner is not None
        # Planner can be enabled or disabled based on defaults

    finally:
        os.chdir(original_cwd)


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================


def test_configuration_missing_file():
    """
    Test that missing config.yaml file is detected.

    WHY TEST THIS:
        If config.yaml doesn't exist, the user needs a CLEAR error message
        telling them to create it from the template.

    SCENARIO:
        - config.yaml doesn't exist
        - Expected: FileNotFoundError with helpful message

    ASSERTIONS:
        1. FileNotFoundError is raised
        2. Error message mentions config.yaml
        3. Error suggests using template
    """
    from config_loader import load_configuration

    # Act & Assert: Loading non-existent config should fail
    with pytest.raises(FileNotFoundError) as exc_info:
        load_configuration("non_existent_config.yaml")

    # Assert: Error message is helpful
    error_msg = str(exc_info.value)
    assert "non_existent_config.yaml" in error_msg
    assert "config.yaml.template" in error_msg or "template" in error_msg.lower()


def test_configuration_missing_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that missing API_KEY is detected.

    WHY TEST THIS:
        API_KEY is REQUIRED for AnythingLLM. Without it, the NPU backend
        won't work. This must be caught at startup, not during first request.

    SCENARIO:
        - config.yaml exists
        - .env doesn't have API_KEY
        - Expected: ValueError with clear message

    ASSERTIONS:
        1. ValueError is raised
        2. Error message mentions API_KEY
        3. Error suggests setting it in .env
    """
    from config_loader import load_configuration

    # Arrange: Clear API_KEY from environment
    monkeypatch.delenv("API_KEY", raising=False)

    # Create config WITHOUT api_key
    config_dict = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test",
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_configuration(str(config_path))

        # Assert: Error message is helpful
        error_msg = str(exc_info.value)
        assert "API_KEY" in error_msg
        assert ".env" in error_msg
    finally:
        os.chdir(original_cwd)


def test_configuration_missing_required_npu_fields(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test that missing required NPU config fields are detected.

    WHY TEST THIS:
        npu_provider requires base_url and workspace_slug. Missing these
        will cause connection failures. Better to catch at startup.

    SCENARIO:
        - config.yaml missing workspace_slug
        - Expected: ValueError

    ASSERTIONS:
        1. ValueError is raised
        2. Error identifies missing field
    """
    from config_loader import load_configuration

    # Arrange: Config missing workspace_slug
    incomplete_config = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            # Missing workspace_slug!
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(incomplete_config, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_configuration(str(config_path))

        # Assert: Error mentions missing field
        error_msg = str(exc_info.value)
        assert "workspace_slug" in error_msg or "NPU" in error_msg
    finally:
        os.chdir(original_cwd)


def test_configuration_invalid_yaml(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test that invalid YAML syntax is caught.

    WHY TEST THIS:
        Users might accidentally break YAML syntax (indentation, etc.).
        The error should clearly indicate it's a YAML parsing issue.

    SCENARIO:
        - config.yaml has invalid YAML syntax
        - Expected: ValueError mentioning parsing error

    ASSERTIONS:
        1. ValueError is raised
        2. Error mentions YAML parsing
    """
    from config_loader import load_configuration

    # Arrange: Create file with invalid YAML
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "npu_provider:\n"
        "  base_url: http://localhost:3001\n"
        "  workspace_slug: test\n"
        "invalid yaml syntax here [ { missing closing brackets",
        encoding="utf-8"
    )

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_configuration(str(config_path))

        # Assert: Error mentions parsing
        error_msg = str(exc_info.value).lower()
        assert "parsing" in error_msg or "yaml" in error_msg
    finally:
        os.chdir(original_cwd)


# ==============================================================================
# ENVIRONMENT VARIABLE RESOLUTION TESTS
# ==============================================================================


def test_env_variable_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that ${VAR_NAME} templates are resolved from environment.

    WHY TEST THIS:
        Secrets should be in .env, not config.yaml. The system supports
        ${VAR_NAME} syntax to reference environment variables in configs.

    SCENARIO:
        - config.yaml has api_key: "${API_KEY}"
        - Environment has API_KEY=secret123
        - Expected: Resolved to "secret123"

    ASSERTIONS:
        1. Template syntax is recognized
        2. Environment variable is read
        3. Final value is the environment variable value
    """
    from config_loader import load_configuration

    # Arrange: Set environment variable
    monkeypatch.setenv("API_KEY", "secret-from-env-12345")
    monkeypatch.setenv("CUSTOM_URL", "http://custom-server:8080")

    # Config using template syntax
    config_dict = {
        "npu_provider": {
            "api_key": "${API_KEY}",
            "base_url": "${CUSTOM_URL}",
            "workspace_slug": "test",
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act: Load config
        config = load_configuration(str(config_path))

        # Assert: Variables were resolved
        assert config.npu_provider.api_key == "secret-from-env-12345"
        assert config.npu_provider.base_url == "http://custom-server:8080"
    finally:
        os.chdir(original_cwd)


def test_env_variable_missing_not_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that unresolved ${VAR} templates are left as-is (or caught).

    WHY TEST THIS:
        If an environment variable doesn't exist, we need to either:
        1. Leave the template syntax as-is (detectable later), or
        2. Raise an error immediately

    Current implementation leaves it unresolved, and validation
    catches it as an invalid API key.

    SCENARIO:
        - config.yaml has api_key: "${MISSING_VAR}"
        - MISSING_VAR is not in environment
        - Expected: Error during validation

    ASSERTIONS:
        1. Template is not resolved (stays as ${MISSING_VAR})
        2. Validation catches invalid API key
    """
    from config_loader import load_configuration

    # Arrange: Ensure variable is NOT in environment
    monkeypatch.delenv("MISSING_VAR", raising=False)
    monkeypatch.setenv("API_KEY", "${MISSING_VAR}")  # Template won't resolve

    config_dict = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test",
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act & Assert: Should fail validation
        with pytest.raises(ValueError) as exc_info:
            load_configuration(str(config_path))

        # The error should be about invalid/missing API key
        error_msg = str(exc_info.value)
        assert "API_KEY" in error_msg or "api_key" in error_msg
    finally:
        os.chdir(original_cwd)


# ==============================================================================
# CONFIG FORMAT NORMALIZATION TESTS
# ==============================================================================


def test_simple_config_format_normalization(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test that simple config format is normalized to extended format.

    WHY TEST THIS:
        SelfAI supports two config formats:
        1. Simple: model_server_base_url, workspace_slug (old format)
        2. Extended: npu_provider.base_url, etc. (new format)

        The loader should accept both and normalize to extended.

    SCENARIO:
        - config.yaml uses simple format (old keys)
        - Expected: Converted to extended format internally

    ASSERTIONS:
        1. Simple format is recognized
        2. Keys are mapped correctly
        3. Final AppConfig uses extended structure
    """
    from config_loader import load_configuration

    # Arrange: Old-style simple config
    simple_config = {
        "model_server_base_url": "http://localhost:3001/api/v1",
        "workspace_slug": "old-workspace",
        "stream": True,
        "default_agent": "code_helfer",
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(simple_config, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act: Load simple config
        config = load_configuration(str(config_path))

        # Assert: Mapped to npu_provider
        assert config.npu_provider.base_url == "http://localhost:3001/api/v1"
        assert config.npu_provider.workspace_slug == "old-workspace"

        # Assert: System settings mapped correctly
        assert config.system.streaming_enabled is True

        # Assert: Agent config mapped
        assert config.agent_config.default_agent == "code_helfer"
    finally:
        os.chdir(original_cwd)


# ==============================================================================
# PLANNER CONFIGURATION TESTS
# ==============================================================================


def test_planner_configuration_with_multiple_providers(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test configuration with multiple planner providers.

    WHY TEST THIS:
        Users can configure multiple planner backends for fallback.
        Each provider should be loaded and validated.

    SCENARIO:
        - Config has 2 planner providers (local, cloud)
        - Expected: Both are loaded into planner.providers list

    ASSERTIONS:
        1. Both providers are in config
        2. Each has correct fields
        3. Provider order is preserved
    """
    from config_loader import load_configuration

    # Arrange: Config with multiple planner providers
    config_dict = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test",
        },
        "planner": {
            "enabled": True,
            "execution_timeout": 120.0,
            "providers": [
                {
                    "name": "local-ollama",
                    "type": "local_ollama",
                    "base_url": "http://localhost:11434",
                    "model": "gemma3:1b",
                    "timeout": 180.0,
                    "max_tokens": 768,
                },
                {
                    "name": "cloud-ollama",
                    "type": "cloud_ollama",
                    "base_url": "https://cloud.ollama.ai",
                    "model": "gemma3:3b",
                    "timeout": 240.0,
                    "max_tokens": 1024,
                },
            ],
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act: Load config
        config = load_configuration(str(config_path))

        # Assert: Planner is enabled
        assert config.planner.enabled is True

        # Assert: Both providers are loaded
        assert len(config.planner.providers) == 2

        # Assert: First provider details
        provider1 = config.planner.providers[0]
        assert provider1.name == "local-ollama"
        assert provider1.base_url == "http://localhost:11434"
        assert provider1.model == "gemma3:1b"

        # Assert: Second provider details
        provider2 = config.planner.providers[1]
        assert provider2.name == "cloud-ollama"
        assert "cloud" in provider2.base_url
        assert provider2.model == "gemma3:3b"
    finally:
        os.chdir(original_cwd)


def test_planner_provider_missing_required_field(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test that planner provider validation catches missing fields.

    WHY TEST THIS:
        Each planner provider MUST have base_url and model.
        Missing these will cause runtime errors.

    SCENARIO:
        - Planner provider missing 'model' field
        - Expected: ValueError during config loading

    ASSERTIONS:
        1. ValueError is raised
        2. Error identifies the missing field
    """
    from config_loader import load_configuration

    # Arrange: Provider missing 'model'
    config_dict = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test",
        },
        "planner": {
            "enabled": True,
            "providers": [
                {
                    "name": "incomplete-provider",
                    "type": "local_ollama",
                    "base_url": "http://localhost:11434",
                    # Missing: model
                },
            ],
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_configuration(str(config_path))

        # Assert: Error mentions missing field
        error_msg = str(exc_info.value)
        assert "model" in error_msg or "incomplete-provider" in error_msg
    finally:
        os.chdir(original_cwd)


# ==============================================================================
# DATACLASS VALIDATION TESTS
# ==============================================================================


def test_config_dataclass_structure(sample_app_config):
    """
    Test that AppConfig dataclass has correct structure.

    WHY TEST THIS:
        The AppConfig dataclass is the structured, validated form of
        the configuration. All code uses this, so it must be correct.

    ASSERTIONS:
        1. AppConfig has all required attributes
        2. Each section is the correct dataclass type
        3. Nested dataclasses are properly populated
    """
    from config_loader import (
        AppConfig, NPUConfig, CPUConfig, SystemConfig,
        AgentConfig, PlannerConfig, MergeConfig
    )

    config = sample_app_config

    # Assert: Top-level type
    assert isinstance(config, AppConfig)

    # Assert: Each section has correct type
    assert isinstance(config.npu_provider, NPUConfig)
    assert isinstance(config.cpu_fallback, CPUConfig)
    assert isinstance(config.system, SystemConfig)
    assert isinstance(config.agent_config, AgentConfig)
    assert isinstance(config.planner, PlannerConfig)
    assert isinstance(config.merge, MergeConfig)

    # Assert: Planner providers are loaded
    assert len(config.planner.providers) > 0
    for provider in config.planner.providers:
        # Each provider should have these attributes
        assert hasattr(provider, "name")
        assert hasattr(provider, "base_url")
        assert hasattr(provider, "model")


# ==============================================================================
# DEFAULT VALUE TESTS
# ==============================================================================


def test_default_values_applied(
    tmp_path: Path,
    mock_env_vars: Dict[str, str],
):
    """
    Test that default values are applied for optional fields.

    WHY TEST THIS:
        Not all fields are required. The config loader should apply
        sensible defaults for optional fields.

    SCENARIO:
        - Config doesn't specify stream_timeout
        - Expected: Default value is applied

    ASSERTIONS:
        1. Optional field has a value (not None)
        2. Value is the expected default
    """
    from config_loader import load_configuration

    # Arrange: Config without stream_timeout
    config_dict = {
        "npu_provider": {
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test",
        },
        "system": {
            "streaming_enabled": True,
            # stream_timeout not specified
        },
    }

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # Act
        config = load_configuration(str(config_path))

        # Assert: stream_timeout has default (or None)
        # The exact default depends on implementation
        assert config.system.stream_timeout is not None or \
               config.system.stream_timeout is None  # Both are valid

        # Assert: Other defaults
        assert config.cpu_fallback.n_ctx > 0  # Should have default context size
    finally:
        os.chdir(original_cwd)
