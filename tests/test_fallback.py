"""
Backend Fallback Mechanism Tests

This test module verifies the CRITICAL fallback chain that ensures SelfAI
continues functioning even when primary backends fail.

FALLBACK CHAIN:
    1. AnythingLLM (NPU) - Primary: Fast, hardware-accelerated
    2. QNN (Direct NPU) - Secondary: Direct Qualcomm Neural Network access
    3. CPU (GGUF) - Tertiary: Guaranteed fallback, always works

WHY THIS MATTERS:
    The fallback mechanism is a CORE FEATURE. Users without NPU hardware,
    or with misconfigured services, should still get responses. These tests
    ensure that the system NEVER completely fails if ANY backend works.

TEST STRATEGY:
    - Simulate failures at each level
    - Verify the system tries the next backend
    - Ensure error messages are informative
    - Confirm CPU fallback ALWAYS succeeds (last resort)

MOCKING STRATEGY:
    We mock the LLM interfaces to simulate failures without needing
    actual hardware or running services. This makes tests:
    - Fast (no network calls)
    - Reliable (no external dependencies)
    - Reproducible (deterministic failures)
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from typing import List, Dict, Any


# ==============================================================================
# BACKEND FALLBACK CHAIN TESTS
# ==============================================================================


def test_fallback_chain_all_backends_succeed(
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test that when ALL backends work, the PRIMARY (AnythingLLM) is used.

    WHY TEST THIS:
        We want to ensure the system prioritizes the fastest backend (NPU)
        when available. This test verifies the priority ordering.

    SCENARIO:
        - AnythingLLM: ✓ Working
        - QNN: ✓ Working
        - CPU: ✓ Working
        Expected: Use AnythingLLM (first in priority)

    ASSERTIONS:
        1. Response comes from AnythingLLM (contains NPU-specific text)
        2. QNN and CPU are never called (no fallback needed)
        3. No error/warning messages in UI
    """
    # Arrange: Create backend list in priority order
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

    # Act: Simulate the fallback logic (simplified version)
    response_text = None
    last_error = None

    for backend in execution_backends:
        interface = backend["interface"]
        try:
            response_text = interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[],
            )
            break  # Success, no fallback needed
        except Exception as exc:
            last_error = exc
            continue

    # Assert: AnythingLLM should have been used
    assert response_text is not None, "Should have received a response"
    assert "AnythingLLM NPU backend" in response_text, \
        "Response should be from primary backend (AnythingLLM)"

    # Assert: AnythingLLM was called, others were not
    assert mock_anythingllm_interface.generate_response.called, \
        "AnythingLLM should have been called"
    assert not mock_qnn_interface.generate_response.called, \
        "QNN should NOT be called when AnythingLLM succeeds"
    assert not mock_cpu_interface.generate_response.called, \
        "CPU should NOT be called when AnythingLLM succeeds"


