"""Backend manager with automatic fallback orchestration.

This module provides intelligent backend selection and failover:
1. Try NPU (fastest, hardware-accelerated)
2. If NPU fails → Try QNN (alternative NPU path)
3. If QNN fails → Fall back to CPU (guaranteed to work)

The manager handles async exceptions gracefully and logs all fallback events
for monitoring and debugging.

Architecture:
    BackendManager coordinates multiple providers:

    BackendManager
    ├── NPUProvider (Primary)
    ├── QNNProvider (Secondary, optional)
    └── CPUProvider (Fallback)

    Fallback Chain:
        NPU → QNN → CPU
        (Each step triggered by async exceptions)

Usage:
    >>> from src.backends import BackendManager
    >>> from src.backends.base import Message
    >>> from src.core import load_settings
    >>>
    >>> settings = load_settings()
    >>> manager = await BackendManager.create(settings)
    >>>
    >>> # Automatic fallback if NPU fails
    >>> messages = [Message(role="user", content="Hello")]
    >>> response = await manager.generate_response(messages)
    >>> print(f"Backend used: {response.metadata['provider']}")
    >>>
    >>> await manager.close()
"""

import asyncio
from typing import AsyncIterator, List, Optional

from src.backends.base import (
    GenerationConfig,
    GenerationResponse,
    LLMProvider,
    Message,
)
from src.backends.cpu_provider import CPUProvider
from src.backends.npu_provider import NPUProvider
from src.core import Settings, get_logger
from src.core.exceptions import (
    BackendError,
    BackendUnavailableError,
    FallbackTriggered,
)


logger = get_logger(__name__)


# =============================================================================
# BACKEND MANAGER
# =============================================================================


