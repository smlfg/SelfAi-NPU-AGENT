"""CPU provider implementation using llama-cpp-python for local GGUF model inference.

This module implements the CPU-based LLM provider as a fallback option when NPU
acceleration is not available. It uses llama-cpp-python to run GGUF quantized models
on the CPU.
"""

from pathlib import Path
from typing import Dict, Iterator, List, Optional

from src.backends.base import LLMProvider

# Conditional import of llama_cpp - not always available
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None  # type: ignore


class CPUProvider(LLMProvider):
    """CPU-based LLM provider using llama-cpp-python for GGUF models.

    This provider runs quantized GGUF models on the CPU without requiring GPU or NPU
    acceleration. It serves as a reliable fallback option when hardware acceleration
    is unavailable.

    Attributes:
        model_path: Path to the GGUF model file.
        model: Loaded Llama model instance.
        n_ctx: Context window size.
        n_gpu_layers: Number of layers to offload to GPU (0 for pure CPU).
        verbose: Whether to enable verbose model logging.
    """

    def __init__(
        self,
        model_path: str,
        *,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        verbose: bool = False,
    ) -> None:
        """Initialize the CPU provider.

        Args:
            model_path: Path to the GGUF model file.
            n_ctx: Context window size (default: 4096).
            n_gpu_layers: Number of layers to offload to GPU (default: 0 for pure CPU).
            verbose: Enable verbose logging during inference (default: False).

        Raises:
            ImportError: If llama-cpp-python is not installed.
            FileNotFoundError: If the model file is not found.
            RuntimeError: If model loading fails.
        """
        super().__init__(provider_name="CPU", provider_type="cpu")

        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "CPU fallback is not available. "
                "Install it with: pip install llama-cpp-python"
            )

        self.model_path = Path(model_path)
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.verbose = verbose
        self.model = self._load_model()

    def _load_model(self) -> Llama:
        """Load the GGUF model from the specified path.

        Returns:
            Loaded Llama model instance ready for inference.

        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If model loading fails.
        """
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Model file not found at: {self.model_path}"
            )

        try:
            # Load the model with specified parameters
            # n_ctx defines the maximum context length the model can process
            # n_gpu_layers=0 ensures pure CPU execution
            return Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Error loading GGUF model: {exc}"
            ) from exc

    def _format_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """Format system prompt, history, and user prompt into message list.

        Args:
            system_prompt: System-level instructions.
            user_prompt: Current user query.
            history: Optional conversation history.

        Returns:
            List of message dictionaries in OpenAI format.
        """
        messages: List[Dict[str, str]] = []

        # Add system prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        if history:
            messages.extend(history)

        # Add current user prompt
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a complete response from the CPU model (blocking call).

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Not used for local CPU inference.
            max_output_tokens: Maximum tokens to generate.

        Returns:
            Complete generated response text.

        Raises:
            RuntimeError: If inference fails.
        """
        messages = self._format_messages(system_prompt, user_prompt, history)

        try:
            completion = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_output_tokens,
            )
            return completion['choices'][0]['message']['content']
        except Exception as exc:
            raise RuntimeError(
                f"CPU inference error: {exc}"
            ) from exc

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a streaming response from the CPU model (yields chunks).

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Not used for local CPU inference.
            max_output_tokens: Maximum tokens to generate.

        Yields:
            Individual text chunks as they are generated.

        Raises:
            RuntimeError: If inference fails.
        """
        messages = self._format_messages(system_prompt, user_prompt, history)

        try:
            stream = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_output_tokens,
                stream=True,
            )

            for chunk in stream:
                delta = chunk['choices'][0].get('delta', {})
                content = delta.get('content')
                if content:
                    yield content

        except Exception as exc:
            raise RuntimeError(
                f"CPU streaming inference error: {exc}"
            ) from exc

    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming responses.

        Returns:
            True, as llama-cpp-python supports streaming.
        """
        return True

    def healthcheck(self) -> bool:
        """Perform a health check on the CPU model.

        Returns:
            True if the model is loaded and appears functional, False otherwise.
        """
        return self.model is not None

    def get_metadata(self) -> Dict[str, any]:
        """Get metadata about this CPU provider.

        Returns:
            Dictionary containing provider metadata including model information.
        """
        metadata = super().get_metadata()
        metadata.update({
            "model_path": str(self.model_path),
            "n_ctx": self.n_ctx,
            "n_gpu_layers": self.n_gpu_layers,
            "verbose": self.verbose,
        })
        return metadata
