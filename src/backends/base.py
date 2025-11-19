"""Abstract base classes for async LLM backend providers.

This module defines the core abstractions for all LLM inference backends
using async/await patterns for high-performance I/O operations.

The async design enables:
- Concurrent request handling
- Non-blocking I/O for network operations
- Efficient resource utilization
- Graceful timeout handling
- Clean fallback orchestration

Architecture:
    All backend providers implement the LLMProvider protocol:

    LLMProvider (Abstract Base Class)
    ├── NPUProvider (AnythingLLM via async HTTP)
    ├── QNNProvider (Qualcomm Neural Network SDK)
    └── CPUProvider (llama-cpp-python fallback)

Usage:
    >>> from src.backends import LLMProvider, NPUProvider
    >>> from src.core import load_settings
    >>>
    >>> settings = load_settings()
    >>> provider = NPUProvider(settings.npu_provider)
    >>>
    >>> # Async inference
    >>> response = await provider.generate_response(
    ...     messages=[{"role": "user", "content": "Hello"}],
    ...     max_tokens=512
    ... )
    >>>
    >>> # Streaming inference
    >>> async for chunk in provider.stream_response(
    ...     messages=[{"role": "user", "content": "Hello"}],
    ...     max_tokens=512
    ... ):
    ...     print(chunk, end="", flush=True)
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from src.core import get_logger
from src.core.exceptions import InferenceError


logger = get_logger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Message:
    """A single message in a conversation.

    Attributes:
        role: Message role (system, user, assistant).
        content: Message content text.
        name: Optional speaker name.
        metadata: Optional additional metadata.

    Example:
        >>> msg = Message(role="user", content="What is Python?")
        >>> system_msg = Message(role="system", content="You are a helpful assistant.")
    """

    role: str
    content: str
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format.

        Returns:
            Dictionary representation suitable for API calls.
        """
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class GenerationConfig:
    """Configuration for text generation.

    Attributes:
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature (0.0-2.0).
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling threshold.
        stop_sequences: List of sequences that stop generation.
        frequency_penalty: Penalty for token frequency (-2.0 to 2.0).
        presence_penalty: Penalty for token presence (-2.0 to 2.0).
        stream: Whether to stream the response.

    Example:
        >>> config = GenerationConfig(
        ...     max_tokens=512,
        ...     temperature=0.7,
        ...     top_p=0.9,
        ...     stream=True
        ... )
    """

    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 1.0
    top_k: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary format.

        Returns:
            Dictionary representation suitable for API calls.
        """
        result = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": self.stream,
        }
        if self.top_k is not None:
            result["top_k"] = self.top_k
        if self.stop_sequences:
            result["stop"] = self.stop_sequences
        return result


@dataclass
class GenerationResponse:
    """Response from text generation.

    Attributes:
        content: Generated text content.
        finish_reason: Reason generation stopped (stop, length, error).
        usage: Token usage statistics.
        metadata: Optional additional metadata (model name, latency, etc.).

    Example:
        >>> response = GenerationResponse(
        ...     content="Python is a programming language...",
        ...     finish_reason="stop",
        ...     usage={"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60}
        ... )
    """

    content: str
    finish_reason: str = "stop"
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# ABSTRACT BASE CLASS
# =============================================================================


class LLMProvider(ABC):
    """Abstract base class for async LLM inference providers.

    All backend implementations (NPU, QNN, CPU) must implement this interface.
    The async design enables high-performance concurrent operations.

    Key Methods:
        - generate_response(): Main inference method (async)
        - stream_response(): Streaming inference (async iterator)
        - health_check(): Provider availability check (async)
        - close(): Cleanup resources (async)

    Lifecycle:
        1. Initialize provider with configuration
        2. (Optional) Check health with health_check()
        3. Generate responses with generate_response() or stream_response()
        4. Clean up with close() when done

    Example:
        >>> class MyProvider(LLMProvider):
        ...     async def generate_response(self, messages, config):
        ...         # Implementation
        ...         return GenerationResponse(content="response")
        ...
        ...     async def stream_response(self, messages, config):
        ...         # Implementation
        ...         yield "chunk1"
        ...         yield "chunk2"
        ...
        ...     async def health_check(self):
        ...         return True
        ...
        ...     async def close(self):
        ...         # Cleanup
        ...         pass
    """

    def __init__(self, name: str):
        """Initialize the provider.

        Args:
            name: Human-readable provider name (e.g., "npu", "cpu").
        """
        self.name = name
        self._logger = get_logger(f"{__name__}.{name}")

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> GenerationResponse:
        """Generate a complete response (non-streaming).

        This is the main inference method. Implementations should:
        1. Format messages for the backend API
        2. Make async HTTP/RPC call to inference service
        3. Parse response and return GenerationResponse

        Args:
            messages: List of conversation messages.
            config: Generation configuration (uses defaults if None).

        Returns:
            Complete generation response.

        Raises:
            InferenceError: If generation fails.
            asyncio.TimeoutError: If generation times out.

        Example:
            >>> messages = [Message(role="user", content="Hello")]
            >>> response = await provider.generate_response(messages)
            >>> print(response.content)
            'Hi! How can I help you today?'
        """
        pass

    @abstractmethod
    async def stream_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[str]:
        """Generate a streaming response (word-by-word).

        This enables real-time output for better UX. Implementations should:
        1. Format messages for the backend API
        2. Make async streaming HTTP/RPC call
        3. Yield chunks as they arrive

        Args:
            messages: List of conversation messages.
            config: Generation configuration (uses defaults if None).

        Yields:
            Text chunks as they are generated.

        Raises:
            InferenceError: If streaming fails.
            asyncio.TimeoutError: If streaming times out.

        Example:
            >>> messages = [Message(role="user", content="Hello")]
            >>> async for chunk in provider.stream_response(messages):
            ...     print(chunk, end="", flush=True)
            Hi! How can I help you today?
        """
        pass
        # Make this a generator to satisfy the type checker
        yield  # pragma: no cover

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and healthy.

        This should be a lightweight check (e.g., ping endpoint, check model loaded).
        Used by BackendManager to determine if fallback is needed.

        Returns:
            True if provider is healthy, False otherwise.

        Example:
            >>> if await provider.health_check():
            ...     print("Provider is ready")
            ... else:
            ...     print("Provider unavailable, using fallback")
        """
        pass

    async def close(self) -> None:
        """Clean up provider resources.

        Override this to close HTTP sessions, release model memory, etc.
        Called automatically when using the provider as an async context manager.

        Example:
            >>> async with provider:
            ...     response = await provider.generate_response(messages)
            >>> # Resources automatically cleaned up
        """
        self._logger.debug(f"Closing {self.name} provider")

    # Context manager support for automatic resource cleanup
    async def __aenter__(self) -> "LLMProvider":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and clean up resources."""
        await self.close()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def messages_to_dicts(messages: List[Message]) -> List[Dict[str, Any]]:
    """Convert Message objects to dictionaries.

    Args:
        messages: List of Message objects.

    Returns:
        List of message dictionaries.

    Example:
        >>> messages = [Message(role="user", content="Hello")]
        >>> dicts = messages_to_dicts(messages)
        >>> print(dicts)
        [{'role': 'user', 'content': 'Hello'}]
    """
    return [msg.to_dict() for msg in messages]


async def with_timeout(
    coro,
    timeout: float,
    error_message: str = "Operation timed out",
) -> Any:
    """Execute a coroutine with a timeout.

    Args:
        coro: Coroutine to execute.
        timeout: Timeout in seconds.
        error_message: Error message if timeout occurs.

    Returns:
        Result of the coroutine.

    Raises:
        InferenceError: If timeout occurs.

    Example:
        >>> result = await with_timeout(
        ...     provider.generate_response(messages),
        ...     timeout=30.0,
        ...     error_message="Inference timed out after 30s"
        ... )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as e:
        raise InferenceError(error_message, context={"timeout": timeout}) from e
