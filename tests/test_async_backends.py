"""Pytest-asyncio tests for async backend providers.

This module tests:
1. NPU provider with simulator server
2. CPU fallback provider
3. Backend manager with automatic fallback
4. Streaming responses
5. Health checks
6. Error handling

Usage:
    # Run all tests
    pytest tests/test_async_backends.py -v

    # Run specific test
    pytest tests/test_async_backends.py::test_npu_provider_with_simulator -v

    # Run with coverage
    pytest tests/test_async_backends.py --cov=src.backends -v

Requirements:
    - NPU simulator must be running on localhost:3001
    - Or start it automatically with the simulator_server fixture
"""

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator

import pytest
import httpx
from fastapi.testclient import TestClient

# Import the modules to test
from src.backends.base import (
    GenerationConfig,
    LLMProvider,
    Message,
    GenerationResponse,
)
from src.backends.npu_provider import NPUProvider
from src.backends.cpu_provider import CPUProvider
from src.backends.manager import BackendManager
from src.core.config import NPUProviderSettings, CPUFallbackSettings
from src.core.exceptions import (
    NPUConnectionError,
    BackendUnavailableError,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def simulator_server():
    """Start NPU simulator server for testing.

    Yields:
        Base URL of the simulator server.
    """
    # Import simulator app
    from src.backends.mocks.npu_server import app

    # Create test client
    client = TestClient(app)

    # Verify server is running
    response = client.get("/health")
    assert response.status_code == 200

    yield "http://testserver/api/v1"


@pytest.fixture
def npu_config(simulator_server: str) -> NPUProviderSettings:
    """Create NPU provider configuration for testing.

    Args:
        simulator_server: Base URL of simulator server.

    Returns:
        NPU provider configuration.
    """
    return NPUProviderSettings(
        api_key="test-key",
        base_url=simulator_server,
        workspace_slug="test",
    )


@pytest.fixture
def cpu_config() -> CPUFallbackSettings:
    """Create CPU fallback configuration for testing.

    Returns:
        CPU fallback configuration.
    """
    # Use a small test model if available, otherwise skip CPU tests
    model_path = "models/Phi-3-mini-4k-instruct.Q4_K_M.gguf"

    return CPUFallbackSettings(
        model_path=model_path,
        n_ctx=512,  # Small context for faster tests
        n_gpu_layers=0,
    )


@pytest.fixture
def sample_messages() -> list[Message]:
    """Create sample messages for testing.

    Returns:
        List of test messages.
    """
    return [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello, test!"),
    ]


@pytest.fixture
def generation_config() -> GenerationConfig:
    """Create generation configuration for testing.

    Returns:
        Test generation config.
    """
    return GenerationConfig(
        max_tokens=100,
        temperature=0.7,
        stream=False,
    )


# =============================================================================
# NPU PROVIDER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_npu_provider_initialization(npu_config: NPUProviderSettings):
    """Test NPU provider initialization."""
    provider = NPUProvider(npu_config, timeout=10.0)

    assert provider.name == "npu"
    assert provider.config == npu_config
    assert provider.timeout == 10.0

    await provider.close()


@pytest.mark.asyncio
async def test_npu_provider_with_simulator(
    npu_config: NPUProviderSettings,
    sample_messages: list[Message],
    generation_config: GenerationConfig,
):
    """Test NPU provider with simulator server."""
    async with NPUProvider(npu_config) as provider:
        # Test non-streaming generation
        response = await provider.generate_response(
            messages=sample_messages,
            config=generation_config,
        )

        assert isinstance(response, GenerationResponse)
        assert len(response.content) > 0
        assert response.finish_reason == "stop"
        assert response.metadata["provider"] == "npu"


@pytest.mark.asyncio
async def test_npu_provider_streaming(
    npu_config: NPUProviderSettings,
    sample_messages: list[Message],
):
    """Test NPU provider streaming."""
    config = GenerationConfig(stream=True, max_tokens=50)

    async with NPUProvider(npu_config) as provider:
        chunks = []

        async for chunk in provider.stream_response(
            messages=sample_messages,
            config=config,
        ):
            chunks.append(chunk)

        # Should receive multiple chunks
        assert len(chunks) > 0

        # Concatenated chunks should form a response
        full_response = "".join(chunks)
        assert len(full_response) > 0


@pytest.mark.asyncio
async def test_npu_provider_health_check(npu_config: NPUProviderSettings):
    """Test NPU provider health check."""
    async with NPUProvider(npu_config) as provider:
        is_healthy = await provider.health_check()
        assert is_healthy is True


@pytest.mark.asyncio
async def test_npu_provider_connection_error():
    """Test NPU provider with invalid URL."""
    invalid_config = NPUProviderSettings(
        api_key="test-key",
        base_url="http://invalid-host:9999/api/v1",
        workspace_slug="test",
    )

    async with NPUProvider(invalid_config, timeout=2.0) as provider:
        is_healthy = await provider.health_check()
        assert is_healthy is False

        # Should raise connection error
        with pytest.raises(NPUConnectionError):
            await provider.generate_response(
                messages=[Message(role="user", content="test")]
            )


# =============================================================================
# CPU PROVIDER TESTS
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.skipif(
    not Path("models/Phi-3-mini-4k-instruct.Q4_K_M.gguf").exists(),
    reason="CPU model not available",
)
async def test_cpu_provider_initialization(cpu_config: CPUFallbackSettings):
    """Test CPU provider initialization."""
    provider = await CPUProvider.create(cpu_config)

    assert provider.name == "cpu"
    assert provider.config == cpu_config

    await provider.close()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not Path("models/Phi-3-mini-4k-instruct.Q4_K_M.gguf").exists(),
    reason="CPU model not available",
)
async def test_cpu_provider_generation(
    cpu_config: CPUFallbackSettings,
    sample_messages: list[Message],
    generation_config: GenerationConfig,
):
    """Test CPU provider generation."""
    async with await CPUProvider.create(cpu_config) as provider:
        response = await provider.generate_response(
            messages=sample_messages,
            config=generation_config,
        )

        assert isinstance(response, GenerationResponse)
        assert len(response.content) > 0
        assert response.metadata["provider"] == "cpu"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not Path("models/Phi-3-mini-4k-instruct.Q4_K_M.gguf").exists(),
    reason="CPU model not available",
)
async def test_cpu_provider_streaming(
    cpu_config: CPUFallbackSettings,
    sample_messages: list[Message],
):
    """Test CPU provider streaming."""
    config = GenerationConfig(stream=True, max_tokens=50)

    async with await CPUProvider.create(cpu_config) as provider:
        chunks = []

        async for chunk in provider.stream_response(
            messages=sample_messages,
            config=config,
        ):
            chunks.append(chunk)

        assert len(chunks) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(
    not Path("models/Phi-3-mini-4k-instruct.Q4_K_M.gguf").exists(),
    reason="CPU model not available",
)
async def test_cpu_provider_health_check(cpu_config: CPUFallbackSettings):
    """Test CPU provider health check."""
    async with await CPUProvider.create(cpu_config) as provider:
        is_healthy = await provider.health_check()
        assert is_healthy is True


