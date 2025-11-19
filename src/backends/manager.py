"""Backend manager with automatic fallback logic for LLM providers.

This module implements the BackendManager class which orchestrates multiple LLM
providers and automatically falls back from NPU to CPU when backends fail.
"""

import time
from typing import Any, Dict, Iterator, List, Optional

from src.backends.base import LLMProvider


class BackendError(Exception):
    """Exception raised when all backends fail to generate a response."""
    pass


class BackendManager:
    """Manages multiple LLM providers with automatic fallback logic.

    The BackendManager maintains a prioritized list of LLM providers and automatically
    switches to fallback providers when the primary backend fails. This ensures robust
    operation even when hardware acceleration is unavailable.

    Typical fallback chain: NPU (AnythingLLM) → QNN → CPU

    Attributes:
        providers: List of registered LLM providers in priority order.
        active_provider_index: Index of the currently active provider.
        retry_attempts: Number of retry attempts per provider.
        retry_delay: Delay in seconds between retry attempts.
    """

    def __init__(
        self,
        providers: Optional[List[LLMProvider]] = None,
        *,
        retry_attempts: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the backend manager.

        Args:
            providers: Optional list of LLM providers in priority order.
            retry_attempts: Number of retries per provider (default: 2).
            retry_delay: Delay in seconds between retries (default: 1.0).

        Raises:
            ValueError: If no providers are given and none are added later.
        """
        self.providers: List[LLMProvider] = providers or []
        self.active_provider_index: int = 0
        self.retry_attempts: int = max(0, retry_attempts)
        self.retry_delay: float = max(0.0, retry_delay)

    def add_provider(self, provider: LLMProvider, priority: Optional[int] = None) -> None:
        """Add a new provider to the manager.

        Args:
            provider: LLM provider instance to add.
            priority: Optional priority index (lower = higher priority).
                If None, appends to the end of the list.

        Raises:
            TypeError: If provider is not an instance of LLMProvider.
        """
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                f"Provider must be an instance of LLMProvider, got {type(provider)}"
            )

        if priority is None:
            self.providers.append(provider)
        else:
            priority_index = max(0, min(priority, len(self.providers)))
            self.providers.insert(priority_index, provider)

    def remove_provider(self, provider_name: str) -> bool:
        """Remove a provider by name.

        Args:
            provider_name: Name of the provider to remove.

        Returns:
            True if a provider was removed, False if not found.
        """
        initial_count = len(self.providers)
        self.providers = [
            p for p in self.providers
            if p.provider_name != provider_name
        ]
        return len(self.providers) < initial_count

    def get_active_provider(self) -> Optional[LLMProvider]:
        """Get the currently active provider.

        Returns:
            The active LLMProvider instance, or None if no providers are available.
        """
        if not self.providers or self.active_provider_index >= len(self.providers):
            return None
        return self.providers[self.active_provider_index]

    def set_active_provider(self, index: int) -> bool:
        """Set the active provider by index.

        Args:
            index: Index of the provider to activate.

        Returns:
            True if successful, False if index is out of range.
        """
        if 0 <= index < len(self.providers):
            self.active_provider_index = index
            return True
        return False

    def set_active_provider_by_name(self, provider_name: str) -> bool:
        """Set the active provider by name.

        Args:
            provider_name: Name of the provider to activate.

        Returns:
            True if successful, False if provider not found.
        """
        for idx, provider in enumerate(self.providers):
            if provider.provider_name == provider_name:
                self.active_provider_index = idx
                return True
        return False

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all registered providers with their metadata.

        Returns:
            List of dictionaries containing provider information.
        """
        return [
            {
                "index": idx,
                "name": provider.provider_name,
                "type": provider.provider_type,
                "active": idx == self.active_provider_index,
                "metadata": provider.get_metadata(),
            }
            for idx, provider in enumerate(self.providers)
        ]

    def healthcheck_all(self) -> Dict[str, bool]:
        """Run health checks on all providers.

        Returns:
            Dictionary mapping provider names to health check results.
        """
        return {
            provider.provider_name: provider.healthcheck()
            for provider in self.providers
        }

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        use_fallback: bool = True,
    ) -> str:
        """Generate a response with automatic fallback on failure.

        This method attempts to generate a response using the active provider first,
        then falls back to other providers in order if the active one fails.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Optional request timeout.
            max_output_tokens: Optional maximum tokens to generate.
            use_fallback: Whether to try fallback providers on failure (default: True).

        Returns:
            Generated response text.

        Raises:
            BackendError: If all providers fail to generate a response.
            ValueError: If no providers are registered.
        """
        if not self.providers:
            raise ValueError("No providers registered in BackendManager.")

        # Determine provider order: active first, then fallbacks
        if use_fallback:
            provider_indices = [self.active_provider_index] + [
                idx for idx in range(len(self.providers))
                if idx != self.active_provider_index
            ]
        else:
            provider_indices = [self.active_provider_index]

        last_error: Optional[Exception] = None

        # Try each provider in order
        for provider_index in provider_indices:
            provider = self.providers[provider_index]

            # Try with retries
            for attempt in range(self.retry_attempts + 1):
                try:
                    response = provider.generate_response(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        history=history,
                        timeout=timeout,
                        max_output_tokens=max_output_tokens,
                    )

                    # Success - update active provider if we fell back
                    if provider_index != self.active_provider_index:
                        self.active_provider_index = provider_index

                    return response

                except Exception as exc:
                    last_error = exc
                    if attempt < self.retry_attempts:
                        # Retry after delay
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        # Move to next provider
                        break

        # All providers failed
        raise BackendError(
            f"All {len(provider_indices)} provider(s) failed. "
            f"Last error: {last_error}"
        ) from last_error

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        use_fallback: bool = True,
    ) -> Iterator[str]:
        """Generate a streaming response with automatic fallback on failure.

        This method attempts to generate a streaming response using the active provider
        first, then falls back to other providers in order if the active one fails.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Optional request timeout.
            max_output_tokens: Optional maximum tokens to generate.
            use_fallback: Whether to try fallback providers on failure (default: True).

        Yields:
            Individual text chunks as they are generated.

        Raises:
            BackendError: If all providers fail to generate a response.
            ValueError: If no providers are registered.
        """
        if not self.providers:
            raise ValueError("No providers registered in BackendManager.")

        # Determine provider order: active first, then fallbacks
        if use_fallback:
            provider_indices = [self.active_provider_index] + [
                idx for idx in range(len(self.providers))
                if idx != self.active_provider_index
            ]
        else:
            provider_indices = [self.active_provider_index]

        last_error: Optional[Exception] = None

        # Try each provider in order
        for provider_index in provider_indices:
            provider = self.providers[provider_index]

            # Skip if provider doesn't support streaming
            if not provider.supports_streaming():
                # Fall back to blocking mode and yield as single chunk
                try:
                    response = provider.generate_response(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        history=history,
                        timeout=timeout,
                        max_output_tokens=max_output_tokens,
                    )

                    # Success - update active provider if we fell back
                    if provider_index != self.active_provider_index:
                        self.active_provider_index = provider_index

                    yield response
                    return

                except Exception as exc:
                    last_error = exc
                    continue

            # Try streaming with retries
            for attempt in range(self.retry_attempts + 1):
                try:
                    stream = provider.stream_generate_response(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        history=history,
                        timeout=timeout,
                        max_output_tokens=max_output_tokens,
                    )

                    # Success - update active provider if we fell back
                    if provider_index != self.active_provider_index:
                        self.active_provider_index = provider_index

                    # Yield all chunks from the stream
                    for chunk in stream:
                        yield chunk
                    return

                except Exception as exc:
                    last_error = exc
                    if attempt < self.retry_attempts:
                        # Retry after delay
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        # Move to next provider
                        break

        # All providers failed
        raise BackendError(
            f"All {len(provider_indices)} provider(s) failed. "
            f"Last error: {last_error}"
        ) from last_error

    def __repr__(self) -> str:
        """Return a string representation of this manager."""
        active_name = "None"
        if self.providers and 0 <= self.active_provider_index < len(self.providers):
            active_name = self.providers[self.active_provider_index].provider_name
        return (
            f"BackendManager(providers={len(self.providers)}, "
            f"active='{active_name}')"
        )
