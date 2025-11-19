# LLM Backend Abstraction Layer

This package provides a clean, modular abstraction layer for different LLM inference backends with automatic fallback support.

## Architecture

The backend abstraction follows the **Strategy Pattern** combined with **Chain of Responsibility** for fallback handling:

```
┌─────────────────────────────────────────────────────────────────┐
│                      BackendManager                              │
│  (Orchestrates providers with automatic fallback)               │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │   NPU   │    │   QNN   │    │   CPU   │
   │Provider │    │Provider │    │Provider │
   └─────────┘    └─────────┘    └─────────┘
        │               │               │
        ▼               ▼               ▼
   AnythingLLM    QAI Hub       llama-cpp
   (NPU Server)   (Direct NPU)   (CPU)
```

## Components

### 1. `LLMProvider` (Abstract Base Class)

Defines the interface that all providers must implement:

```python
from abc import ABC, abstractmethod
from typing import Iterator, List, Dict, Optional

class LLMProvider(ABC):
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
        """Generate complete response (blocking)."""
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
        """Generate streaming response (yields chunks)."""
        pass
```

### 2. `NPUProvider` (AnythingLLM)

Hardware-accelerated inference using AnythingLLM server:

- **Backend**: AnythingLLM HTTP API
- **Hardware**: Snapdragon X Elite NPU
- **Streaming**: ✅ Supported (Server-Sent Events)
- **Use Case**: Primary backend for production

```python
from src.backends import NPUProvider

provider = NPUProvider(
    api_key="your-api-key",
    base_url="http://localhost:3001/api/v1",
    workspace_slug="main",
    stream=True,
    timeout=60.0,
)
```

### 3. `QNNProvider` (Qualcomm Neural Network)

Direct NPU model execution using QAI Hub:

- **Backend**: QAI Hub Models (qai_hub_models)
- **Hardware**: Snapdragon X Elite NPU (direct)
- **Streaming**: ❌ Not supported (falls back to blocking)
- **Use Case**: Alternative NPU backend when AnythingLLM unavailable

```python
from src.backends import QNNProvider

provider = QNNProvider(
    model_path="models/Phi-3.5-Mini-Instruct",
    context_length=1024,
    max_tokens=512,
)
```

### 4. `CPUProvider` (Llama.cpp)

CPU-based fallback using llama-cpp-python:

- **Backend**: llama-cpp-python
- **Hardware**: CPU (no acceleration)
- **Streaming**: ✅ Supported
- **Use Case**: Guaranteed fallback when NPU unavailable

```python
from src.backends import CPUProvider

provider = CPUProvider(
    model_path="models/Phi-3-mini-4k-instruct.Q4_K_M.gguf",
    n_ctx=4096,
    n_gpu_layers=0,  # Pure CPU
    verbose=False,
)
```

### 5. `BackendManager` (Orchestrator)

Manages multiple providers with automatic fallback:

```python
from src.backends import BackendManager, NPUProvider, CPUProvider

# Create providers
npu = NPUProvider(...)
cpu = CPUProvider(...)

# Create manager (priority order: NPU → CPU)
manager = BackendManager(
    providers=[npu, cpu],
    retry_attempts=2,
    retry_delay=1.0,
)

# Generate with automatic fallback
response = manager.generate_response(
    system_prompt="You are a helpful assistant.",
    user_prompt="What is Python?",
)
```

## Usage Examples

### Basic Usage

```python
from src.backends import BackendManager, NPUProvider, CPUProvider

# Initialize providers
npu = NPUProvider(
    api_key="YOUR_API_KEY",
    base_url="http://localhost:3001/api/v1",
    workspace_slug="main",
)
cpu = CPUProvider(model_path="models/phi-3-mini.gguf")

# Create manager with fallback chain
manager = BackendManager(providers=[npu, cpu])

# Generate response (tries NPU first, falls back to CPU on failure)
response = manager.generate_response(
    system_prompt="You are a coding assistant.",
    user_prompt="Explain list comprehensions in Python.",
)
print(response)
```

### Streaming Usage

```python
# Stream response with automatic fallback
for chunk in manager.stream_generate_response(
    system_prompt="You are a helpful assistant.",
    user_prompt="Write a haiku about programming.",
):
    print(chunk, end="", flush=True)
print()  # Newline after streaming
```

### Provider Management

```python
# List all providers
for provider_info in manager.list_providers():
    print(f"{provider_info['name']}: Active={provider_info['active']}")

# Health check all providers
health_status = manager.healthcheck_all()
for name, is_healthy in health_status.items():
    print(f"{name}: {'✓' if is_healthy else '✗'}")

# Switch active provider
manager.set_active_provider_by_name("CPU")
```

### Error Handling

```python
from src.backends import BackendError

try:
    response = manager.generate_response(
        system_prompt="System prompt",
        user_prompt="User query",
        use_fallback=True,  # Enable automatic fallback
    )
except BackendError as e:
    print(f"All backends failed: {e}")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Configuration Integration

### Loading from `config.yaml`

```python
from config_loader import load_configuration
from src.backends import BackendManager, NPUProvider, CPUProvider

