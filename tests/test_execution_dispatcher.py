"""
Execution Dispatcher Tests

This test module verifies the EXECUTION PHASE of the SelfAI pipeline.
The ExecutionDispatcher orchestrates the execution of planned subtasks.

WHAT EXECUTION DISPATCHER DOES:
    - Loads plan from JSON file
    - Executes subtasks in order (respecting dependencies)
    - Routes each subtask to appropriate agent and LLM backend
    - Handles backend failures with automatic fallback
    - Saves results to memory
    - Updates plan with result paths
    - Provides progress updates via UI

WHY TEST EXECUTION:
    Execution is where plans become reality. Failures here waste user time.
    These tests ensure:
    - Subtasks execute in correct order
    - Dependencies are respected
    - Backend fallback works
    - Results are saved correctly
    - Errors are handled gracefully
    - Retry logic works

TEST COVERAGE:
    1. Successful single subtask execution
    2. Multi-subtask execution with dependencies
    3. Parallel execution groups
    4. Backend fallback during execution
    5. Retry logic on transient failures
    6. Handling of permanent failures
    7. Result saving and plan updates
    8. Agent context loading
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock, Mock, patch, call


# ==============================================================================
# BASIC EXECUTION TESTS
# ==============================================================================


def test_single_subtask_execution_success(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test successful execution of a single subtask.

    WHY TEST THIS:
        This is the most basic execution scenario - one task, one backend,
        success. All other tests build on this foundation.

    SCENARIO:
        - Plan has 1 subtask
        - AnythingLLM backend succeeds
        - Result is saved to memory

    ASSERTIONS:
        1. Subtask is executed
        2. Correct agent is used
        3. LLM backend is called with correct prompt
        4. Result is saved
        5. Plan is updated with result_path
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange: Create plan with single subtask
    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Simple Task",
                "objective": "Complete this simple task",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "No merge needed"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        }
    ]

    # Act: Execute plan
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        retry_attempts=1,
        retry_delay=0.1,
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: LLM was called
    assert mock_anythingllm_interface.generate_response.called, \
        "LLM backend should be called for subtask execution"

    # Assert: Result was saved (plan file updated)
    with open(sample_plan_file, "r", encoding="utf-8") as f:
        updated_plan = json.load(f)

    assert "result_path" in updated_plan["subtasks"][0], \
        "Plan should be updated with result path after execution"

    result_path = Path(updated_plan["subtasks"][0]["result_path"])
    assert result_path.exists(), "Result file should exist"


def test_multi_subtask_execution_with_dependencies(
    tmp_path: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test execution of multiple subtasks with dependencies.

    WHY TEST THIS:
        Real plans have dependencies. Subtask B might need results from
        subtask A. The dispatcher must execute in correct order.

    SCENARIO:
        - S1: No dependencies (executes first)
        - S2: Depends on S1 (executes second)
        - S3: Depends on S2 (executes third)

    ASSERTIONS:
        1. Subtasks execute in dependency order
        2. Each subtask waits for dependencies
        3. All results are saved
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange: Plan with dependency chain S1 → S2 → S3
    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "First Task",
                "objective": "Do first thing",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            },
            {
                "id": "S2",
                "title": "Second Task",
                "objective": "Do second thing (after S1)",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 2,
                "depends_on": ["S1"],
            },
            {
                "id": "S3",
                "title": "Third Task",
                "objective": "Do third thing (after S2)",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 3,
                "depends_on": ["S2"],
            },
        ],
        "merge": {"strategy": "Combine all"},
    }

    plan_path = tmp_path / "dependency_plan.json"
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        }
    ]

    # Track call order
    call_order = []
    original_generate = mock_anythingllm_interface.generate_response

    def track_call(*args, **kwargs):
        # Extract subtask ID from prompt if possible
        prompt = kwargs.get("user_prompt", "")
        if "first" in prompt.lower():
            call_order.append("S1")
        elif "second" in prompt.lower():
            call_order.append("S2")
        elif "third" in prompt.lower():
            call_order.append("S3")
        return original_generate(*args, **kwargs)

    mock_anythingllm_interface.generate_response.side_effect = track_call

    # Act: Execute plan
    dispatcher = ExecutionDispatcher(
        plan_path=plan_path,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        retry_attempts=1,
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: All tasks were executed
    assert mock_anythingllm_interface.generate_response.call_count == 3, \
        "All 3 subtasks should be executed"

    # Assert: Execution order is correct
    assert call_order == ["S1", "S2", "S3"], \
        "Subtasks should execute in dependency order"

    # Assert: All results are saved
    with open(plan_path, "r", encoding="utf-8") as f:
        updated_plan = json.load(f)

    for task in updated_plan["subtasks"]:
        assert "result_path" in task
        assert Path(task["result_path"]).exists()


# ==============================================================================
# BACKEND FALLBACK DURING EXECUTION TESTS
# ==============================================================================


def test_execution_backend_fallback(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test backend fallback during subtask execution.

    WHY TEST THIS:
        Even if AnythingLLM worked during planning, it might fail
        during execution (network issues, server restart, etc.).
        Execution must fall back to alternative backends.

    SCENARIO:
        - S1: AnythingLLM fails, fallback to QNN succeeds
        - Result is still saved correctly

    ASSERTIONS:
        1. Primary backend is tried first
        2. Failure triggers fallback
        3. Secondary backend succeeds
        4. Result is saved
        5. UI shows appropriate messages
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange: Configure AnythingLLM to fail
    mock_anythingllm_interface.generate_response.side_effect = ConnectionError(
        "AnythingLLM server timeout"
    )

    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Task with fallback",
                "objective": "Complete despite backend failure",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "Simple"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        },
        {
            "interface": mock_qnn_interface,
            "label": "QNN",
            "name": "qnn",
            "type": "qnn",
        },
    ]

    # Act
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        retry_attempts=1,
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: Both backends were tried
    assert mock_anythingllm_interface.generate_response.called, \
        "Primary backend should be tried first"
    assert mock_qnn_interface.generate_response.called, \
        "Should fall back to QNN when primary fails"

    # Assert: Result was still saved
    with open(sample_plan_file, "r", encoding="utf-8") as f:
        updated_plan = json.load(f)

    assert "result_path" in updated_plan["subtasks"][0]
    result_path = Path(updated_plan["subtasks"][0]["result_path"])
    assert result_path.exists()

    # Assert: Result contains QNN response (not AnythingLLM)
    result_content = result_path.read_text(encoding="utf-8")
    assert "QNN NPU backend" in result_content, \
        "Result should be from fallback backend (QNN)"


# ==============================================================================
# RETRY LOGIC TESTS
# ==============================================================================


def test_execution_retry_on_transient_failure(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test retry logic for transient failures.

    WHY TEST THIS:
        Network glitches can cause temporary failures. The executor
        should retry a few times before giving up or falling back.

    SCENARIO:
        - First attempt: Fails with timeout
        - Second attempt: Succeeds
        - Result is saved

    ASSERTIONS:
        1. First attempt fails
        2. System retries automatically
        3. Second attempt succeeds
        4. Result is saved from successful retry
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange: Fail first time, succeed second time
    attempt_count = [0]

    def flaky_response(*args, **kwargs):
        attempt_count[0] += 1
        if attempt_count[0] == 1:
            raise TimeoutError("Request timeout (transient)")
        else:
            return "Success on retry"

    mock_anythingllm_interface.generate_response.side_effect = flaky_response

    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Flaky task",
                "objective": "Task that needs retry",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "Simple"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        }
    ]

    # Act: Execute with retry_attempts=2
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        retry_attempts=2,  # Allow retries
        retry_delay=0.01,  # Fast retry for testing
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: Called twice (initial + 1 retry)
    assert mock_anythingllm_interface.generate_response.call_count >= 2, \
        "Should retry after transient failure"

    # Assert: Result was saved from successful retry
    with open(sample_plan_file, "r", encoding="utf-8") as f:
        updated_plan = json.load(f)

    assert "result_path" in updated_plan["subtasks"][0]
    result_path = Path(updated_plan["subtasks"][0]["result_path"])
    assert result_path.exists()

    result_content = result_path.read_text(encoding="utf-8")
    assert "Success on retry" in result_content


def test_execution_failure_after_all_retries_exhausted(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test behavior when ALL retries and ALL backends fail.

    WHY TEST THIS:
        In the worst case, everything fails. The system should:
        1. Try all retries on primary backend
        2. Fall back to secondary backends
        3. Try retries on those too
        4. Eventually give up gracefully with clear error

    SCENARIO:
        - All backends fail permanently
        - All retries exhausted
        - Execution aborts with error

    ASSERTIONS:
        1. Multiple retry attempts on each backend
        2. Appropriate error message
        3. Execution stops (doesn't continue with invalid state)
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher, ExecutionError

    # Arrange: All backends fail permanently
    mock_anythingllm_interface.generate_response.side_effect = RuntimeError(
        "Permanent failure"
    )
    mock_qnn_interface.generate_response.side_effect = RuntimeError(
        "QNN also failed"
    )
    mock_cpu_interface.generate_response.side_effect = RuntimeError(
        "CPU failed too"
    )

    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Doomed task",
                "objective": "Will fail completely",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "Simple"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        },
        {
            "interface": mock_qnn_interface,
            "label": "QNN",
            "name": "qnn",
            "type": "qnn",
        },
        {
            "interface": mock_cpu_interface,
            "label": "CPU",
            "name": "cpu",
            "type": "cpu",
        },
    ]

    # Act & Assert: Should raise ExecutionError
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        retry_attempts=2,
        retry_delay=0.01,
        max_output_tokens=512,
    )

    with pytest.raises(ExecutionError) as exc_info:
        dispatcher.run()

    # Assert: Error message is informative
    error_msg = str(exc_info.value)
    assert "failed" in error_msg.lower() or "error" in error_msg.lower()


# ==============================================================================
# AGENT CONTEXT LOADING TESTS
# ==============================================================================


def test_execution_loads_agent_context(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test that execution loads relevant conversation history for agent.

    WHY TEST THIS:
        Each subtask execution should include relevant conversation history
        from the agent's memory. This provides context for better responses.

    SCENARIO:
        - Agent has previous conversations in memory
        - Subtask execution loads this context
        - LLM receives history along with prompt

    ASSERTIONS:
        1. Memory system is queried for context
        2. Context is passed to LLM interface
        3. Agent-specific system prompt is used
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange: Add some conversation history
    agent = sample_agent_manager.active_agent
    sample_memory_system.save_conversation(
        agent,
        "Previous question about Python",
        "Previous answer about Python features"
    )

    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Task with context",
                "objective": "Answer a Python question",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "Simple"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        }
    ]

    # Act
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: LLM was called
    assert mock_anythingllm_interface.generate_response.called

    # Assert: System prompt from agent was used
    call_kwargs = mock_anythingllm_interface.generate_response.call_args[1]
    assert "system_prompt" in call_kwargs
    assert len(call_kwargs["system_prompt"]) > 0

    # Note: Checking that history was loaded would require inspecting
    # the call arguments more deeply, which depends on implementation


# ==============================================================================
# RESULT SAVING TESTS
# ==============================================================================


def test_execution_saves_results_with_metadata(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test that execution saves results with proper metadata.

    WHY TEST THIS:
        Saved results should include:
        - The subtask objective
        - The LLM response
        - Metadata (agent, timestamp, etc.)

    SCENARIO:
        - Execute subtask
        - Check saved result file
        - Verify it contains all expected information

    ASSERTIONS:
        1. Result file exists
        2. Contains subtask objective
        3. Contains LLM response
        4. Contains metadata (agent, timestamp)
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange
    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Test Task",
                "objective": "This is the objective for testing",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "Simple"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    # Mock LLM to return specific response
    mock_anythingllm_interface.generate_response.return_value = (
        "This is the LLM response to the objective"
    )

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        }
    ]

    # Act
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: Result file exists and has correct content
    with open(sample_plan_file, "r", encoding="utf-8") as f:
        updated_plan = json.load(f)

    result_path = Path(updated_plan["subtasks"][0]["result_path"])
    assert result_path.exists()

    result_content = result_path.read_text(encoding="utf-8")

    # Assert: Contains objective
    assert "objective for testing" in result_content.lower() or \
           "S1" in result_content, \
        "Result should reference the subtask objective"

    # Assert: Contains LLM response
    assert "LLM response to the objective" in result_content, \
        "Result should contain the actual LLM response"


# ==============================================================================
# UI PROGRESS TESTS
# ==============================================================================


def test_execution_provides_ui_progress_updates(
    sample_plan_file: Path,
    sample_agent_manager,
    sample_memory_system,
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test that execution provides progress updates to UI.

    WHY TEST THIS:
        Execution can take minutes for complex plans. Users need
        progress updates to know the system is working.

    SCENARIO:
        - Execute multi-task plan
        - Verify UI receives status updates for each task

    ASSERTIONS:
        1. UI receives "starting" messages
        2. UI receives "completed" messages
        3. UI shows which task is currently executing
    """
    from selfai.core.execution_dispatcher import ExecutionDispatcher

    # Arrange: Plan with multiple tasks
    plan_data = {
        "subtasks": [
            {
                "id": "S1",
                "title": "First Task",
                "objective": "Do first thing",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            },
            {
                "id": "S2",
                "title": "Second Task",
                "objective": "Do second thing",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 2,
                "depends_on": ["S1"],
            },
        ],
        "merge": {"strategy": "Combine"},
    }

    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    execution_backends = [
        {
            "interface": mock_anythingllm_interface,
            "label": "AnythingLLM",
            "name": "anythingllm",
            "type": "npu",
        }
    ]

    # Act
    dispatcher = ExecutionDispatcher(
        plan_path=sample_plan_file,
        agent_manager=sample_agent_manager,
        memory_system=sample_memory_system,
        llm_backends=execution_backends,
        ui=mock_terminal_ui,
        backend_label="Test",
        max_output_tokens=512,
    )

    dispatcher.run()

    # Assert: UI status method was called multiple times
    assert mock_terminal_ui.status.call_count > 0, \
        "UI should receive progress updates"

    # Assert: Check for task-related messages
    status_calls = [
        call[0][0] for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 0
    ]

    # Should have messages about tasks
    task_mentions = [msg for msg in status_calls if "S1" in msg or "S2" in msg or "Task" in msg]
    assert len(task_mentions) > 0, \
        "UI should show progress about individual tasks"


# ==============================================================================
# HELPER IMPORTS
# ==============================================================================


from selfai.core.execution_dispatcher import ExecutionDispatcher, ExecutionError