class BackendManager:
    """Intelligent backend manager with automatic fallback.

    This class manages multiple LLM providers and automatically falls back
    between them when failures occur.

    Attributes:
        providers: List of available providers in priority order.
        current_provider: Currently active provider.
        fallback_enabled: Whether automatic fallback is enabled.

    Example:
        >>> from src.core import load_settings
        >>>
        >>> settings = load_settings()
        >>> manager = await BackendManager.create(settings)
        >>>
        >>> # Inference with automatic fallback
        >>> messages = [Message(role="user", content="Hello")]
        >>> response = await manager.generate_response(messages)
        >>>
        >>> # Check which backend was used
        >>> print(response.metadata.get("provider"))
        'npu'  # or 'cpu' if NPU failed
        >>>
        >>> await manager.close()
    """

    def __init__(
        self,
        providers: List[LLMProvider],
        fallback_enabled: bool = True,
    ):
        """Initialize backend manager.

        Note: Use BackendManager.create() instead of calling this directly.

        Args:
            providers: List of providers in fallback priority order.
            fallback_enabled: Whether to enable automatic fallback.
        """
        self.providers = providers
        self.current_provider = providers[0] if providers else None
        self.fallback_enabled = fallback_enabled
        self._logger = get_logger(f"{__name__}.BackendManager")

        self._logger.info(
            "Backend manager initialized",
            extra={
                "provider_count": len(providers),
                "providers": [p.name for p in providers],
                "fallback_enabled": fallback_enabled,
            },
        )

    @classmethod
    async def create(
        cls,
        settings: Settings,
        fallback_enabled: bool = True,
    ) -> "BackendManager":
        """Factory method to create backend manager with all providers.

        Args:
            settings: Application settings.
            fallback_enabled: Whether to enable automatic fallback.

        Returns:
            Initialized backend manager.

        Raises:
            BackendUnavailableError: If no providers could be initialized.

        Example:
            >>> from src.core import load_settings
            >>>
            >>> settings = load_settings()
            >>> manager = await BackendManager.create(settings)
        """
        providers = []

        # Try to initialize NPU provider
        try:
            npu_provider = NPUProvider(
                config=settings.npu_provider,
                timeout=settings.system.stream_timeout or 60.0,
            )

            if await npu_provider.health_check():
                providers.append(npu_provider)
                logger.info("NPU provider initialized and healthy")
            else:
                logger.warning("NPU provider failed health check, skipping")
                await npu_provider.close()

        except Exception as e:
            logger.warning(f"Failed to initialize NPU provider: {e}")

        # TODO: Add QNN provider initialization here when implemented

        # Always initialize CPU fallback
        try:
            cpu_provider = await CPUProvider.create(
                config=settings.cpu_fallback
            )
            providers.append(cpu_provider)
            logger.info("CPU fallback provider initialized")

        except Exception as e:
            logger.error(f"Failed to initialize CPU fallback: {e}")

        if not providers:
            raise BackendUnavailableError(
                "No inference backends available",
                backend_name="all",
                context={"attempted": ["npu", "cpu"]},
            )

        logger.info(
            f"Backend manager created with {len(providers)} provider(s): "
            f"{[p.name for p in providers]}"
        )

        return cls(providers, fallback_enabled)

    async def generate_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> GenerationResponse:
        """Generate response with automatic fallback on failure.

        Args:
            messages: List of conversation messages.
            config: Generation configuration.

        Returns:
            Generation response from first successful provider.

        Raises:
            BackendUnavailableError: If all providers fail.

        Example:
            >>> messages = [Message(role="user", content="Hello")]
            >>> response = await manager.generate_response(messages)
            >>> print(response.content)
        """
        if not self.providers:
            raise BackendUnavailableError(
                "No providers available",
                backend_name="all",
            )

        last_error = None

        for i, provider in enumerate(self.providers):
            try:
                self._logger.debug(
                    f"Attempting inference with {provider.name} provider",
                    extra={"provider": provider.name, "attempt": i + 1},
                )

                response = await provider.generate_response(messages, config)

                # Update current provider on success
                if provider != self.current_provider:
                    old_provider = self.current_provider.name if self.current_provider else "none"
                    self.current_provider = provider

                    self._logger.info(
                        f"Switched to {provider.name} provider",
                        extra={
                            "from": old_provider,
                            "to": provider.name,
                        },
                    )

                return response

            except BackendError as e:
                last_error = e
                self._logger.warning(
                    f"{provider.name} provider failed: {e.message}",
                    extra={
                        "provider": provider.name,
                        "error_type": type(e).__name__,
                        "context": e.context,
                    },
                )

                # If fallback is disabled, raise immediately
                if not self.fallback_enabled:
                    raise

                # If this is not the last provider, trigger fallback
                if i < len(self.providers) - 1:
                    next_provider = self.providers[i + 1]

                    fallback_error = FallbackTriggered(
                        from_backend=provider.name,
                        to_backend=next_provider.name,
                        reason=f"{type(e).__name__}: {e.message}",
                    )

                    self._logger.warning(
                        f"Falling back: {provider.name} → {next_provider.name}",
                        extra={
                            "from": provider.name,
                            "to": next_provider.name,
                            "reason": type(e).__name__,
                        },
                    )

            except Exception as e:
                last_error = e
                self._logger.error(
                    f"Unexpected error in {provider.name} provider",
                    exc_info=e,
                    extra={"provider": provider.name},
                )

                if not self.fallback_enabled:
                    raise

        # All providers failed
        raise BackendUnavailableError(
            "All inference backends failed",
            backend_name="all",
            context={
                "providers_attempted": [p.name for p in self.providers],
                "last_error": str(last_error),
            },
            original_error=last_error,
        )

    async def stream_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[str]:
        """Stream response with automatic fallback on failure.

        Args:
            messages: List of conversation messages.
            config: Generation configuration.

        Yields:
            Text chunks from first successful provider.

        Raises:
            BackendUnavailableError: If all providers fail.

        Example:
            >>> messages = [Message(role="user", content="Tell me a story")]
            >>> async for chunk in manager.stream_response(messages):
            ...     print(chunk, end="", flush=True)
        """
        if not self.providers:
            raise BackendUnavailableError(
                "No providers available",
                backend_name="all",
            )

        last_error = None

        for i, provider in enumerate(self.providers):
            try:
                self._logger.debug(
                    f"Attempting streaming with {provider.name} provider",
                    extra={"provider": provider.name},
                )

                async for chunk in provider.stream_response(messages, config):
                    yield chunk

                # If we reach here, streaming succeeded
                if provider != self.current_provider:
                    self.current_provider = provider
                    self._logger.info(f"Switched to {provider.name} provider")

                return  # Success, exit

            except BackendError as e:
                last_error = e
                self._logger.warning(
                    f"{provider.name} streaming failed: {e.message}",
                    extra={"provider": provider.name},
                )

                if not self.fallback_enabled or i >= len(self.providers) - 1:
                    raise

                # Log fallback
                next_provider = self.providers[i + 1]
                self._logger.warning(
                    f"Falling back: {provider.name} → {next_provider.name}"
                )

            except Exception as e:
                last_error = e
                self._logger.error(
                    f"Unexpected streaming error in {provider.name}",
                    exc_info=e,
                )

                if not self.fallback_enabled:
                    raise

        # All providers failed
        raise BackendUnavailableError(
            "All streaming backends failed",
            backend_name="all",
            context={
                "providers_attempted": [p.name for p in self.providers],
                "last_error": str(last_error),
            },
            original_error=last_error,
        )

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all providers.

        Returns:
            Dictionary mapping provider names to health status.

        Example:
            >>> health = await manager.health_check_all()
            >>> print(health)
            {'npu': True, 'cpu': True}
        """
        health_status = {}

        for provider in self.providers:
            try:
                is_healthy = await provider.health_check()
                health_status[provider.name] = is_healthy
            except Exception as e:
                self._logger.error(
                    f"Health check failed for {provider.name}",
                    exc_info=e,
                )
                health_status[provider.name] = False

        return health_status

    async def close(self) -> None:
        """Close all providers and release resources.

        Example:
            >>> await manager.close()
        """
        self._logger.info("Closing all providers")

        close_tasks = [provider.close() for provider in self.providers]
        await asyncio.gather(*close_tasks, return_exceptions=True)

        self._logger.info("All providers closed")

    # Context manager support
    async def __aenter__(self) -> "BackendManager":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and clean up."""
        await self.close()
