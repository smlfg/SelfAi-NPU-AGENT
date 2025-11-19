"""QNN provider implementation for direct NPU model execution using Qualcomm AI Hub.

This module implements the QNN-based LLM provider that directly executes models on
Snapdragon X Elite NPU hardware using the Qualcomm AI Hub runtime.
"""

from pathlib import Path
from typing import Dict, Iterator, List, Optional

from src.backends.base import LLMProvider

# Conditional import of qai_hub_models - only available on compatible hardware
try:
    from qai_hub_models.models._shared.llm.app import ChatApp
    from qai_hub_models.models._shared.llm.model import LLMBase
    QAI_HUB_AVAILABLE = True
except ImportError:
    QAI_HUB_AVAILABLE = False
    ChatApp = None  # type: ignore
    LLMBase = None  # type: ignore


class QNNProvider(LLMProvider):
    """QNN-based LLM provider for direct NPU model execution.

    This provider uses Qualcomm AI Hub models to run inference directly on the
    Snapdragon X Elite NPU. It provides fast, on-device inference without requiring
    an external server like AnythingLLM.

    Attributes:
        model_path: Path to the QNN model directory.
        model_name: Name of the loaded model.
        model: ChatApp instance for running inference.
        context_length: Maximum context window size.
        max_tokens: Default maximum output tokens.
    """

    def __init__(
        self,
        model_path: str,
        *,
        context_length: int = 1024,
        max_tokens: int = 512,
    ) -> None:
        """Initialize the QNN provider.

        Args:
            model_path: Path to the QNN model directory (must contain genai_config.json).
            context_length: Maximum context window size (default: 1024).
            max_tokens: Default maximum output tokens (default: 512).

        Raises:
            ImportError: If qai_hub_models library is not installed.
            FileNotFoundError: If the model directory or genai_config.json is not found.
            RuntimeError: If model initialization fails.
        """
        super().__init__(provider_name="QNN", provider_type="qnn")

        if not QAI_HUB_AVAILABLE:
            raise ImportError(
                "The 'qai_hub_models' library is not installed. "
                "QNN NPU inference is not available. "
                "Install it with: pip install qai-hub-models"
            )

        self.model_path = Path(model_path)
        self.model_name = self.model_path.name
        self.context_length = context_length
        self.max_tokens = max_tokens
        self.model = self._load_model()

    def _get_model_class(self):
        """Determine the correct model class from qai_hub_models based on model name.

        Returns:
            The appropriate model class for this QNN model.

        Note:
            This method attempts to load model-specific classes for better performance
            and compatibility. Falls back to the generic LLMBase class if a specific
            class is not available.
        """
        model_name_lower = self.model_name.lower()

        # Try to load model-specific classes
        if "deepseek" in model_name_lower:
            try:
                from qai_hub_models.models.deepseek_r1_distill_qwen_7b.model import (
                    DeepSeekR1DistillQwen7B as ModelClass
                )
                return ModelClass
            except ImportError:
                # Fall back to generic LLM class
                return LLMBase
        elif "phi" in model_name_lower:
            try:
                from qai_hub_models.models.phi_3_5_mini_instruct.model import (
                    Phi35MiniInstruct as ModelClass
                )
                return ModelClass
            except ImportError:
                # Fall back to generic LLM class
                return LLMBase
        else:
            # Default to generic LLM class for unknown models
            return LLMBase

    def _load_model(self) -> ChatApp:
        """Load the QNN model using the QAI Hub ChatApp.

        Returns:
            Initialized ChatApp instance ready for inference.

        Raises:
            FileNotFoundError: If model directory or config is missing.
            RuntimeError: If model initialization fails.
        """
        if not self.model_path.is_dir() or not (self.model_path / "genai_config.json").exists():
            raise FileNotFoundError(
                f"QNN model directory or genai_config.json not found at: {self.model_path}"
            )

        try:
            model_cls = self._get_model_class()

            # ChatApp is the primary interface for QNN model interaction
            # The prompt format must be model-specific; this is a common format
            app = ChatApp(
                model_cls=model_cls,
                get_input_prompt_with_tags=lambda x: f"<|user|>\n{x}<|end|>\n<|assistant|>\n",
                tokenizer=None,  # Tokenizer is loaded internally by the model
                end_tokens=["<|end|>", "<|endoftext|>", "</s>"]
            )
            return app
        except Exception as exc:
            raise RuntimeError(f"Error initializing QNN ChatApp: {exc}") from exc

    def _format_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Format system prompt, history, and user prompt for QNN model input.

        Args:
            system_prompt: System-level instructions.
            user_prompt: Current user query.
            history: Optional conversation history.

        Returns:
            Formatted prompt string suitable for QNN model input.

        Note:
            QNN models may have limited support for structured history and system prompts.
            This implementation prepends system instructions to the user query.
        """
        parts: List[str] = []

        # Add system prompt as instruction prefix
        if system_prompt:
            parts.append(f"System Instructions: {system_prompt.strip()}")

        # TODO: Add proper history support when QNN models support it
        # Current limitation: history is not fully integrated into QNN inference

        # Add user query
        parts.append(f"User Query: {user_prompt.strip()}")

        return "\n\n".join(parts)

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a complete response from the QNN model (blocking call).

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history (limited support).
            timeout: Not used for local QNN inference.
            max_output_tokens: Maximum tokens to generate (overrides default).

        Returns:
            Complete generated response text.

        Raises:
            RuntimeError: If inference fails.
        """
        full_prompt = self._format_prompt(system_prompt, user_prompt, history)
        output_tokens = max_output_tokens if max_output_tokens is not None else self.max_tokens

        try:
            # Run QNN inference with on-device execution
            response = self.model.generate_output_prompt(
                input_prompt=full_prompt,
                context_length=self.context_length,
                max_output_tokens=output_tokens,
                model_from_pretrained_extra={
                    "eval_mode": "on-device",
                    "target_runtime": "QNN_CONTEXT_BINARY"
                }
            )
            return response if response else "QNN model produced no output."
        except Exception as exc:
            raise RuntimeError(f"QNN inference error: {exc}") from exc

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a streaming response (not supported for QNN - fallback to blocking).

        QNN models do not currently support native streaming. This method falls back
        to generating the complete response and yielding it as a single chunk.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Not used.
            max_output_tokens: Maximum tokens to generate.

        Yields:
            The complete response as a single chunk.

        Note:
            This is a fallback implementation. True streaming is not available for QNN.
        """
        # QNN does not support streaming - generate complete response
        response = self.generate_response(
            system_prompt,
            user_prompt,
            history,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
        yield response

    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming responses.

        Returns:
            False, as QNN models do not support true streaming.
        """
        return False

    def healthcheck(self) -> bool:
        """Perform a health check on the QNN model.

        Returns:
            True if the model is loaded and appears functional, False otherwise.
        """
        return self.model is not None

    def get_metadata(self) -> Dict[str, any]:
        """Get metadata about this QNN provider.

        Returns:
            Dictionary containing provider metadata including model information.
        """
        metadata = super().get_metadata()
        metadata.update({
            "model_path": str(self.model_path),
            "model_name": self.model_name,
            "context_length": self.context_length,
            "max_tokens": self.max_tokens,
        })
        return metadata


def find_qnn_models(models_dir: Path) -> List[Path]:
    """Find available QNN model directories by searching for genai_config.json files.

    Args:
        models_dir: Root directory to search for QNN models.

    Returns:
        List of paths to QNN model directories.

    Note:
        A valid QNN model directory must contain a genai_config.json file.
    """
    qnn_model_paths: List[Path] = []
    if not models_dir.is_dir():
        return []

    # Recursively search for QNN model configuration files
    for config_file in models_dir.rglob("genai_config.json"):
        # The model directory is the parent of the config file
        qnn_model_paths.append(config_file.parent)

    return qnn_model_paths
