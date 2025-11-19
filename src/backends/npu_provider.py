"""Async NPU provider implementation using AnythingLLM API.

This module provides async communication with AnythingLLM server for NPU-accelerated
inference on Snapdragon X Elite devices.

The implementation uses httpx for async HTTP operations, enabling:
- Non-blocking network I/O
- Concurrent request handling
- Streaming Server-Sent Events (SSE)
- Automatic connection pooling
- Graceful timeout handling

Architecture:
    NPUProvider communicates with AnythingLLM server via REST API:

    NPUProvider (httpx.AsyncClient)
        ↓
    AnythingLLM API (/v1/workspace/:slug/chat)
        ↓
    NPU Hardware (Snapdragon X Elite)

Usage:
    >>> from src.backends import NPUProvider
    >>> from src.backends.base import Message, GenerationConfig
    >>> from src.core import load_settings
    >>>
    >>> settings = load_settings()
    >>> provider = NPUProvider(settings.npu_provider)
    >>>
    >>> # Health check
    >>> if await provider.health_check():
    ...     # Generate response
    ...     messages = [Message(role="user", content="Hello")]
    ...     response = await provider.generate_response(messages)
    ...     print(response.content)
    >>>
    >>> # Streaming
    >>> async for chunk in provider.stream_response(messages):
    ...     print(chunk, end="", flush=True)
    >>>
    >>> # Cleanup
    >>> await provider.close()
"""

import json
from typing import AsyncIterator, List, Optional

import httpx

from src.backends.base import (
    GenerationConfig,
    GenerationResponse,
    LLMProvider,
    Message,
    messages_to_dicts,
    with_timeout,
)
from src.core import get_logger
from src.core.config import NPUProviderSettings
from src.core.exceptions import AnythingLLMError, NPUConnectionError


logger = get_logger(__name__)


# =============================================================================
# NPU PROVIDER IMPLEMENTATION
# =============================================================================


