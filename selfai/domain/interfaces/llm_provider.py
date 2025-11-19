"""LLM Provider interface for language model inference.

This module defines the protocol that all LLM implementations must follow,
enabling dependency inversion and easy swapping of LLM backends.

The protocol supports both streaming and blocking inference modes.
"""

from typing import Protocol, Iterator, Optional


class ILLMProvider(Protocol):
    """Protocol defining the interface for language model providers.

    All LLM implementations (AnythingLLM, NPU, CPU, Ollama) must implement
    this protocol to be compatible with the application layer.

    This protocol follows the Liskov Substitution Principle (LSP):
    any implementation can be substituted without breaking the system.

    Methods:
        generate_response: Blocking inference call.
        stream_generate_response: Streaming inference call (optional).
        get_model_info: Retrieve model metadata (optional).
    """

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[list[dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from the language model (blocking).

        This method performs a synchronous inference call and returns the
        complete generated text.

        Args:
            system_prompt: System instructions defining the AI's behavior.
            user_prompt: The user's input message or question.
            history: Optional conversation history in format:
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            timeout: Maximum time in seconds to wait for response.
                If None, uses provider's default timeout.
            max_output_tokens: Maximum number of tokens to generate.
                If None, uses provider's default limit.

        Returns:
            Generated response text from the language model.

        Raises:
            TimeoutError: If the request exceeds the timeout duration.
            ConnectionError: If the LLM provider is unreachable.
            ValueError: If input validation fails.
            RuntimeError: For other provider-specific errors.

        Example:
            >>> provider = MyLLMProvider()
            >>> response = provider.generate_response(
            ...     system_prompt="You are a helpful assistant.",
            ...     user_prompt="What is the capital of France?",
            ...     max_output_tokens=100
            ... )
            >>> print(response)
            "The capital of France is Paris."
        """
        ...

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[list[dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a response from the language model (streaming).

        This method performs an asynchronous streaming inference call,
        yielding tokens as they are generated.

        Note:
            Not all LLM providers support streaming. Implementations that
            don't support streaming should raise NotImplementedError.

        Args:
            system_prompt: System instructions defining the AI's behavior.
            user_prompt: The user's input message or question.
            history: Optional conversation history.
            timeout: Maximum time in seconds for the entire stream.
            max_output_tokens: Maximum number of tokens to generate.

        Yields:
            str: Individual tokens or chunks of text as they are generated.

        Raises:
            NotImplementedError: If the provider doesn't support streaming.
            TimeoutError: If the stream exceeds the timeout duration.
            ConnectionError: If the connection is lost during streaming.
            ValueError: If input validation fails.

        Example:
            >>> provider = MyLLMProvider()
            >>> for chunk in provider.stream_generate_response(
            ...     system_prompt="You are helpful.",
            ...     user_prompt="Write a poem."
            ... ):
            ...     print(chunk, end="", flush=True)
            Roses are red,
            Violets are blue,
            ...
        """
        ...

    def get_model_info(self) -> dict[str, str]:
        """Retrieve metadata about the language model.

        Returns:
            Dictionary containing model information with keys:
                - name: Model identifier (e.g., "Phi-3-mini")
                - type: Provider type (e.g., "npu", "cpu", "api")
                - version: Model version if available
                - context_length: Maximum context window size
                - parameters: Number of parameters (e.g., "3.8B")

        Example:
            >>> provider = MyLLMProvider()
            >>> info = provider.get_model_info()
            >>> print(info["name"])
            "Phi-3-mini-4k-instruct"
        """
        ...