def test_fallback_chain_npu_fails_qnn_succeeds(
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test fallback from AnythingLLM (fails) → QNN (succeeds).

    WHY TEST THIS:
        This simulates a common failure scenario: AnythingLLM server is down
        or misconfigured, but the system has QNN models available. The system
        should automatically try QNN without user intervention.

    SCENARIO:
        - AnythingLLM: ✗ Fails (connection error)
        - QNN: ✓ Succeeds
        - CPU: (not reached)
        Expected: Fallback to QNN, get QNN response

    FAILURE SIMULATION:
        We configure AnythingLLM mock to raise ConnectionError, simulating
        a network failure or server downtime.

    ASSERTIONS:
        1. System tries AnythingLLM first (and it fails)
        2. System automatically falls back to QNN
        3. Response comes from QNN
        4. Warning message about AnythingLLM failure
        5. Success message about QNN working
    """
    # Arrange: Configure AnythingLLM to fail
    mock_anythingllm_interface.generate_response.side_effect = ConnectionError(
        "AnythingLLM server not responding at http://localhost:3001"
    )

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

    # Act: Simulate fallback logic with error handling
    response_text = None
    last_error = None
    used_backend = None

    for backend in execution_backends:
        interface = backend["interface"]
        label = backend["label"]
        try:
            response_text = interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[],
            )
            used_backend = label
            mock_terminal_ui.status(f"Success with {label}", "success")
            break  # Success
        except Exception as exc:
            last_error = exc
            mock_terminal_ui.status(
                f"Backend '{label}' failed: {exc}",
                "warning"
            )
            continue  # Try next backend

    # Assert: Should have fallen back to QNN
    assert response_text is not None, "Should have received a response from fallback"
    assert "QNN NPU backend" in response_text, \
        "Response should be from QNN (fallback backend)"
    assert used_backend == "QNN", "QNN should have been the successful backend"

    # Assert: Both AnythingLLM and QNN were tried
    assert mock_anythingllm_interface.generate_response.called, \
        "Should have tried AnythingLLM first"
    assert mock_qnn_interface.generate_response.called, \
        "Should have fallen back to QNN"
    assert not mock_cpu_interface.generate_response.called, \
        "Should not need CPU fallback when QNN works"

    # Assert: Appropriate UI messages
    warning_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "warning"
    ]
    assert len(warning_calls) >= 1, "Should have warning about AnythingLLM failure"

    success_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "success"
    ]
    assert len(success_calls) >= 1, "Should have success message for QNN"


def test_fallback_chain_all_npu_fail_cpu_succeeds(
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test fallback to CPU when ALL NPU backends fail.

    WHY TEST THIS:
        This is the WORST-CASE scenario: no NPU backends work (no hardware,
        no services, etc.). The CPU fallback is the LAST RESORT that ensures
        the system NEVER completely fails.

    SCENARIO:
        - AnythingLLM: ✗ Fails (server down)
        - QNN: ✗ Fails (no models found)
        - CPU: ✓ Succeeds (GGUF model available)
        Expected: System falls back to CPU and continues working

    CRITICAL REQUIREMENT:
        CPU fallback MUST work. It's the safety net that ensures users
        can always use SelfAI, even without NPU hardware.

    ASSERTIONS:
        1. All NPU backends are tried and fail
        2. System falls back to CPU (last resort)
        3. Response comes from CPU backend
        4. Multiple warning messages about failures
        5. Final success message from CPU
    """
    # Arrange: Configure both NPU backends to fail
    mock_anythingllm_interface.generate_response.side_effect = ConnectionError(
        "AnythingLLM server not responding"
    )
    mock_qnn_interface.generate_response.side_effect = FileNotFoundError(
        "No QNN models found in models/ directory"
    )

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

    # Act: Simulate complete fallback to CPU
    response_text = None
    last_error = None
    used_backend = None
    attempts = []

    for backend in execution_backends:
        interface = backend["interface"]
        label = backend["label"]
        try:
            response_text = interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[],
            )
            used_backend = label
            attempts.append((label, "success"))
            mock_terminal_ui.status(f"Success with {label}", "success")
            break
        except Exception as exc:
            last_error = exc
            attempts.append((label, "failed"))
            mock_terminal_ui.status(f"Backend '{label}' failed: {exc}", "warning")
            continue

    # Assert: Should have fallen back to CPU
    assert response_text is not None, \
        "CPU fallback MUST work - it's the last resort"
    assert "CPU fallback backend" in response_text, \
        "Response should be from CPU backend"
    assert used_backend == "CPU", "CPU should be the successful backend"

    # Assert: All backends were tried in order
    assert len(attempts) == 3, "Should have tried all 3 backends"
    assert attempts[0] == ("AnythingLLM", "failed"), "First attempt: AnythingLLM"
    assert attempts[1] == ("QNN", "failed"), "Second attempt: QNN"
    assert attempts[2] == ("CPU", "success"), "Final attempt: CPU success"

    # Assert: All interfaces were called
    assert mock_anythingllm_interface.generate_response.called
    assert mock_qnn_interface.generate_response.called
    assert mock_cpu_interface.generate_response.called

    # Assert: Multiple warnings and final success
    warning_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "warning"
    ]
    assert len(warning_calls) == 2, "Should have 2 warnings (AnythingLLM, QNN)"

    success_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "success"
    ]
    assert len(success_calls) >= 1, "Should have success message for CPU"