# =============================================================================
# BACKEND MANAGER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_backend_manager_initialization(
    npu_config: NPUProviderSettings,
    cpu_config: CPUFallbackSettings,
):
    """Test backend manager initialization."""
    # Create providers manually
    npu_provider = NPUProvider(npu_config)

    # Create manager with NPU only
    manager = BackendManager(
        providers=[npu_provider],
        fallback_enabled=True,
    )

    assert len(manager.providers) == 1
    assert manager.current_provider == npu_provider
    assert manager.fallback_enabled is True

    await manager.close()


@pytest.mark.asyncio
async def test_backend_manager_fallback(
    npu_config: NPUProviderSettings,
    cpu_config: CPUFallbackSettings,
    sample_messages: list[Message],
):
    """Test backend manager automatic fallback."""
    # Create invalid NPU config to trigger fallback
    invalid_npu = NPUProviderSettings(
        api_key="test",
        base_url="http://invalid:9999/api/v1",
        workspace_slug="test",
    )

    npu_provider = NPUProvider(invalid_npu, timeout=1.0)

    # Skip if CPU model not available
    if not Path(cpu_config.model_path).exists():
        pytest.skip("CPU model not available for fallback test")

    cpu_provider = await CPUProvider.create(cpu_config)

    # Create manager with both providers
    manager = BackendManager(
        providers=[npu_provider, cpu_provider],
        fallback_enabled=True,
    )

    # Should fall back to CPU when NPU fails
    response = await manager.generate_response(
        messages=sample_messages,
        config=GenerationConfig(max_tokens=50),
    )

    # Should get response from CPU provider
    assert response.metadata["provider"] == "cpu"

    await manager.close()


@pytest.mark.asyncio
async def test_backend_manager_health_check(
    npu_config: NPUProviderSettings,
):
    """Test backend manager health check."""
    npu_provider = NPUProvider(npu_config)
    manager = BackendManager(providers=[npu_provider])

    health = await manager.health_check_all()

    assert "npu" in health
    assert health["npu"] is True

    await manager.close()


@pytest.mark.asyncio
async def test_backend_manager_no_providers():
    """Test backend manager with no providers."""
    manager = BackendManager(providers=[], fallback_enabled=True)

    with pytest.raises(BackendUnavailableError):
        await manager.generate_response(
            messages=[Message(role="user", content="test")]
        )


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_full_stack_with_simulator(
    npu_config: NPUProviderSettings,
    sample_messages: list[Message],
):
    """Test full stack integration with simulator."""
    async with NPUProvider(npu_config) as provider:
        # Test health check
        assert await provider.health_check() is True

        # Test non-streaming
        response = await provider.generate_response(
            messages=sample_messages,
            config=GenerationConfig(max_tokens=100),
        )
        assert len(response.content) > 0

        # Test streaming
        chunks = []
        async for chunk in provider.stream_response(
            messages=sample_messages,
            config=GenerationConfig(max_tokens=50, stream=True),
        ):
            chunks.append(chunk)
        assert len(chunks) > 0


@pytest.mark.asyncio
async def test_concurrent_requests(
    npu_config: NPUProviderSettings,
    sample_messages: list[Message],
):
    """Test concurrent requests to NPU provider."""
    async with NPUProvider(npu_config) as provider:
        # Create multiple concurrent requests
        tasks = [
            provider.generate_response(
                messages=sample_messages,
                config=GenerationConfig(max_tokens=50),
            )
            for _ in range(5)
        ]

        # Wait for all to complete
        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert len(responses) == 5
        assert all(len(r.content) > 0 for r in responses)


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_response_time(
    npu_config: NPUProviderSettings,
    sample_messages: list[Message],
):
    """Test that response time is reasonable."""
    import time

    async with NPUProvider(npu_config) as provider:
        start = time.time()

        await provider.generate_response(
            messages=sample_messages,
            config=GenerationConfig(max_tokens=50),
        )

        duration = time.time() - start

        # Should complete within timeout
        assert duration < 10.0  # 10 seconds max


# =============================================================================
# MAIN (for running tests directly)
# =============================================================================


if __name__ == "__main__":
    # Run pytest programmatically
    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
