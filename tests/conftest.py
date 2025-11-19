"""
Pytest Configuration and Shared Fixtures

This module provides comprehensive test fixtures for the SelfAI NPU Agent test suite.
We mock hardware dependencies (NPU, external APIs) to enable testing without physical
Snapdragon X Elite hardware or running services.

Design Philosophy:
    - Fixtures should be ISOLATED: No test should affect another
    - Fixtures should be REALISTIC: Mock responses should match real-world behavior
    - Fixtures should be REUSABLE: Complex setup logic should be shared
    - Fixtures should be WELL-DOCUMENTED: Every fixture explains WHY it exists

Key Mocking Strategy:
    1. NPU Provider: Mock hardware acceleration calls (we don't have Snapdragon X Elite)
    2. AnythingLLM API: Mock HTTP calls to avoid dependency on running server
    3. Ollama API: Mock planner/merge LLM calls
    4. File System: Use temporary directories for memory/plans
    5. Configuration: Provide valid configs without requiring .env files
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml


# ==============================================================================
# CONFIGURATION FIXTURES
# ==============================================================================


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """
    Mock environment variables for testing.

    WHY: Tests should not depend on the developer's actual .env file.
    This fixture provides a clean, isolated environment for each test.

    WHAT IT MOCKS:
        - API_KEY: AnythingLLM authentication
        - OLLAMA_CLOUD_API_KEY: Optional cloud Ollama key

    Args:
        monkeypatch: Pytest fixture for safely patching environment

    Returns:
        Dict of environment variables that were set

    Usage:
        def test_something(mock_env_vars):
            # Environment is already configured
            assert os.getenv("API_KEY") == "test-api-key-12345"
    """
    env_vars = {
        "API_KEY": "test-api-key-12345",
        "OLLAMA_CLOUD_API_KEY": "test-ollama-key-67890",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def sample_config_dict() -> Dict[str, Any]:
    """
    Provides a valid configuration dictionary for testing.

    WHY: Many tests need a valid configuration structure. This fixture
    centralizes the "golden" test configuration to avoid duplication.

    WHAT IT PROVIDES:
        - NPU provider config (AnythingLLM)
        - CPU fallback config (GGUF model)
        - System settings (streaming, etc.)
        - Agent configuration
        - Planner configuration with one provider
        - Merge configuration with one provider

    Returns:
        Dict representing a complete, valid SelfAI configuration

    Note:
        This is the DICT form, not the dataclass. Use `sample_app_config`
        fixture if you need the structured AppConfig object.
    """
    return {
        "npu_provider": {
            "api_key": "${API_KEY}",
            "base_url": "http://localhost:3001/api/v1",
            "workspace_slug": "test-workspace",
        },
        "cpu_fallback": {
            "model_path": "Phi-3-mini-4k-instruct.Q4_K_M.gguf",
            "n_ctx": 4096,
            "n_gpu_layers": 0,
        },
        "system": {
            "streaming_enabled": True,
            "stream_timeout": 60.0,
        },
        "agent_config": {
            "default_agent": "code_helfer",
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
                    "headers": {},
                }
            ],
        },
        "merge": {
            "enabled": True,
            "providers": [
                {
                    "name": "merge-ollama",
                    "type": "local_ollama",
                    "base_url": "http://localhost:11434",
                    "model": "gemma3:3b",
                    "timeout": 180.0,
                    "max_tokens": 1536,
                    "headers": {},
                }
            ],
        },
    }


@pytest.fixture
def temp_config_file(
    tmp_path: Path, sample_config_dict: Dict[str, Any], mock_env_vars: Dict[str, str]
) -> Path:
    """
    Creates a temporary config.yaml file for testing.

    WHY: Some tests need to load configuration from an actual file
    (testing the file loading logic itself). This fixture provides
    a real YAML file in a temporary location.

    WHAT IT DOES:
        1. Creates a temporary directory
        2. Writes the sample config as YAML
        3. Returns the path to the config file
        4. Automatically cleaned up after test

    Args:
        tmp_path: Pytest fixture for temporary directories
        sample_config_dict: Our standard test configuration
        mock_env_vars: Ensures environment variables are set

    Returns:
        Path to the temporary config.yaml file

    Usage:
        def test_config_loading(temp_config_file):
            config = load_configuration(str(temp_config_file))
            assert config.npu_provider.base_url == "http://localhost:3001/api/v1"
    """
    config_path = tmp_path / "config.yaml"

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config_dict, f)

    return config_path


@pytest.fixture
def sample_app_config(temp_config_file: Path):
    """
    Provides a fully loaded AppConfig object for testing.

    WHY: Many tests need a structured, validated AppConfig object.
    This fixture provides the complete configuration pipeline:
    env vars → YAML file → validation → AppConfig dataclass.

    WHAT IT PROVIDES:
        A fully initialized AppConfig with all sections populated

    Returns:
        AppConfig object ready for use in tests

    Usage:
        def test_backend_loading(sample_app_config):
            assert sample_app_config.npu_provider.api_key == "test-api-key-12345"
            assert sample_app_config.planner.enabled is True
    """
    from config_loader import load_configuration

    # Change to temp directory so relative paths work
    original_cwd = Path.cwd()
    os.chdir(temp_config_file.parent)

    try:
        config = load_configuration(str(temp_config_file))
        return config
    finally:
        os.chdir(original_cwd)


# ==============================================================================
# BACKEND INTERFACE MOCKS
# ==============================================================================


@pytest.fixture
def mock_anythingllm_interface() -> MagicMock:
    """
    Mock for AnythingLLMInterface (NPU backend).

    WHY: We can't assume tests run on hardware with Snapdragon X Elite NPU,
    nor can we assume an AnythingLLM server is running. This mock simulates
    successful NPU inference without the actual hardware.

    WHAT IT MOCKS:
        - generate_response(): Blocking inference
        - stream_generate_response(): Streaming inference (yields chunks)
        - Health check and initialization

    BEHAVIOR:
        - Returns realistic test responses
        - Simulates streaming with word-by-word chunks
        - Can be configured to raise exceptions for failure testing

    Returns:
        MagicMock configured to behave like AnythingLLMInterface

    Usage:
        def test_npu_inference(mock_anythingllm_interface):
            response = mock_anythingllm_interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[]
            )
            assert "test response" in response.lower()
    """
    mock = MagicMock()

    # Mock blocking inference
    mock.generate_response.return_value = (
        "This is a test response from the mocked AnythingLLM NPU backend. "
        "The Snapdragon X Elite NPU would normally accelerate this inference."
    )

    # Mock streaming inference
    def mock_streaming(*args, **kwargs):
        """Simulate streaming response word-by-word."""
        words = [
            "This ", "is ", "a ", "streaming ", "response ", "from ",
            "the ", "mocked ", "NPU ", "backend."
        ]
        for word in words:
            yield word

    mock.stream_generate_response.side_effect = mock_streaming

    # Mock health check
    mock.healthcheck.return_value = True

    return mock


@pytest.fixture
def mock_qnn_interface() -> MagicMock:
    """
    Mock for NpuLLMInterface (QNN direct NPU access).

    WHY: The QNN backend requires Qualcomm Neural Network SDK and .qnn model
    files optimized for Snapdragon X Elite. We mock this to test the fallback
    logic without requiring the actual QNN runtime.

    WHAT IT MOCKS:
        - generate_response(): QNN model inference
        - Model initialization and loading

    BEHAVIOR:
        - Returns test responses simulating QNN inference
        - Can be configured to fail (for fallback testing)

    Returns:
        MagicMock configured to behave like NpuLLMInterface

    Usage:
        def test_qnn_inference(mock_qnn_interface):
            response = mock_qnn_interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[]
            )
            assert "test response" in response
    """
    mock = MagicMock()

    mock.generate_response.return_value = (
        "This is a test response from the mocked QNN NPU backend. "
        "QNN provides direct NPU access via Qualcomm AI Hub models."
    )

    # QNN doesn't support streaming in current implementation
    mock.stream_generate_response = None

    return mock


@pytest.fixture
def mock_cpu_interface() -> MagicMock:
    """
    Mock for LocalLLMInterface (CPU fallback).

    WHY: CPU inference via llama-cpp-python can be slow and requires GGUF
    model files. This mock simulates CPU inference for fast, deterministic tests.

    WHAT IT MOCKS:
        - generate_response(): CPU-based inference
        - Model loading from GGUF files

    BEHAVIOR:
        - Returns test responses
        - Should ALWAYS succeed (it's the final fallback)
        - Can simulate slow inference for timeout testing

    Returns:
        MagicMock configured to behave like LocalLLMInterface

    Usage:
        def test_cpu_fallback(mock_cpu_interface):
            # CPU backend should always work as last resort
            response = mock_cpu_interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[]
            )
            assert response  # CPU should never fail completely
    """
    mock = MagicMock()

    mock.generate_response.return_value = (
        "This is a test response from the mocked CPU fallback backend. "
        "Running on CPU via llama-cpp-python with GGUF quantized model."
    )

    # CPU backend doesn't typically stream in current implementation
    # but could be added in the future
    mock.stream_generate_response = None

    return mock


@pytest.fixture
def mock_planner_interface() -> MagicMock:
    """
    Mock for PlannerOllamaInterface (task decomposition).

    WHY: The planner calls Ollama to decompose user goals into DPPM
    (Distributed Planning Problem Model) task plans. We mock this to:
        1. Avoid requiring a running Ollama server
        2. Provide deterministic test plans
        3. Test plan validation logic in isolation

    WHAT IT MOCKS:
        - plan(): Main planning method
        - healthcheck(): Ollama availability check

    BEHAVIOR:
        - Returns valid DPPM-formatted plans
        - Can return invalid plans for validation testing
        - Simulates streaming plan generation

    Returns:
        MagicMock configured to behave like PlannerOllamaInterface

    Usage:
        def test_plan_generation(mock_planner_interface):
            plan = mock_planner_interface.plan(
                goal="Create a web scraper",
                context=planner_context
            )
            assert "subtasks" in plan
            assert len(plan["subtasks"]) > 0
    """
    mock = MagicMock()

    # Default valid plan for testing
    def mock_plan_method(goal: str, context, progress_callback=None):
        """Generate a realistic test plan."""
        if progress_callback:
            # Simulate streaming plan generation
            progress_callback("Analyzing ")
            progress_callback("goal... ")
            progress_callback("Generating ")
            progress_callback("subtasks...\n")

        return {
            "subtasks": [
                {
                    "id": "S1",
                    "title": "Analyze Requirements",
                    "objective": f"Understand the goal: {goal}",
                    "agent_key": "code_helfer",
                    "engine": "anythingllm",
                    "parallel_group": 1,
                    "depends_on": [],
                },
                {
                    "id": "S2",
                    "title": "Implement Solution",
                    "objective": f"Implement the solution for: {goal}",
                    "agent_key": "code_helfer",
                    "engine": "anythingllm",
                    "parallel_group": 2,
                    "depends_on": ["S1"],
                },
            ],
            "merge": {
                "strategy": "Combine analysis and implementation into final solution",
                "steps": [
                    {
                        "title": "Synthesis",
                        "description": "Merge all subtask results",
                        "depends_on": ["S2"],
                    }
                ],
            },
        }

    mock.plan.side_effect = mock_plan_method
    mock.healthcheck.return_value = True

    return mock


@pytest.fixture
def mock_merge_interface() -> MagicMock:
    """
    Mock for MergeOllamaInterface (result synthesis).

    WHY: The merge phase calls Ollama to synthesize subtask results into
    a coherent final answer. We mock this to avoid external dependencies
    and provide deterministic merge results.

    WHAT IT MOCKS:
        - chat(): Merge conversation method
        - stream_chat(): Streaming merge (if supported)

    BEHAVIOR:
        - Returns synthesized responses combining multiple inputs
        - Can simulate streaming merge results

    Returns:
        MagicMock configured to behave like MergeOllamaInterface

    Usage:
        def test_merge_phase(mock_merge_interface):
            merged = mock_merge_interface.chat(
                system_prompt="Synthesize results",
                user_prompt="Combine: [result1, result2]"
            )
            assert "synthesis" in merged.lower()
    """
    mock = MagicMock()

    mock.chat.return_value = (
        "This is a synthesized merge result combining all subtask outputs. "
        "The merge phase eliminates redundancy and provides coherent final answer."
    )

    # Mock streaming merge
    def mock_stream_merge(*args, **kwargs):
        words = ["Merged ", "result: ", "synthesis ", "complete."]
        for word in words:
            yield word

    mock.stream_chat.side_effect = mock_stream_merge

    return mock


# ==============================================================================
# AGENT AND MEMORY FIXTURES
# ==============================================================================


@pytest.fixture
def temp_agents_dir(tmp_path: Path) -> Path:
    """
    Creates a temporary agents directory with sample agents.

    WHY: Tests need realistic agent configurations without modifying
    the actual agents/ directory. This fixture creates a temporary
    agent structure that can be safely used and discarded.

    WHAT IT CREATES:
        agents/
        ├── code_helfer/
        │   ├── system_prompt.md
        │   ├── memory_categories.txt
        │   ├── workspace_slug.txt
        │   └── description.txt
        └── projektmanager/
            ├── system_prompt.md
            ├── memory_categories.txt
            ├── workspace_slug.txt
            └── description.txt

    Args:
        tmp_path: Pytest fixture for temporary directories

    Returns:
        Path to temporary agents directory

    Usage:
        def test_agent_loading(temp_agents_dir):
            manager = AgentManager(agents_dir=temp_agents_dir)
            assert len(manager.agents) == 2
    """
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # Create code_helfer agent
    code_helfer_dir = agents_dir / "code_helfer"
    code_helfer_dir.mkdir()

    (code_helfer_dir / "system_prompt.md").write_text(
        "You are a helpful code assistant specialized in Python development.",
        encoding="utf-8"
    )
    (code_helfer_dir / "memory_categories.txt").write_text(
        "code_helfer\ngeneral",
        encoding="utf-8"
    )
    (code_helfer_dir / "workspace_slug.txt").write_text(
        "code-workspace",
        encoding="utf-8"
    )
    (code_helfer_dir / "description.txt").write_text(
        "Python coding specialist",
        encoding="utf-8"
    )

    # Create projektmanager agent
    pm_dir = agents_dir / "projektmanager"
    pm_dir.mkdir()

    (pm_dir / "system_prompt.md").write_text(
        "You are a project manager helping coordinate complex tasks.",
        encoding="utf-8"
    )
    (pm_dir / "memory_categories.txt").write_text(
        "projektmanager\ngeneral",
        encoding="utf-8"
    )
    (pm_dir / "workspace_slug.txt").write_text(
        "pm-workspace",
        encoding="utf-8"
    )
    (pm_dir / "description.txt").write_text(
        "Project coordination specialist",
        encoding="utf-8"
    )

    return agents_dir


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """
    Creates a temporary memory directory for conversation storage.

    WHY: Tests that involve saving/loading conversations need a clean
    memory directory that won't interfere with actual project memory.

    WHAT IT CREATES:
        memory/
        └── plans/  (empty, will be populated by tests)

    Args:
        tmp_path: Pytest fixture for temporary directories

    Returns:
        Path to temporary memory directory

    Usage:
        def test_memory_save(temp_memory_dir):
            memory = MemorySystem(memory_dir=temp_memory_dir)
            memory.save_conversation(agent, "Hello", "Hi there")
            assert len(list(temp_memory_dir.glob("**/*.txt"))) > 0
    """
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    # Create plans subdirectory
    plans_dir = memory_dir / "plans"
    plans_dir.mkdir()

    return memory_dir


@pytest.fixture
def sample_agent_manager(temp_agents_dir: Path):
    """
    Provides a configured AgentManager for testing.

    WHY: Many tests need an AgentManager with loaded agents.
    This fixture provides a ready-to-use manager with test agents.

    Returns:
        AgentManager with test agents loaded

    Usage:
        def test_agent_switching(sample_agent_manager):
            sample_agent_manager.switch_agent("projektmanager")
            assert sample_agent_manager.active_agent.key == "projektmanager"
    """
    from selfai.core.agent_manager import AgentManager

    manager = AgentManager(agents_dir=temp_agents_dir)

    # Set default active agent
    if manager.agents:
        manager.switch_agent("code_helfer")

    return manager


@pytest.fixture
def sample_memory_system(temp_memory_dir: Path):
    """
    Provides a configured MemorySystem for testing.

    WHY: Tests involving conversation history, plan storage, etc.
    need a MemorySystem. This fixture provides one with a clean
    temporary storage location.

    Returns:
        MemorySystem with temporary storage

    Usage:
        def test_conversation_storage(sample_memory_system, sample_agent_manager):
            agent = sample_agent_manager.active_agent
            path = sample_memory_system.save_conversation(
                agent, "Test prompt", "Test response"
            )
            assert path.exists()
    """
    from selfai.core.memory_system import MemorySystem

    return MemorySystem(memory_dir=temp_memory_dir)


# ==============================================================================
# PLAN AND EXECUTION FIXTURES
# ==============================================================================


@pytest.fixture
def sample_plan_dict() -> Dict[str, Any]:
    """
    Provides a valid DPPM plan structure for testing.

    WHY: Many tests need a realistic plan structure to test
    execution, validation, merging, etc. This fixture provides
    the canonical test plan.

    WHAT IT PROVIDES:
        - 3 subtasks with dependencies
        - Parallel execution groups
        - Merge strategy
        - Valid agent keys

    Returns:
        Dict representing a complete DPPM plan

    Usage:
        def test_plan_validation(sample_plan_dict):
            messages = validate_plan_logic(sample_plan_dict)
            assert len(messages) == 0  # Should be valid
    """
    return {
        "subtasks": [
            {
                "id": "S1",
                "title": "Research Phase",
                "objective": "Research the requirements and constraints",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            },
            {
                "id": "S2",
                "title": "Design Phase",
                "objective": "Design the solution architecture",
                "agent_key": "projektmanager",
                "engine": "anythingllm",
                "parallel_group": 2,
                "depends_on": ["S1"],
            },
            {
                "id": "S3",
                "title": "Implementation Phase",
                "objective": "Implement the designed solution",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 3,
                "depends_on": ["S2"],
            },
        ],
        "merge": {
            "strategy": "Synthesize research, design, and implementation into final deliverable",
            "steps": [
                {
                    "title": "Final Synthesis",
                    "description": "Combine all phases into coherent result",
                    "depends_on": ["S3"],
                }
            ],
        },
        "metadata": {
            "goal": "Test project implementation",
            "planner_provider": "local-ollama",
            "planner_model": "gemma3:1b",
        },
    }


@pytest.fixture
def sample_plan_file(tmp_path: Path, sample_plan_dict: Dict[str, Any]) -> Path:
    """
    Creates a temporary plan JSON file for testing.

    WHY: ExecutionDispatcher and other components load plans from
    files. This fixture provides a real plan file for integration tests.

    Args:
        tmp_path: Pytest fixture for temporary directories
        sample_plan_dict: The plan structure to save

    Returns:
        Path to temporary plan file

    Usage:
        def test_execution_dispatcher(sample_plan_file):
            dispatcher = ExecutionDispatcher(plan_path=sample_plan_file, ...)
            dispatcher.run()
    """
    plan_file = tmp_path / "test_plan.json"

    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(sample_plan_dict, f, indent=2)

    return plan_file


# ==============================================================================
# UI AND SYSTEM FIXTURES
# ==============================================================================


@pytest.fixture
def mock_terminal_ui() -> MagicMock:
    """
    Mock for TerminalUI to suppress output during tests.

    WHY: Tests should not spam the console with UI output. This mock
    captures all UI calls so tests can verify UI interactions without
    polluting test output.

    WHAT IT MOCKS:
        - status(): Status messages
        - stream_prefix(): Stream labels
        - streaming_chunk(): Streaming output
        - typing_animation(): Animated output
        - banner(), clear(), etc.: Visual elements
        - confirm(): User confirmations

    BEHAVIOR:
        - All methods are no-ops by default
        - confirm() returns True by default
        - Can be inspected to verify UI calls were made

    Returns:
        MagicMock configured to behave like TerminalUI

    Usage:
        def test_plan_execution(mock_terminal_ui):
            # UI won't spam console during test
            ui.status("Starting execution", "info")
            assert mock_terminal_ui.status.called
    """
    mock = MagicMock()

    # Most UI methods should be no-ops in tests
    mock.banner.return_value = None
    mock.clear.return_value = None
    mock.status.return_value = None
    mock.stream_prefix.return_value = None
    mock.streaming_chunk.return_value = None
    mock.typing_animation.return_value = None
    mock.start_spinner.return_value = None
    mock.stop_spinner.return_value = None

    # Confirmation methods should return True by default
    mock.confirm.return_value = True
    mock.confirm_plan.return_value = True
    mock.confirm_execution.return_value = True

    # choose_option should return first option by default
    mock.choose_option.return_value = 0

    return mock


@pytest.fixture
def mock_psutil() -> MagicMock:
    """
    Mock for psutil system monitoring.

    WHY: Tests shouldn't depend on actual system resources, and
    psutil might not be available in all test environments.

    Returns:
        MagicMock simulating psutil with realistic system stats

    Usage:
        def test_system_monitor(mock_psutil):
            mem = mock_psutil.virtual_memory()
            assert mem.total > 0
    """
    mock = MagicMock()

    # Mock memory info
    mock.virtual_memory.return_value = MagicMock(
        total=17179869184,  # 16 GB
        available=8589934592,  # 8 GB
        percent=50.0,
        used=8589934592,  # 8 GB
    )

    # Mock swap info
    mock.swap_memory.return_value = MagicMock(
        total=4294967296,  # 4 GB
        used=1073741824,  # 1 GB
        percent=25.0,
    )

    # Mock CPU info
    mock.cpu_percent.return_value = 35.5

    return mock


# ==============================================================================
# HELPER FIXTURES
# ==============================================================================


@pytest.fixture
def captured_output():
    """
    Captures stdout/stderr for tests that check console output.

    WHY: Some tests need to verify that specific messages are printed.
    This fixture makes it easy to capture and inspect output.

    Yields:
        Context manager that captures output

    Usage:
        def test_error_message(captured_output):
            with captured_output() as (out, err):
                print("Error occurred")
            assert "Error" in out.getvalue()
    """
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO

    def _capture():
        out = StringIO()
        err = StringIO()
        return redirect_stdout(out), redirect_stderr(err), out, err

    yield _capture


# ==============================================================================
# PARAMETRIZED FIXTURES FOR BACKEND TESTING
# ==============================================================================


@pytest.fixture(params=["anythingllm", "qnn", "cpu"])
def backend_type(request) -> str:
    """
    Parametrized fixture for testing all backend types.

    WHY: Some tests should run against ALL backend types to ensure
    consistent behavior. This fixture automatically runs the test
    three times, once for each backend.

    Returns:
        Backend type identifier: "anythingllm", "qnn", or "cpu"

    Usage:
        def test_all_backends(backend_type):
            # This test runs 3 times, once per backend
            assert backend_type in ["anythingllm", "qnn", "cpu"]
    """
    return request.param


@pytest.fixture
def backend_interface(
    backend_type: str,
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
) -> MagicMock:
    """
    Provides the appropriate mock interface based on backend_type.

    WHY: When testing with backend_type parametrization, we need
    to return the corresponding mock interface.

    Args:
        backend_type: Which backend to use
        mock_anythingllm_interface: NPU backend mock
        mock_qnn_interface: QNN backend mock
        mock_cpu_interface: CPU backend mock

    Returns:
        The appropriate mock interface for the backend type
    """
    backends = {
        "anythingllm": mock_anythingllm_interface,
        "qnn": mock_qnn_interface,
        "cpu": mock_cpu_interface,
    }
    return backends[backend_type]
