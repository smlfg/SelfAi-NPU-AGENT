"""LLM Provider Wrappers - Auto-configured Backend Interfaces.

This module provides clean wrapper classes for all LLM backends that
automatically pull their configuration from the centralized settings system.

Usage:
    from src.core.config import load_settings
    from src.core.providers import NPUProvider

    settings = load_settings()
    npu = NPUProvider(settings)  # Automatically pulls url/key from settings
    response = npu.generate("Hello, world!")
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from src.core.config import AppConfig
from src.core.logger import get_logger

# Import legacy interfaces
from selfai.core.anythingllm_interface import AnythingLLMInterface
from selfai.core.local_llm_interface import LocalLLMInterface

try:
    from selfai.core.npu_llm_interface import NpuLLMInterface
except ImportError:
    NpuLLMInterface = None  # NPU interface is optional

__all__ = [
    "NPUProvider",
    "CPUProvider",
    "QNNProvider",
    "PlannerProvider",
    "MergeProvider",
]


logger = get_logger(__name__)


class NPUProvider:
    """NPU-accelerated LLM provider (AnythingLLM backend).

    This provider automatically configures itself from the app settings,
    connecting to the AnythingLLM server for NPU-accelerated inference.

    Example:
        ```python
        from src.core.config import load_settings
        from src.core.providers import NPUProvider

        settings = load_settings()
        npu = NPUProvider(settings)

        response = npu.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="What is Python?",
        )
        print(response)

        # Streaming
        for chunk in npu.generate_stream(...):
            print(chunk, end="", flush=True)
        ```

    Attributes:
        settings: Application configuration
        interface: Underlying AnythingLLM interface
        backend_name: Backend identifier ("npu" or "anythingllm")
    """

    def __init__(self, settings: AppConfig) -> None:
        """Initialize NPU provider from settings.

        Args:
            settings: Application configuration (from load_settings())

        Raises:
            ValueError: If NPU config is missing or invalid
        """
        self.settings = settings
        self.backend_name = "npu"

        # Extract NPU config
        npu_config = settings.npu_provider

        logger.info(
            f"Initializing NPU provider: {npu_config.base_url} "
            f"(workspace: {npu_config.workspace_slug})"
        )

        # Get streaming settings
        streaming_enabled = settings.system.streaming_enabled
        stream_timeout = settings.system.stream_timeout or 60.0

        # Initialize interface
        try:
            self.interface = AnythingLLMInterface(
                api_key=npu_config.api_key,
                base_url=npu_config.base_url,
                workspace_slug=npu_config.workspace_slug,
                stream=streaming_enabled,
                timeout=stream_timeout,
            )
            logger.info("NPU provider initialized successfully")
        except Exception as exc:
            logger.error(f"Failed to initialize NPU provider: {exc}")
            raise ValueError(f"NPU provider initialization failed: {exc}") from exc

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Optional[Iterable[Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate response from NPU.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            history: Optional conversation history
            timeout: Optional timeout override
            max_output_tokens: Optional max tokens override

        Returns:
            Generated response text
        """
        return self.interface.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Optional[Iterable[Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        """Generate streaming response from NPU.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            history: Optional conversation history
            timeout: Optional timeout override
            max_output_tokens: Optional max tokens override

        Yields:
            Response chunks
        """
        return self.interface.stream_generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )


class QNNProvider:
    """QNN (Qualcomm Neural Network) provider for direct NPU access.

    This provider uses QAI Hub models for on-device inference directly
    on the Snapdragon X Elite NPU.

    Example:
        ```python
        from src.core.config import load_settings
        from src.core.providers import QNNProvider

        settings = load_settings()
        qnn = QNNProvider(settings, model_path="/path/to/model.qnn")

        response = qnn.generate("System prompt", "User prompt")
        ```
    """

    def __init__(self, settings: AppConfig, model_path: str) -> None:
        """Initialize QNN provider.

        Args:
            settings: Application configuration
            model_path: Path to QNN model file

        Raises:
            ImportError: If QNN interface not available
            ValueError: If model not found
        """
        self.settings = settings
        self.backend_name = "qnn"
        self.model_path = model_path

        if NpuLLMInterface is None:
            raise ImportError(
                "QNN interface not available. Install qai_hub_models."
            )

        logger.info(f"Initializing QNN provider with model: {model_path}")

        try:
            self.interface = NpuLLMInterface(model_path=model_path)
            logger.info("QNN provider initialized successfully")
        except Exception as exc:
            logger.error(f"Failed to initialize QNN provider: {exc}")
            raise ValueError(f"QNN provider initialization failed: {exc}") from exc

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Optional[Iterable[Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate response from QNN.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            history: Optional conversation history
            timeout: Optional timeout override
            max_output_tokens: Optional max tokens override

        Returns:
            Generated response text
        """
        return self.interface.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )


class CPUProvider:
    """CPU-based LLM provider (llama-cpp-python fallback).

    This provider uses GGUF quantized models for CPU inference,
    providing a guaranteed fallback when NPU is unavailable.

    Example:
        ```python
        from src.core.config import load_settings
        from src.core.providers import CPUProvider

        settings = load_settings()
        cpu = CPUProvider(settings)

        response = cpu.generate("System prompt", "User prompt")
        ```
    """

    def __init__(self, settings: AppConfig) -> None:
        """Initialize CPU provider from settings.

        Args:
            settings: Application configuration

        Raises:
            ValueError: If CPU config is missing or model not found
        """
        self.settings = settings
        self.backend_name = "cpu"

        # Extract CPU config
        cpu_config = settings.cpu_fallback

        logger.info(f"Initializing CPU provider with model: {cpu_config.model_path}")

        try:
            self.interface = LocalLLMInterface(
                model_path=cpu_config.model_path,
                n_ctx=cpu_config.n_ctx,
                n_gpu_layers=cpu_config.n_gpu_layers,
            )
            logger.info("CPU provider initialized successfully")
        except Exception as exc:
            logger.error(f"Failed to initialize CPU provider: {exc}")
            raise ValueError(f"CPU provider initialization failed: {exc}") from exc

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Optional[Iterable[Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate response from CPU.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            history: Optional conversation history
            timeout: Optional timeout override
            max_output_tokens: Optional max tokens override

        Returns:
            Generated response text
        """
        return self.interface.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )


class PlannerProvider:
    """Ollama-based planner provider for task decomposition.

    This provider connects to an Ollama server to generate execution plans.

    Example:
        ```python
        from src.core.config import load_settings
        from src.core.providers import PlannerProvider

        settings = load_settings()
        planner = PlannerProvider(settings, provider_name="local-ollama")

        plan = planner.generate_plan(goal="Analyze data", agents=[...])
        ```
    """

    def __init__(
        self,
        settings: AppConfig,
        provider_name: Optional[str] = None,
    ) -> None:
        """Initialize planner provider from settings.

        Args:
            settings: Application configuration
            provider_name: Name of planner provider to use (default: first available)

        Raises:
            ValueError: If planner config missing or provider not found
        """
        self.settings = settings
        self.backend_name = "planner"

        if not settings.planner or not settings.planner.enabled:
            raise ValueError("Planner is not enabled in configuration")

        if not settings.planner.providers:
            raise ValueError("No planner providers configured")

        # Select provider
        if provider_name:
            provider_config = next(
                (p for p in settings.planner.providers if p.name == provider_name),
                None,
            )
            if not provider_config:
                raise ValueError(f"Planner provider '{provider_name}' not found")
        else:
            provider_config = settings.planner.providers[0]

        self.provider_name = provider_config.name

        logger.info(
            f"Initializing planner provider '{self.provider_name}' "
            f"({provider_config.type}, model: {provider_config.model})"
        )

        # Import planner interface
        from src.pipeline.planner import Planner, PlannerConfig

        # Create config
        planner_config = PlannerConfig(
            base_url=provider_config.base_url,
            model=provider_config.model,
            timeout=provider_config.timeout,
            max_tokens=provider_config.max_tokens,
            headers=provider_config.headers,
        )

        # Initialize planner
        self.interface = Planner(planner_config)
        logger.info(f"Planner provider '{self.provider_name}' initialized")


class MergeProvider:
    """Ollama-based merge provider for result synthesis.

    This provider connects to an Ollama server to merge subtask results.

    Example:
        ```python
        from src.core.config import load_settings
        from src.core.providers import MergeProvider

        settings = load_settings()
        merger = MergeProvider(settings, provider_name="merge-ollama")

        result = merger.merge(plan, execution_result)
        ```
    """

    def __init__(
        self,
        settings: AppConfig,
        provider_name: Optional[str] = None,
    ) -> None:
        """Initialize merge provider from settings.

        Args:
            settings: Application configuration
            provider_name: Name of merge provider to use (default: first available)

        Raises:
            ValueError: If merge config missing or provider not found
        """
        self.settings = settings
        self.backend_name = "merge"

        if not settings.merge or not settings.merge.enabled:
            raise ValueError("Merge is not enabled in configuration")

        if not settings.merge.providers:
            raise ValueError("No merge providers configured")

        # Select provider
        if provider_name:
            provider_config = next(
                (p for p in settings.merge.providers if p.name == provider_name),
                None,
            )
            if not provider_config:
                raise ValueError(f"Merge provider '{provider_name}' not found")
        else:
            provider_config = settings.merge.providers[0]

        self.provider_name = provider_config.name

        logger.info(
            f"Initializing merge provider '{self.provider_name}' "
            f"({provider_config.type}, model: {provider_config.model})"
        )

        # Import merge interface (from legacy for now)
        from selfai.core.merge_ollama_interface import MergeOllamaInterface

        # Initialize merge interface
        self.interface = MergeOllamaInterface(
            base_url=provider_config.base_url,
            model=provider_config.model,
            timeout=provider_config.timeout,
            max_tokens=provider_config.max_tokens,
            headers=provider_config.headers,
        )

        logger.info(f"Merge provider '{self.provider_name}' initialized")
