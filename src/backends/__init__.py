"""Async backend providers for LLM inference.

This package provides high-performance async inference backends with automatic fallback:

Backends:
    - NPUProvider: Hardware-accelerated inference via AnythingLLM
    - CPUProvider: CPU fallback using llama-cpp-python
    - BackendManager: Intelligent fallback orchestration

Key Features:
    - Async/await for non-blocking I/O
    - Automatic fallback on errors
    - Streaming support
    - Health checks
    - Connection pooling

Usage:
    >>> from src.backends import BackendManager, NPUProvider, CPUProvider
    >>> from src.backends.base import Message, GenerationConfig
    >>> from src.core import load_settings
    >>>
    >>> # Simple usage with BackendManager
    >>> settings = load_settings()
    >>> manager = await BackendManager.create(settings)
    >>>
    >>> messages = [Message(role="user", content="Hello")]
    >>> response = await manager.generate_response(messages)
    >>> print(response.content)
    >>>
    >>> await manager.close()
    >>>
    >>> # Direct provider usage
    >>> async with NPUProvider(settings.npu_provider) as provider:
    ...     response = await provider.generate_response(messages)
    ...     print(response.content)
"""

# Base classes and data models
from src.backends.base import (
    LLMProvider,
    Message,
    GenerationConfig,
    GenerationResponse,
    messages_to_dicts,
    with_timeout,
)

# Concrete providers
from src.backends.npu_provider import NPUProvider, create_npu_provider
from src.backends.cpu_provider import CPUProvider

# Backend manager
from src.backends.manager import BackendManager


__all__ = [
    # Base classes
    "LLMProvider",
    "Message",
    "GenerationConfig",
    "GenerationResponse",
    "messages_to_dicts",
    "with_timeout",

    # Providers
    "NPUProvider",
    "create_npu_provider",
    "CPUProvider",

    # Manager
    "BackendManager",
]

__version__ = "2.0.0"
__description__ = "Async LLM backend providers with automatic fallback"
