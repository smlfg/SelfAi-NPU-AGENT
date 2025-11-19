"""Async CPU fallback provider using llama-cpp-python.

This module provides async CPU inference using GGUF quantized models via llama-cpp-python.
Since llama-cpp-python is synchronous, we run it in a thread pool executor to maintain
async compatibility.

The CPU provider serves as the ultimate fallback when NPU/QNN are unavailable,
ensuring the system always remains functional.

Architecture:
    CPUProvider wraps llama-cpp-python in async interface:

    CPUProvider
        ↓
    ThreadPoolExecutor (async wrapper)
        ↓
    llama-cpp-python (sync)
        ↓
    GGUF Model (CPU inference)

Usage:
    >>> from src.backends import CPUProvider
    >>> from src.backends.base import Message
    >>> from src.core import load_settings
    >>>
    >>> settings = load_settings()
    >>> provider = await CPUProvider.create(settings.cpu_fallback)
    >>>
    >>> # Generate response (runs in background thread)
    >>> messages = [Message(role="user", content="Hello")]
    >>> response = await provider.generate_response(messages)
    >>> print(response.content)
    >>>
    >>> # Cleanup
    >>> await provider.close()
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import AsyncIterator, List, Optional

from src.backends.base import (
    GenerationConfig,
    GenerationResponse,
    LLMProvider,
    Message,
    messages_to_dicts,
)
from src.core import get_logger
from src.core.config import CPUFallbackSettings
from src.core.exceptions import CPUFallbackError, ModelLoadError


logger = get_logger(__name__)


# =============================================================================
# CPU PROVIDER IMPLEMENTATION
# =============================================================================


class CPUProvider(LLMProvider):
    """Async CPU fallback provider using llama-cpp-python.

    This provider loads GGUF quantized models and runs inference on CPU.
    Uses a thread pool executor to maintain async compatibility.

    Attributes:
        config: CPU fallback configuration.
        model: Loaded llama-cpp-python model.
        executor: Thread pool for running sync model operations.

    Example:
        >>> from src.core import load_settings
        >>>
        >>> settings = load_settings()
        >>> provider = await CPUProvider.create(settings.cpu_fallback)
        >>>
        >>> # Use as context manager
        >>> async with provider:
        ...     messages = [Message(role="user", content="Hello")]
        ...     response = await provider.generate_response(messages)
    """

    def __init__(
        self,
        config: CPUFallbackSettings,
        model,  # llama_cpp.Llama instance
        executor: ThreadPoolExecutor,
    ):
        """Initialize CPU provider.

        Note: Use CPUProvider.create() instead of calling this directly.

        Args:
            config: CPU fallback configuration.
            model: Loaded llama-cpp-python model.
            executor: Thread pool executor.
        """
        super().__init__(name="cpu")
        self.config = config
        self.model = model
        self.executor = executor

        self._logger.info(
            "CPU provider initialized",
            extra={
                "model_path": config.model_path,
                "n_ctx": config.n_ctx,
                "n_gpu_layers": config.n_gpu_layers,
            },
        )

    @classmethod
    async def create(
        cls,
        config: CPUFallbackSettings,
        max_workers: int = 1,
    ) -> "CPUProvider":
        """Factory method to create CPU provider with async model loading.

        Args:
            config: CPU fallback configuration.
            max_workers: Number of thread pool workers (default: 1).

        Returns:
            Initialized CPU provider.

        Raises:
            ModelLoadError: If model file not found or loading fails.

        Example:
            >>> from src.core import load_settings
            >>>
            >>> settings = load_settings()
            >>> provider = await CPUProvider.create(settings.cpu_fallback)
        """
        # Check if model file exists
        model_path = Path(config.model_path)
        if not model_path.exists():
            raise ModelLoadError(
                f"Model file not found: {config.model_path}",
                context={
                    "model_path": str(model_path),
                    "cwd": str(Path.cwd()),
                },
            )

        # Create thread pool executor
        executor = ThreadPoolExecutor(max_workers=max_workers)

        # Load model in thread pool to avoid blocking
        logger.info(f"Loading CPU model: {config.model_path}")

        try:
            loop = asyncio.get_event_loop()

            def load_model():
                """Load model in background thread."""
                try:
                    from llama_cpp import Llama
                except ImportError as e:
                    raise ModelLoadError(
                        "llama-cpp-python not installed. Install with: pip install llama-cpp-python",
                        original_error=e,
                    )

                return Llama(
                    model_path=str(model_path),
                    n_ctx=config.n_ctx,
                    n_gpu_layers=config.n_gpu_layers,
                    verbose=False,
                )

            model = await loop.run_in_executor(executor, load_model)

            logger.info(
                "CPU model loaded successfully",
                extra={
                    "model_path": config.model_path,
                    "n_ctx": config.n_ctx,
                },
            )

            return cls(config, model, executor)

        except Exception as e:
            executor.shutdown(wait=False)
            raise ModelLoadError(
                f"Failed to load CPU model: {config.model_path}",
                context={"model_path": config.model_path},
                original_error=e,
            ) from e

    async def generate_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> GenerationResponse:
        """Generate a complete response using CPU inference.

        Runs llama-cpp-python in a background thread to avoid blocking.

        Args:
            messages: List of conversation messages.
            config: Generation configuration (uses defaults if None).

        Returns:
            Complete generation response.

        Raises:
            CPUFallbackError: If CPU inference fails.

        Example:
            >>> messages = [Message(role="user", content="What is Python?")]
            >>> response = await provider.generate_response(messages)
            >>> print(response.content)
        """
        config = config or GenerationConfig()

        self._logger.debug(
            "Starting CPU inference",
            extra={
                "message_count": len(messages),
                "max_tokens": config.max_tokens,
            },
        )

        try:
            loop = asyncio.get_event_loop()

            def run_inference():
                """Run inference in background thread."""
                # Format messages for llama-cpp-python
                message_dicts = messages_to_dicts(messages)

                # Generate response
                response = self.model.create_chat_completion(
                    messages=message_dicts,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                    top_p=config.top_p,
                    stop=config.stop_sequences,
                )

                return response

            # Run in thread pool
            response = await loop.run_in_executor(self.executor, run_inference)

            # Parse llama-cpp-python response
            content = response["choices"][0]["message"]["content"]
            finish_reason = response["choices"][0]["finish_reason"]
            usage = response.get("usage", {})

            self._logger.info(
                "CPU inference completed",
                extra={
                    "response_length": len(content),
                    "tokens_used": usage.get("total_tokens", 0),
                },
            )

            return GenerationResponse(
                content=content,
                finish_reason=finish_reason,
                usage=usage,
                metadata={"provider": "cpu", "model_path": self.config.model_path},
            )

        except Exception as e:
            raise CPUFallbackError(
                "CPU inference failed",
                context={
                    "model_path": self.config.model_path,
                    "message_count": len(messages),
                },
                original_error=e,
            ) from e

    async def stream_response(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[str]:
        """Generate a streaming response using CPU inference.

        Note: llama-cpp-python's streaming is synchronous, so we yield chunks
        from a background thread.

        Args:
            messages: List of conversation messages.
            config: Generation configuration (uses defaults if None).

        Yields:
            Text chunks as they are generated.

        Raises:
            CPUFallbackError: If streaming fails.

        Example:
            >>> messages = [Message(role="user", content="Tell me a story")]
            >>> async for chunk in provider.stream_response(messages):
            ...     print(chunk, end="", flush=True)
        """
        config = config or GenerationConfig(stream=True)

        self._logger.debug("Starting CPU streaming inference")

        try:
            loop = asyncio.get_event_loop()
            queue = asyncio.Queue()

            def run_streaming_inference():
                """Run streaming inference in background thread."""
                try:
                    message_dicts = messages_to_dicts(messages)

                    # Create streaming iterator
                    stream = self.model.create_chat_completion(
                        messages=message_dicts,
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                        top_p=config.top_p,
                        stream=True,
                    )

                    # Put chunks in queue
                    for chunk in stream:
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta:
                            asyncio.run_coroutine_threadsafe(
                                queue.put(delta["content"]), loop
                            )

                    # Signal completion
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)

                except Exception as e:
                    asyncio.run_coroutine_threadsafe(queue.put(e), loop)

            # Start streaming in background thread
            self.executor.submit(run_streaming_inference)

            # Yield chunks from queue
            while True:
                item = await queue.get()

                if item is None:
                    # End of stream
                    break
                elif isinstance(item, Exception):
                    # Error occurred
                    raise item
                else:
                    # Chunk of text
                    yield item

            self._logger.info("CPU streaming completed")

        except Exception as e:
            raise CPUFallbackError(
                "CPU streaming inference failed",
                context={"model_path": self.config.model_path},
                original_error=e,
            ) from e

    async def health_check(self) -> bool:
        """Check if CPU provider is ready.

        Always returns True since if the model loaded, it's ready.

        Returns:
            True (CPU is always available once loaded).

        Example:
            >>> if await provider.health_check():
            ...     print("CPU provider ready")
        """
        return True  # If model loaded successfully, it's always ready

    async def close(self) -> None:
        """Unload model and shutdown thread pool.

        Example:
            >>> await provider.close()
        """
        self._logger.info("Closing CPU provider")

        # Shutdown thread pool
        self.executor.shutdown(wait=True)

        # Unload model (free memory)
        del self.model

        self._logger.info("CPU provider closed")