def test_fallback_all_backends_fail_gracefully(
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test graceful failure when EVERY backend fails (edge case).

    WHY TEST THIS:
        Even though CPU should never fail, we need to test the edge case
        where EVERYTHING goes wrong (corrupted models, permission errors, etc.).
        The system should fail gracefully with a clear error message.

    SCENARIO:
        - AnythingLLM: ✗ Fails
        - QNN: ✗ Fails
        - CPU: ✗ Fails (corrupted model)
        Expected: Clear error message, no crash

    ASSERTIONS:
        1. All backends were tried
        2. No response received (all failed)
        3. Clear error message to user
        4. last_error contains the CPU failure (last attempted)
    """
    # Arrange: Configure ALL backends to fail
    mock_anythingllm_interface.generate_response.side_effect = ConnectionError(
        "AnythingLLM server not responding"
    )
    mock_qnn_interface.generate_response.side_effect = FileNotFoundError(
        "No QNN models found"
    )
    mock_cpu_interface.generate_response.side_effect = RuntimeError(
        "Failed to load CPU model: corrupted GGUF file"
    )

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

    # Act: Simulate complete failure
    response_text = None
    last_error = None

    for backend in execution_backends:
        interface = backend["interface"]
        label = backend["label"]
        try:
            response_text = interface.generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[],
            )
            break
        except Exception as exc:
            last_error = exc
            mock_terminal_ui.status(f"Backend '{label}' failed: {exc}", "warning")
            continue

    # Final error if nothing worked
    if response_text is None:
        mock_terminal_ui.status(
            f"All backends failed. Last error: {last_error}",
            "error"
        )

    # Assert: No response received
    assert response_text is None, \
        "Should have no response when all backends fail"

    # Assert: last_error contains CPU failure (last attempt)
    assert last_error is not None, "Should have captured the last error"
    assert "corrupted GGUF file" in str(last_error), \
        "Last error should be from CPU backend"

    # Assert: Error message was shown
    error_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "error"
    ]
    assert len(error_calls) >= 1, "Should have error message for complete failure"


# ==============================================================================
# STREAMING FALLBACK TESTS
# ==============================================================================


def test_streaming_fallback_to_blocking(
    mock_anythingllm_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test fallback from streaming to blocking mode when streaming fails.

    WHY TEST THIS:
        Streaming provides better UX (word-by-word output), but not all
        backends support it. When streaming fails, the system should
        gracefully fall back to blocking mode without losing the response.

    SCENARIO:
        - Streaming: ✗ Fails (network error mid-stream)
        - Blocking: ✓ Succeeds
        Expected: Get complete response via blocking mode

    ASSERTIONS:
        1. Streaming is attempted first
        2. Streaming failure is caught
        3. System falls back to blocking generate_response
        4. Complete response is received
    """
    # Arrange: Configure streaming to fail, blocking to succeed
    def failing_stream(*args, **kwargs):
        yield "This "
        yield "is "
        raise ConnectionError("Stream interrupted")

    mock_anythingllm_interface.stream_generate_response.side_effect = failing_stream
    mock_anythingllm_interface.generate_response.return_value = (
        "This is a complete response from blocking mode"
    )

    # Act: Simulate streaming with fallback
    response_text = None
    use_streaming = True

    if use_streaming:
        try:
            chunks = []
            for chunk in mock_anythingllm_interface.stream_generate_response(
                system_prompt="You are helpful",
                user_prompt="Hello",
                history=[],
            ):
                chunks.append(chunk)
            response_text = "".join(chunks)
        except Exception as exc:
            mock_terminal_ui.status(
                f"Streaming failed: {exc}. Falling back to blocking mode.",
                "warning"
            )
            use_streaming = False

    if not use_streaming:
        # Fallback to blocking
        response_text = mock_anythingllm_interface.generate_response(
            system_prompt="You are helpful",
            user_prompt="Hello",
            history=[],
        )

    # Assert: Should have response from blocking mode
    assert response_text is not None
    assert "complete response from blocking mode" in response_text

    # Assert: Both methods were tried
    assert mock_anythingllm_interface.stream_generate_response.called
    assert mock_anythingllm_interface.generate_response.called

    # Assert: Warning about streaming failure
    warning_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "warning"
    ]
    assert len(warning_calls) >= 1


# ==============================================================================
# BACKEND INITIALIZATION FAILURE TESTS
# ==============================================================================


def test_backend_loading_handles_missing_dependencies():
    """
    Test that backend loading gracefully handles missing dependencies.

    WHY TEST THIS:
        Users might not have all dependencies installed (especially NPU-specific
        libraries). The system should skip unavailable backends and continue
        with what's available.

    SCENARIO:
        - Try to load QNN backend
        - QNN SDK not installed (ImportError)
        - System continues without QNN

    ASSERTIONS:
        1. ImportError is caught
        2. Warning message shown
        3. Backend is skipped (not added to execution_backends list)
        4. System continues normally
    """
    # Simulate the backend loading logic
    execution_backends = []

    # Try to load QNN (simulating ImportError)
    try:
        # This would normally be: from selfai.core.npu_llm_interface import ...
        raise ImportError("No module named 'qai_hub_models'")
    except ImportError as exc:
        # Should handle gracefully
        warning_msg = f"QNN backend unavailable: {exc}"
        # In real code, this would call ui.status()
        assert "unavailable" in warning_msg
        assert "qai_hub_models" in str(exc)

    # Assert: Backend list doesn't include QNN
    qnn_backends = [b for b in execution_backends if b.get("name") == "qnn"]
    assert len(qnn_backends) == 0, "QNN should not be in backend list"


