"""Abstract base class for LLM providers.

This module defines the interface that all LLM backend providers must implement.
It ensures consistent behavior across different backend implementations (NPU, CPU, QNN).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


class LLMProvider(ABC):
    """Abstract base class defining the interface for all LLM providers.

    All concrete LLM provider implementations (NPU, CPU, QNN) must inherit from
    this class and implement its abstract methods. This ensures a consistent
    interface for generating responses across different backend types.

    Attributes:
        provider_name: Human-readable name of the provider (e.g., "AnythingLLM", "CPU").
        provider_type: Type category of the provider (e.g., "npu", "cpu", "qnn").
    """

    def __init__(self, provider_name: str, provider_type: str) -> None:
        """Initialize the LLM provider.

        Args:
            provider_name: Human-readable name identifying this provider instance.
            provider_type: Type category for this provider (npu/cpu/qnn).
        """
        self.provider_name = provider_name
        self.provider_type = provider_type

    @abstractmethod
    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a complete response from the LLM (blocking call).

        This method sends a request to the LLM backend and waits for the complete
        response before returning. Use this when you need the full response at once.

        Args:
            system_prompt: System-level instructions that define the AI's behavior.
            user_prompt: The actual user query or instruction.
            history: Optional conversation history as a list of message dictionaries.
                Each dictionary should have 'role' and 'content' keys.
            timeout: Optional timeout in seconds for the request.
            max_output_tokens: Optional maximum number of tokens to generate.

        Returns:
            The complete generated response as a string.

        Raises:
            RuntimeError: If the backend fails to generate a response.
            TimeoutError: If the request exceeds the specified timeout.
        """
        pass

    @abstractmethod
    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a streaming response from the LLM (yields chunks).

        This method sends a request to the LLM backend and yields response chunks
        as they become available. Use this for better perceived latency and to
        provide incremental feedback to users.

        Args:
            system_prompt: System-level instructions that define the AI's behavior.
            user_prompt: The actual user query or instruction.
            history: Optional conversation history as a list of message dictionaries.
                Each dictionary should have 'role' and 'content' keys.
            timeout: Optional timeout in seconds for the request.
            max_output_tokens: Optional maximum number of tokens to generate.

        Yields:
            str: Individual chunks of the response as they are generated.

        Raises:
            RuntimeError: If the backend fails to generate a response or streaming
                is not supported by this provider.
            TimeoutError: If the request exceeds the specified timeout.
        """
        pass

    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming responses.

        Returns:
            True if stream_generate_response is fully implemented and functional,
            False otherwise.
        """
        # Default implementation - subclasses can override
        return True

    def healthcheck(self) -> bool:
        """Perform a health check to verify the provider is accessible and functional.

        This method should verify that the backend service is reachable and ready
        to handle requests. Implementations should be lightweight and fast.

        Returns:
            True if the provider is healthy and ready, False otherwise.

        Note:
            This is an optional method with a default implementation. Subclasses
            are encouraged to override with provider-specific health checks.
        """
        # Default implementation - subclasses should override
        return True

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about this provider.

        Returns:
            Dictionary containing provider metadata such as name, type, model info,
            and capabilities.
        """
        return {
            "provider_name": self.provider_name,
            "provider_type": self.provider_type,
            "supports_streaming": self.supports_streaming(),
        }

    def __repr__(self) -> str:
        """Return a string representation of this provider."""
        return f"{self.__class__.__name__}(name='{self.provider_name}', type='{self.provider_type}')"
