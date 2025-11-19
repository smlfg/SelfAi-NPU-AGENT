# AgentPipeline - CLI Integration Guide

**Date**: 2025-01-19
**Component**: Agent 3 (Pipeline Engineer)
**Status**: ✅ COMPLETE

---

## Overview

The `AgentPipeline` class provides a **CLI-compatible interface** to the refactored Planner→Executor→Merger pipeline. It satisfies the contract expected by `src/cli.py` while maintaining clean separation of concerns and flexibility.

---

## CLI Contract

The CLI expects the following interface:

```python
class AgentPipeline:
    def __init__(self, backend_manager: Any, system_prompt: str = "..."):
        """Initialize pipeline with backend manager and system prompt."""
        ...

    def run(self, user_input: str) -> str:
        """Main entry point for chat loop. Returns final answer."""
        ...

    def clear_memory_global(self) -> None:
        """Clear conversation history and memory."""
        ...
```

---

## Usage

### Basic Usage

```python
from src.pipeline import AgentPipeline

# Create backend manager (provides LLM interfaces)
backend_manager = MyBackendManager()

# Initialize pipeline
pipeline = AgentPipeline(
    backend_manager=backend_manager,
    system_prompt="You are a helpful AI assistant."
)

# Run pipeline
response = pipeline.run("What is Python?")
print(response)

# Clear memory
pipeline.clear_memory_global()
```

---

### With Real Backend

```python
from src.core import load_settings
from src.core.providers import NPUProvider, CPUProvider
from src.pipeline import AgentPipeline

# Load settings
settings = load_settings()

# Create backend manager
class BackendManager:
    def __init__(self):
        self.backends = []

        # Add NPU backend
        try:
            npu = NPUProvider(settings)
            self.backends.append({
                'interface': npu.interface,
                'name': 'npu',
                'label': 'NPU',
                'type': 'npu',
            })
        except Exception:
            pass

        # Add CPU backend (fallback)
        cpu = CPUProvider(settings)
        self.backends.append({
            'interface': cpu.interface,
            'name': 'cpu',
            'label': 'CPU',
            'type': 'cpu',
        })

# Initialize pipeline
backend_manager = BackendManager()
pipeline = AgentPipeline(backend_manager)

# Interactive loop
while True:
    user_input = input("You: ")
    if user_input.lower() == "quit":
        break

    response = pipeline.run(user_input)
    print(f"AI: {response}")
```

---

## Architecture

### Execution Flow

```
User Input (string)
    ↓
AgentPipeline.run(user_input)
    ↓
Decision: Simple or Full Pipeline?
    ├─ Simple (< 10 words): Direct LLM call
    │   └─ backend.generate_response() → Final Answer
    │
    └─ Full (≥ 10 words): Planner → Executor → Merger
        ├─ Planner: Generate execution plan
        ├─ Executor: Run subtasks with tools/backends
        └─ Merger: Synthesize results
        └─ Final Answer (string)
```

---

### Components Used

| Component | Source | Purpose |
|-----------|--------|---------|
| **Planner** | `src.pipeline.planner` | Task decomposition (optional) |
| **Executor** | `src.pipeline.executor` | Subtask execution with backends |
| **Merger** | `src.pipeline.merger` | Result synthesis (optional) |
| **Backends** | Passed via `backend_manager` | LLM interfaces (NPU, QNN, CPU) |

---

## Configuration

### With Settings (Recommended)

If `config.yaml` exists, AgentPipeline will automatically:
- Enable planner (if configured)
- Enable merger (if configured)
- Use configured timeouts and limits

```yaml
# config.yaml
planner:
  enabled: true
  providers:
    - name: "local-ollama"
      type: "local_ollama"
      base_url: "http://localhost:11434"
      model: "gemma3:1b"
      timeout: 180.0
      max_tokens: 768

merge:
  enabled: true
  providers:
    - name: "merge-ollama"
      type: "local_ollama"
      base_url: "http://localhost:11434"
      model: "gemma3:3b"
      timeout: 180.0
      max_tokens: 2048
```

---

### Without Settings (Fallback)

If `config.yaml` is missing, AgentPipeline will:
- Disable planner (use simple execution)
- Disable merger (return first subtask result)
- Still work with direct LLM calls

---

## Backend Manager Contract

The `backend_manager` parameter must provide LLM interfaces. Two formats are supported:

### Format 1: List of Backends

```python
class BackendManager:
    def __init__(self):
        self.backends = [
            {
                'interface': llm_interface,  # Must have generate_response()
                'name': 'backend_name',
                'label': 'Display Label',
                'type': 'backend_type',
            },
            # ... more backends
        ]
```

### Format 2: Direct Interface

```python
class BackendManager:
    def generate_response(self, system_prompt, user_prompt, **kwargs):
        """Direct LLM interface."""
        ...
```

---

## Memory Management

### Conversation History

AgentPipeline maintains in-memory conversation history:

```python
pipeline = AgentPipeline(backend_manager)

# Conversation history is empty
print(len(pipeline.conversation_history))  # 0

# Run some queries
pipeline.run("Hello")
pipeline.run("How are you?")

# History now contains 4 messages (2 exchanges)
print(len(pipeline.conversation_history))  # 4

# Clear history
pipeline.clear_memory_global()
print(len(pipeline.conversation_history))  # 0
```

### History Format

```python
[
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user", "content": "How are you?"},
    {"role": "assistant", "content": "I'm doing well, thank you!"},
]
```

---

## Error Handling

AgentPipeline handles errors gracefully:

```python
try:
    response = pipeline.run("What is Python?")
    print(response)
except Exception as exc:
    # Internal errors are caught and returned as string
    # response will be like: "Sorry, I encountered an error: ..."
    pass
```