class NPUProvider(LLMProvider):
    """Async provider for AnythingLLM NPU inference.

    This provider connects to AnythingLLM server running on Snapdragon X Elite
    devices for hardware-accelerated inference.

    Attributes:
        config: NPU provider configuration.
        client: Async HTTP client for API communication.
        timeout: Default timeout for requests in seconds.

    Example:
        >>> from src.core import load_settings
        >>>
        >>> settings = load_settings()
        >>> provider = NPUProvider(settings.npu_provider)
        >>>
        >>> # Use as context manager for automatic cleanup
        >>> async with provider:
        ...     response = await provider.generate_response(messages)
        ...     print(response.content)
    """

    def __init__(
        self,
        config: NPUProviderSettings,
        timeout: float = 60.0,
    ):
        """Initialize NPU provider.

        Args:
            config: NPU provider configuration from settings.
            timeout: Default timeout for requests in seconds.

        Example:
            >>> from src.core import load_settings
            >>> settings = load_settings()
            >>> provider = NPUProvider(
            ...     config=settings.npu_provider,
            ...     timeout=30.0
            ... )
        """
        super().__init__(name="npu")
        self.config = config
        self.timeout = timeout

        # Create async HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

        self._logger.info(
            "NPU provider initialized",
            extra={
                "base_url": config.base_url,
                "workspace": config.workspace_slug,
                "timeout": timeout,
            },
        )

    async def generate_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> GenerationResponse:
        """Generate a complete response using NPU.

        Args:
            messages: List of conversation messages.
            config: Generation configuration (uses defaults if None).

        Returns:
            Complete generation response.

        Raises:
            NPUConnectionError: If connection to AnythingLLM fails.
            AnythingLLMError: If API returns an error.
            InferenceError: If generation fails.

        Example:
            >>> messages = [Message(role="user", content="What is Python?")]
            >>> config = GenerationConfig(max_tokens=256, temperature=0.7)
            >>> response = await provider.generate_response(messages, config)
            >>> print(response.content)
            'Python is a high-level programming language...'
        """
        config = config or GenerationConfig()

        # Build request payload
        payload = {
            "message": messages[-1].content if messages else "",
            "mode": "chat",
        }

        # Add generation parameters
        if config.temperature != 0.7:
            payload["temperature"] = config.temperature
        if config.max_tokens != 512:
            payload["maxTokens"] = config.max_tokens

        endpoint = f"/workspace/{self.config.workspace_slug}/chat"

        self._logger.debug(
            "Sending NPU inference request",
            extra={
                "endpoint": endpoint,
                "message_count": len(messages),
                "max_tokens": config.max_tokens,
            },
        )

        try:
            response = await with_timeout(
                self.client.post(endpoint, json=payload),
                timeout=self.timeout,
                error_message=f"NPU request timed out after {self.timeout}s",
            )

            response.raise_for_status()
            data = response.json()

            # Parse AnythingLLM response format
            if "textResponse" in data:
                content = data["textResponse"]
            elif "message" in data:
                content = data["message"]
            else:
                raise AnythingLLMError(
                    "Unexpected response format from AnythingLLM",
                    context={"response_keys": list(data.keys())},
                )

            self._logger.info(
                "NPU inference completed",
                extra={
                    "response_length": len(content),
                    "workspace": self.config.workspace_slug,
                },
            )

            return GenerationResponse(
                content=content,
                finish_reason="stop",
                usage={"total_tokens": len(content.split())},  # Rough estimate
                metadata={"provider": "npu", "workspace": self.config.workspace_slug},
            )

        except httpx.ConnectError as e:
            raise NPUConnectionError(
                f"Failed to connect to AnythingLLM at {self.config.base_url}",
                context={
                    "base_url": self.config.base_url,
                    "workspace": self.config.workspace_slug,
                },
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            raise AnythingLLMError(
                f"AnythingLLM API error: {e.response.status_code}",
                context={
                    "status_code": e.response.status_code,
                    "response": e.response.text[:500],
                },
                original_error=e,
            ) from e

        except Exception as e:
            raise AnythingLLMError(
                "Unexpected error during NPU inference",
                context={"workspace": self.config.workspace_slug},
                original_error=e,
            ) from e

    async def stream_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[str]:
        """Generate a streaming response using NPU.

        This uses Server-Sent Events (SSE) to stream tokens as they are generated.

        Args:
            messages: List of conversation messages.
            config: Generation configuration (uses defaults if None).

        Yields:
            Text chunks as they are generated.

        Raises:
            NPUConnectionError: If connection to AnythingLLM fails.
            AnythingLLMError: If streaming fails.

        Example:
            >>> messages = [Message(role="user", content="Tell me a story")]
            >>> async for chunk in provider.stream_response(messages):
            ...     print(chunk, end="", flush=True)
            Once upon a time...
        """
        config = config or GenerationConfig(stream=True)

        # Build request payload
        payload = {
            "message": messages[-1].content if messages else "",
            "mode": "chat",
            "stream": True,
        }

        if config.temperature != 0.7:
            payload["temperature"] = config.temperature
        if config.max_tokens != 512:
            payload["maxTokens"] = config.max_tokens

        endpoint = f"/workspace/{self.config.workspace_slug}/stream-chat"

        self._logger.debug(
            "Starting NPU streaming request",
            extra={
                "endpoint": endpoint,
                "message_count": len(messages),
            },
        )

        try:
            async with self.client.stream("POST", endpoint, json=payload) as response:
                response.raise_for_status()

                # Process Server-Sent Events
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue

                    # Parse SSE format: "data: {json}"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        # Check for stream end marker
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)

                            # Extract content chunk
                            if "textResponse" in data:
                                yield data["textResponse"]
                            elif "delta" in data:
                                yield data["delta"]
                            elif "content" in data:
                                yield data["content"]

                        except json.JSONDecodeError:
                            # Might be plain text chunk
                            yield data_str

            self._logger.info("NPU streaming completed")

        except httpx.ConnectError as e:
            raise NPUConnectionError(
                f"Failed to connect to AnythingLLM streaming endpoint",
                context={"base_url": self.config.base_url},
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            raise AnythingLLMError(
                f"AnythingLLM streaming error: {e.response.status_code}",
                context={"status_code": e.response.status_code},
                original_error=e,
            ) from e

    async def health_check(self) -> bool:
        """Check if AnythingLLM server is available.

        Returns:
            True if server is reachable and healthy, False otherwise.

        Example:
            >>> if await provider.health_check():
            ...     print("NPU is ready")
            ... else:
            ...     print("NPU unavailable, will use fallback")
        """
        try:
            # Ping the workspace endpoint with a short timeout
            endpoint = f"/workspace/{self.config.workspace_slug}"
            response = await self.client.get(endpoint, timeout=5.0)
            response.raise_for_status()

            self._logger.debug("NPU health check passed")
            return True

        except Exception as e:
            self._logger.warning(
                "NPU health check failed",
                extra={"error": str(e), "base_url": self.config.base_url},
            )
            return False

    async def close(self) -> None:
        """Close the HTTP client and release resources.

        Example:
            >>> await provider.close()
        """
        await self.client.aclose()
        self._logger.info("NPU provider closed")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


async def create_npu_provider(
    config: NPUProviderSettings,
    timeout: float = 60.0,
) -> NPUProvider:
    """Factory function to create and validate NPU provider.

    Args:
        config: NPU provider configuration.
        timeout: Request timeout in seconds.

    Returns:
        Initialized and validated NPU provider.

    Raises:
        NPUConnectionError: If provider cannot connect to AnythingLLM.

    Example:
        >>> from src.core import load_settings
        >>>
        >>> settings = load_settings()
        >>> provider = await create_npu_provider(settings.npu_provider)
        >>>
        >>> if await provider.health_check():
        ...     response = await provider.generate_response(messages)
    """
    provider = NPUProvider(config, timeout)

    # Verify connectivity
    if not await provider.health_check():
        await provider.close()
        raise NPUConnectionError(
            "Failed to connect to AnythingLLM server during initialization",
            context={
                "base_url": config.base_url,
                "workspace": config.workspace_slug,
            },
        )

    logger.info(
        "NPU provider created and validated",
        extra={
            "base_url": config.base_url,
            "workspace": config.workspace_slug,
        },
    )

    return provider