# Load configuration
config = load_configuration()

# Initialize NPU provider from config
npu = NPUProvider(
    api_key=config.npu_provider.api_key,
    base_url=config.npu_provider.base_url,
    workspace_slug=config.npu_provider.workspace_slug,
    stream=config.system.streaming_enabled,
    timeout=config.system.stream_timeout,
)

# Initialize CPU provider from config
cpu = CPUProvider(
    model_path=config.cpu_fallback.model_path,
    n_ctx=config.cpu_fallback.n_ctx,
    n_gpu_layers=config.cpu_fallback.n_gpu_layers,
)

# Create manager
manager = BackendManager(providers=[npu, cpu])
```

## Advanced Features

### Custom Retry Logic

```python
manager = BackendManager(
    providers=[npu, qnn, cpu],
    retry_attempts=3,  # Retry each provider 3 times
    retry_delay=2.0,   # Wait 2 seconds between retries (exponential backoff)
)
```

### Disable Fallback

```python
# Only use active provider, don't fall back
response = manager.generate_response(
    system_prompt="...",
    user_prompt="...",
    use_fallback=False,  # Raises error if active provider fails
)
```

### Dynamic Provider Management

```python
from src.backends import QNNProvider

# Start with NPU only
manager = BackendManager(providers=[npu])

# Add QNN provider at runtime
qnn = QNNProvider(model_path="models/qnn-model")
manager.add_provider(qnn, priority=1)  # Insert between NPU and CPU

# Remove provider
manager.remove_provider("QNN")
```

## Type Hints

All classes and methods include comprehensive type hints for IDE support:

```python
from typing import List, Dict, Optional, Iterator

def generate_response(
    self,
    system_prompt: str,
    user_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    *,
    timeout: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
) -> str:
    ...
```

## Testing

### Unit Test Example

```python
import pytest
from src.backends import BackendManager, NPUProvider, BackendError

def test_fallback_on_npu_failure():
    # Mock NPU that always fails
    class FailingNPU(NPUProvider):
        def generate_response(self, *args, **kwargs):
            raise RuntimeError("NPU unavailable")

    # Real CPU provider
    cpu = CPUProvider(model_path="models/test.gguf")

    manager = BackendManager(providers=[FailingNPU(...), cpu])

    # Should fall back to CPU
    response = manager.generate_response(
        system_prompt="Test",
        user_prompt="Hello",
    )

    assert response is not None
    assert manager.get_active_provider().provider_name == "CPU"
```

## Performance Considerations

| Provider | Speed | Quality | Hardware Required | Streaming |
|----------|-------|---------|-------------------|-----------|
| NPU (AnythingLLM) | ⚡⚡⚡ Fast | ⭐⭐⭐ High | Snapdragon X Elite | ✅ Yes |
| QNN | ⚡⚡⚡ Very Fast | ⭐⭐⭐ High | Snapdragon X Elite | ❌ No |
| CPU | ⚡ Slow | ⭐⭐ Medium | Any CPU | ✅ Yes |

## Migration from Legacy Code

### Before (Legacy)

```python
# Old monolithic approach
from selfai.core.anythingllm_interface import AnythingLLMInterface
from selfai.core.local_llm_interface import LocalLLMInterface

# Manual fallback logic
try:
    npu = AnythingLLMInterface(...)
    response = npu.generate_response(...)
except Exception:
    cpu = LocalLLMInterface(...)
    response = cpu.generate_response(...)
```

### After (Refactored)

```python
# New clean abstraction
from src.backends import BackendManager, NPUProvider, CPUProvider

manager = BackendManager(providers=[
    NPUProvider(...),
    CPUProvider(...),
])

# Automatic fallback handled by manager
response = manager.generate_response(...)
```

## Benefits of This Architecture

1. **Separation of Concerns**: Each provider is isolated in its own module
2. **SOLID Principles**:
   - Single Responsibility: Each class has one job
   - Open/Closed: Easy to add new providers without modifying existing code
   - Liskov Substitution: All providers are interchangeable
   - Interface Segregation: Clean, minimal interface
   - Dependency Inversion: Depend on abstractions (LLMProvider)
3. **Type Safety**: Full type hints for IDE support and static analysis
4. **Testability**: Easy to mock and test individual components
5. **Documentation**: Comprehensive docstrings (Google style)
6. **Error Handling**: Graceful degradation with automatic fallback
7. **Extensibility**: Add new providers by implementing `LLMProvider`

## Future Extensions

Potential providers to add:

- `CloudProvider` - OpenAI/Anthropic API
- `VLLMProvider` - vLLM server backend
- `OllamaProvider` - Ollama server backend
- `HuggingFaceProvider` - HuggingFace Transformers

All follow the same interface, just implement `LLMProvider`!

## License

See main project LICENSE file.
