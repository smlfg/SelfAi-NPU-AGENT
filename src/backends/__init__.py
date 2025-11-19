"""LLM Backend Abstraction Layer.

This package provides a clean, modular abstraction layer for different LLM inference
backends (NPU, QNN, CPU) with automatic fallback support.

The main components are:
    - LLMProvider: Abstract base class defining the provider interface
    - NPUProvider: AnythingLLM-based NPU acceleration provider
    - QNNProvider: Direct QNN/NPU model execution provider
    - CPUProvider: CPU-based fallback using llama-cpp-python
    - BackendManager: Orchestrates providers with automatic fallback logic
    - BackendError: Exception raised when all backends fail

Example Usage:
    >>> from src.backends import BackendManager, NPUProvider, CPUProvider
    >>>
    >>> # Create providers
    >>> npu = NPUProvider(
    ...     api_key="your-api-key",
    ...     base_url="http://localhost:3001/api/v1",
    ...     workspace_slug="main"
    ... )
    >>> cpu = CPUProvider(model_path="models/phi-3-mini.gguf")
    >>>
    >>> # Create manager with automatic fallback: NPU → CPU
    >>> manager = BackendManager(providers=[npu, cpu])
    >>>
    >>> # Generate response (automatically falls back to CPU if NPU fails)
    >>> response = manager.generate_response(
    ...     system_prompt="You are a helpful assistant.",
    ...     user_prompt="What is Python?"
    ... )
    >>> print(response)

For detailed documentation on each component, see the individual module docstrings.
"""

from src.backends.base import LLMProvider
from src.backends.cpu_provider import CPUProvider
from src.backends.manager import BackendError, BackendManager
from src.backends.npu_provider import NPUProvider
from src.backends.qnn_provider import QNNProvider, find_qnn_models

__all__ = [
    # Base class
    "LLMProvider",
    # Provider implementations
    "NPUProvider",
    "QNNProvider",
    "CPUProvider",
    # Manager and utilities
    "BackendManager",
    "BackendError",
    # Helper functions
    "find_qnn_models",
]

__version__ = "1.0.0"
__author__ = "SelfAI NPU Agent Project"