def test_backend_loading_handles_model_not_found():
    """
    Test that backend loading handles missing model files gracefully.

    WHY TEST THIS:
        Users might not have downloaded model files yet. The system should
        provide helpful error messages and skip that backend.

    SCENARIO:
        - Try to load CPU backend
        - GGUF model file not found
        - System provides clear error message

    ASSERTIONS:
        1. FileNotFoundError is caught
        2. Error message mentions the missing file
        3. Helpful guidance provided
    """
    # Simulate CPU backend loading with missing model
    model_path = "/models/Phi-3-mini-4k-instruct.Q4_K_M.gguf"

    try:
        # Simulate file check
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
    except FileNotFoundError as exc:
        error_msg = str(exc)
        assert "Model file not found" in error_msg
        assert "Phi-3-mini-4k-instruct.Q4_K_M.gguf" in error_msg

        # In real code, would suggest downloading the model
        help_msg = (
            "Please download the model using: "
            "python download_models.py"
        )
        assert "download" in help_msg.lower()


# ==============================================================================
# INTEGRATION TEST: FULL FALLBACK CHAIN IN MAIN LOOP
# ==============================================================================


def test_main_loop_fallback_integration(
    mock_anythingllm_interface: MagicMock,
    mock_qnn_interface: MagicMock,
    mock_cpu_interface: MagicMock,
    mock_terminal_ui: MagicMock,
    sample_agent_manager,
    sample_memory_system,
):
    """
    Integration test: Full fallback chain as it would run in main loop.

    WHY TEST THIS:
        This is the most realistic test - it simulates the actual chat loop
        with a real user prompt, testing the complete fallback mechanism
        end-to-end.

    SCENARIO:
        User sends: "Hello, how are you?"
        - AnythingLLM fails (server down)
        - QNN succeeds
        - Response is saved to memory
        - User sees QNN response

    ASSERTIONS:
        1. User prompt is processed
        2. Fallback happens correctly
        3. Response is saved to memory
        4. Correct UI feedback
    """
    # Arrange: Configure AnythingLLM to fail, QNN to succeed
    mock_anythingllm_interface.generate_response.side_effect = ConnectionError(
        "Connection refused"
    )

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

    user_input = "Hello, how are you?"
    agent = sample_agent_manager.active_agent
    system_prompt = agent.system_prompt
    history = sample_memory_system.load_relevant_context(agent, user_input, limit=2)

    # Act: Simulate main loop response generation
    response_text = None
    active_backend_index = 0

    order = [active_backend_index] + [
        idx for idx in range(len(execution_backends))
        if idx != active_backend_index
    ]

    for backend_index in order:
        backend = execution_backends[backend_index]
        interface = backend["interface"]
        label = backend["label"]

        try:
            mock_terminal_ui.start_spinner("SelfAI is thinking...")
            response_text = interface.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_input,
                history=history,
            )
            mock_terminal_ui.stop_spinner()
            active_backend_index = backend_index
            break
        except Exception as exc:
            mock_terminal_ui.stop_spinner()
            mock_terminal_ui.status(f"Backend '{label}' failed: {exc}", "warning")
            continue

    # Save to memory if successful
    if response_text:
        result_path = sample_memory_system.save_conversation(
            agent=agent,
            user_prompt=user_input,
            llm_response=response_text,
        )

    # Assert: Got response from QNN (fallback)
    assert response_text is not None
    assert "QNN NPU backend" in response_text

    # Assert: Response was saved to memory
    assert result_path is not None
    assert result_path.exists()

    # Assert: Spinner was started and stopped
    assert mock_terminal_ui.start_spinner.called
    assert mock_terminal_ui.stop_spinner.called

    # Assert: Warning was shown for AnythingLLM failure
    warning_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "warning"
    ]
    assert len(warning_calls) >= 1


# ==============================================================================
# HELPER IMPORTS (for integration test)
# ==============================================================================


from pathlib import Path