**Error Flow**:
1. Exception occurs during pipeline execution
2. Error logged via `src.core.logger`
3. User-friendly error message returned as string
4. Error message added to conversation history

---

## Testing

Run the included test suite:

```bash
python test_agent_pipeline.py
```

**Tests**:
- ✅ Basic functionality (run, clear memory)
- ✅ CLI contract compliance (constructor, methods, return types)
- ✅ Conversation history management
- ✅ Mock backend integration

---

## Integration with CLI

The CLI can import and use AgentPipeline:

```python
# src/cli.py
from src.pipeline import AgentPipeline

# Initialize
pipeline = AgentPipeline(backend_manager, system_prompt="...")

# Chat loop
while True:
    user_input = input("You: ")
    if user_input.lower() in ("quit", "exit"):
        break

    if user_input.lower() == "/clear":
        pipeline.clear_memory_global()
        print("Memory cleared!")
        continue

    response = pipeline.run(user_input)
    print(f"AI: {response}")
```

---

## Advanced Features

### Custom Progress Tracking

AgentPipeline uses internal logging but doesn't expose progress callbacks in the CLI interface. For advanced use cases, use the full `Pipeline` class directly:

```python
from src.pipeline import Pipeline

# Full pipeline with progress callbacks
pipeline = Pipeline(settings, agent_manager, memory_system)

result = pipeline.run(
    goal="Complex task",
    progress_callback=my_callback
)
```

---

### Planner vs Simple Mode

AgentPipeline automatically chooses execution mode:

| Input Length | Mode | Components Used |
|-------------|------|----------------|
| **< 10 words** | Simple | Direct LLM call only |
| **≥ 10 words** | Full | Planner → Executor → Merger |

**Override** by modifying `use_full_pipeline` logic in `run()` method.

---

## Performance Considerations

### Simple Mode (Fast)

- **Latency**: ~1-2 seconds
- **Components**: 1 LLM call
- **Best for**: Quick questions, greetings, clarifications

### Full Pipeline Mode (Comprehensive)

- **Latency**: ~10-30 seconds
- **Components**: Planner + N subtasks + Merger
- **Best for**: Complex tasks, multi-step analysis, research

---

## Comparison with Legacy Agent

| Feature | Legacy `Agent` | New `AgentPipeline` |
|---------|---------------|-------------------|
| **Interface** | `agent.run(messages)` | `pipeline.run(user_input)` |
| **Input** | List of messages | Single string |
| **Output** | String (with tool calls) | String (final answer) |
| **Pipeline** | Tool-calling loop | Planner→Executor→Merger |
| **Memory** | External | Built-in |
| **Backend** | Hardcoded provider | Injected manager |
| **Config** | None | `config.yaml` |

---

## Migration from Legacy

### Before (Legacy)

```python
from selfai.core.agent import Agent

agent = Agent(provider_name="local-ollama")
messages = [{"role": "user", "content": "What is Python?"}]
response = agent.run(messages)
```

### After (Refactored)

```python
from src.pipeline import AgentPipeline

pipeline = AgentPipeline(backend_manager)
response = pipeline.run("What is Python?")
```

---

## Troubleshooting

### Issue: "No module named 'src'"

**Solution**: Ensure you're running from project root or add to PYTHONPATH:
```bash
export PYTHONPATH=/path/to/SelfAi-NPU-AGENT:$PYTHONPATH
python your_script.py
```

---

### Issue: "Configuration file not found"

**Solution**: Either:
1. Create `config.yaml` from template:
   ```bash
   cp config.yaml.template config.yaml
   # Edit config.yaml with your settings
   ```
2. Or ignore (AgentPipeline works without config in simple mode)

---

### Issue: "No LLM backends available"

**Solution**: Ensure `backend_manager` provides valid interfaces:
```python
# Check backend_manager has backends
print(backend_manager.backends)

# Or check it has generate_response method
print(hasattr(backend_manager, 'generate_response'))
```

---

## API Reference

### Constructor

```python
AgentPipeline(
    backend_manager: Any,
    system_prompt: str = "You are a helpful AI assistant."
)
```

**Parameters**:
- `backend_manager`: Backend manager providing LLM interfaces
- `system_prompt`: Default system prompt for LLM interactions

**Raises**:
- `ValueError`: If `backend_manager` has no valid backends

---

### run()

```python
def run(self, user_input: str) -> str
```

**Parameters**:
- `user_input`: User's question or request

**Returns**:
- `str`: Final answer from pipeline

**Behavior**:
1. Adds user input to conversation history
2. Chooses simple or full pipeline mode
3. Executes pipeline
4. Adds response to conversation history
5. Returns final answer as string

---

### clear_memory_global()

```python
def clear_memory_global(self) -> None
```

**Behavior**:
- Clears conversation history
- Clears internal memory system (if applicable)
- Logs memory clear event

---

## Files

**Implementation**:
- `src/pipeline/agent_pipeline.py` (450 lines)

**Tests**:
- `test_agent_pipeline.py` (120 lines)

**Documentation**:
- `AGENT_PIPELINE_GUIDE.md` (this file)

---

## Next Steps

### Immediate
1. ✅ **DONE**: Implement `AgentPipeline`
2. ✅ **DONE**: Test with mock backend
3. **TODO**: Integrate with `src/cli.py` (when ready)

### Short Term
4. **TODO**: Add real backend examples
5. **TODO**: Add streaming support for CLI
6. **TODO**: Add progress indicators

### Long Term
7. **TODO**: Add async support for concurrent execution
8. **TODO**: Add caching for repeated queries
9. **TODO**: Add telemetry and metrics

---

**Last Updated**: 2025-01-19
**Status**: ✅ **COMPLETE** - Ready for CLI integration!
