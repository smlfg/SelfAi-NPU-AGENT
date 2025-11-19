# SelfAI Pipeline - Modular Architecture

**Clean, decoupled implementation of the Planner → Executor → Merger pipeline**

---

## Overview

This package provides a **modular, type-safe, UI-agnostic** implementation of the SelfAI three-phase pipeline. Each phase operates independently and communicates via well-defined **Pydantic data models**, ensuring:

- ✅ **Type Safety**: All data structures validated with Pydantic
- ✅ **Testability**: No global state, dependency injection throughout
- ✅ **Decoupling**: No UI dependencies (uses callbacks/protocols)
- ✅ **SOLID Principles**: Single responsibility per module
- ✅ **Clean Code**: Comprehensive docstrings and type hints

---

## Architecture

### Pipeline Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    SelfAI Pipeline v2.0                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. PLANNER (planner.py)                                     │
│     Input:  PlannerContext (agents, goal, memory)           │
│     Output: ExecutionPlan (subtasks, merge strategy)        │
│     ├─ Communicates with Ollama API                         │
│     ├─ Generates DPPM task decomposition                    │
│     └─ Validates plan structure                             │
│                                                              │
│  2. EXECUTOR (executor.py)                                   │
│     Input:  ExecutionPlan                                    │
│     Output: ExecutionResult (subtask results, timing)       │
│     ├─ Executes subtasks via LLM backends                   │
│     ├─ Multi-backend fallback (AnythingLLM→QNN→CPU)        │
│     ├─ Retry logic and error handling                       │
│     └─ Saves results to memory                              │
│                                                              │
│  3. MERGER (merger.py)                                       │
│     Input:  ExecutionPlan + ExecutionResult                  │
│     Output: MergeResult (final synthesized answer)          │
│     ├─ Collects all subtask outputs                         │
│     ├─ Synthesizes via LLM or fallback                      │
│     └─ Saves merged result to memory                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Key Improvements Over Legacy Code

| Aspect | Legacy (`legacy_reference/`) | Refactored (`src/pipeline/`) |
|--------|----------------------------|------------------------------|
| **UI Coupling** | Tightly coupled to `TerminalUI` | UI-agnostic (callbacks) |
| **Type Safety** | Raw dicts everywhere | Pydantic models |
| **Modularity** | 1479-line `selfai.py` | Separate modules |
| **Testability** | Hard to test (UI deps) | Easy to test (protocols) |
| **Data Models** | Unvalidated dicts | Validated Pydantic classes |
| **Documentation** | Minimal docstrings | Google-style comprehensive docs |

---

## Module Structure

### `models.py` - Data Models

**Purpose**: Define all data structures for pipeline communication

**Key Models**:

```python
# Enumerations
ExecutionStatus = Enum("pending", "running", "completed", "failed")
EngineType = Enum("anythingllm", "qnn", "cpu", "smolagent")

# Planner Models
PlannerContext      # Input to planner (agents, goal, memory)
Subtask             # Single task in plan
MergeStrategy       # How to merge results
ExecutionPlan       # Complete plan (subtasks + merge)

# Executor Models
SubtaskResult       # Result of one subtask
ExecutionResult     # All subtask results + metadata

# Merger Models
MergeResult         # Final synthesized output
```

**Validation Features**:
- Unique subtask IDs
- Dependency validation (no circular deps)
- Enum constraints for status/engine
- Length limits for strings (≤160 chars for objectives)

---

### `planner.py` - Task Decomposition

**Purpose**: Generate execution plans from user goals using DPPM methodology

**Core Class**: `Planner`

**Usage Example**:

```python
from src.pipeline import Planner, PlannerConfig, PlannerContext, AgentInfo

# Configure planner
config = PlannerConfig(
    base_url="http://localhost:11434",
    model="gemma3:1b",
    timeout=180.0,
    max_tokens=768,
    temperature=0.1
)

planner = Planner(config)

# Check health
planner.healthcheck()  # Raises PlannerError if unreachable

# Create context
context = PlannerContext(
    agents=[
        AgentInfo(
            key="code_helfer",
            display_name="Code Helper",
            description="Helps with coding tasks"
        )
    ],
    memory_summary="Previous plans: analysis completed",
    available_tools=["read_file", "write_file"],
    goal="Analyze Python code quality"
)

# Generate plan
plan = planner.generate_plan(context, progress_callback=print)
print(f"Generated {len(plan.subtasks)} subtasks")
```

**Key Features**:
- **Streaming Support**: Optional `progress_callback` for real-time plan generation
- **Validation**: Automatic plan structure validation
- **Fallback**: `create_fallback_plan()` for emergency situations
- **Error Handling**: `PlannerError`, `PlanValidationError`, `PlanGenerationError`

**Design Patterns**:
- Dependency Injection (config passed to constructor)
- Protocol-based callbacks (no UI coupling)
- Builder pattern for prompts

---

### `executor.py` - Subtask Execution

**Purpose**: Execute planned subtasks with multi-backend fallback

**Core Class**: `Executor`

**Usage Example**:

```python
from src.pipeline import Executor, ExecutorConfig, BackendConfig

# Configure backends (in priority order)
config = ExecutorConfig(
    backends=[
        BackendConfig(
            interface=anythingllm_interface,
            name="anythingllm",
            label="NPU",
            type="npu"
        ),
        BackendConfig(
            interface=cpu_interface,
            name="cpu",
            label="CPU Fallback",
            type="cpu"
        ),
    ],
    retry_attempts=2,
    retry_delay_seconds=5.0,
    timeout_seconds=120.0,
    max_output_tokens=1024,
    streaming_enabled=True
)

executor = Executor(
    config=config,
    agent_manager=agent_manager,
    memory_system=memory_system
)

# Execute plan
result = executor.execute(plan, progress_callback=my_callback)

print(f"Status: {result.overall_status}")
print(f"Completed in {result.total_execution_time_seconds:.2f}s")
print(f"Failed tasks: {result.failed_subtasks}")
```

**Key Features**:
- **Multi-Backend Fallback**: Automatically tries backends in order
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Streaming**: Supports streaming LLM responses
- **Memory Integration**: Saves all results to memory system
- **Progress Tracking**: Callbacks for start/complete/streaming events

**Protocols**:
- `LLMInterface`: Any LLM backend must implement this
- `AgentInterface`: Agent objects
- `AgentManagerInterface`: Agent management
- `MemorySystemInterface`: Memory persistence
- `ProgressCallback`: UI progress updates (optional)

**Design Patterns**:
- Strategy Pattern (interchangeable backends)
- Chain of Responsibility (backend fallback)
- Observer Pattern (progress callbacks)

---

### `merger.py` - Result Synthesis

**Purpose**: Synthesize subtask results into coherent final answer

**Core Class**: `Merger`

**Usage Example**:

```python
from src.pipeline import Merger, MergerConfig

# Configure merger
config = MergerConfig(
    backend=merge_ollama_interface,
    backend_name="merge-ollama",
    backend_type="local_ollama",
    timeout_seconds=180.0,
    max_tokens=2048,
    streaming_enabled=True,
    fallback_on_error=True
)

merger = Merger(
    config=config,
    agent_manager=agent_manager,
    memory_system=memory_system
)

# Merge results
merge_result = merger.merge(
    plan=execution_plan,
    execution_result=execution_result,
    progress_callback=my_callback
)

print(f"Final answer: {merge_result.final_output}")
print(f"Fallback used: {merge_result.is_fallback}")
print(f"Merge time: {merge_result.merge_time_seconds:.2f}s")
```

**Key Features**:
- **LLM Synthesis**: Uses configured LLM to merge results
- **Fallback Summary**: Automatic fallback if LLM fails
- **Streaming Support**: Real-time merge generation
- **Agent Selection**: Prefers `projektmanager` agent for merge
- **Memory Integration**: Saves merged result

**Protocols**:
- `MergeLLMInterface`: Merge-specific LLM interface
- `ExecutionLLMInterface`: Standard LLM interface (fallback)
- `AgentInterface`, `AgentManagerInterface`, `MemorySystemInterface`
- `ProgressCallback`: Merge progress updates

**Design Patterns**:
- Template Method (merge workflow)
- Strategy Pattern (LLM vs fallback)
- Adapter Pattern (multiple LLM interface types)

---

## Complete Pipeline Example

```python
from src.pipeline import (
    Planner, PlannerConfig, PlannerContext,
    Executor, ExecutorConfig, BackendConfig,
    Merger, MergerConfig,
    AgentInfo
)

# 1. Configure Planner
planner_config = PlannerConfig(
    base_url="http://localhost:11434",
    model="gemma3:1b",
    timeout=180.0
)
planner = Planner(planner_config)

# 2. Configure Executor
executor_config = ExecutorConfig(
    backends=[
        BackendConfig(interface=anythingllm, name="anythingllm", label="NPU"),
        BackendConfig(interface=cpu_llm, name="cpu", label="CPU"),
    ],
    retry_attempts=2,
    timeout_seconds=120.0
)
executor = Executor(executor_config, agent_manager, memory_system)

# 3. Configure Merger
merger_config = MergerConfig(
    backend=merge_ollama,
    backend_name="merge-ollama",
    timeout_seconds=180.0
)
merger = Merger(merger_config, agent_manager, memory_system)

# 4. Run Pipeline
context = PlannerContext(
    agents=[AgentInfo(key="analyst", display_name="Analyst", ...)],
    goal="Analyze quarterly sales data"
)

# Phase 1: Plan
plan = planner.generate_plan(context)
print(f"✓ Plan generated: {len(plan.subtasks)} subtasks")

# Phase 2: Execute
result = executor.execute(plan)
print(f"✓ Execution complete: {result.overall_status}")

# Phase 3: Merge
merge = merger.merge(plan, result)
print(f"✓ Merge complete: {merge.final_output[:100]}...")
```

---

## Comparison with Legacy Code

### Legacy Planner (`legacy_reference/selfai/core/planner_ollama_interface.py`)

**Issues**:
- Returns raw dict (no validation)
- Validation scattered across multiple functions
- Progress callback tightly coupled

**Refactored** (`src/pipeline/planner.py`):
- Returns `ExecutionPlan` (Pydantic validated)
- Single validation point in `_parse_and_validate_plan()`
- Protocol-based callbacks (no coupling)

---

### Legacy Executor (`legacy_reference/selfai/core/execution_dispatcher.py`)

**Issues**:
- Requires `ui` parameter (tight UI coupling)
- Calls `ui.status()`, `ui.streaming_chunk()` directly
- Loads plan from file path (file I/O mixed with logic)
- No return value (updates file in-place)

**Refactored** (`src/pipeline/executor.py`):
- No `ui` parameter (uses optional callbacks)
- Returns `ExecutionResult` (pure data)
- Accepts `ExecutionPlan` object (no file I/O)
- Testable (all I/O through interfaces)

---

### Legacy Merger (in `legacy_reference/selfai/selfai.py`)

**Issues**:
- Embedded in 1479-line main file
- Mixed with orchestration logic
- Direct `ui.status()`, `ui.typing_animation()` calls
- No dedicated module

**Refactored** (`src/pipeline/merger.py`):
- Dedicated module (250 lines, single responsibility)
- Returns `MergeResult` (pure data)
- Optional callbacks (no UI coupling)
- Testable and reusable

---

## Testing Strategy

### Unit Tests

```python
import pytest
from src.pipeline import Planner, PlannerConfig, PlannerContext, AgentInfo

def test_planner_generates_valid_plan():
    config = PlannerConfig(
        base_url="http://localhost:11434",
        model="gemma3:1b",
        timeout=180.0
    )
    planner = Planner(config)

    context = PlannerContext(
        agents=[AgentInfo(key="test", display_name="Test Agent")],
        goal="Test goal"
    )

    # Mock Ollama response
    with patch.object(planner, '_blocking_request') as mock_request:
        mock_request.return_value = '{"subtasks": [...], "merge": {...}}'
        plan = planner.generate_plan(context)

    assert len(plan.subtasks) > 0
    assert plan.merge is not None
```

### Integration Tests

```python
def test_full_pipeline_integration():
    # Setup
    planner = Planner(planner_config)
    executor = Executor(executor_config, agent_manager, memory_system)
    merger = Merger(merger_config, agent_manager, memory_system)

    # Run pipeline
    context = create_test_context()
    plan = planner.generate_plan(context)
    exec_result = executor.execute(plan)
    merge_result = merger.merge(plan, exec_result)

    # Verify
    assert exec_result.overall_status == ExecutionStatus.COMPLETED
    assert merge_result.is_fallback == False
    assert len(merge_result.final_output) > 0
```

---

## Migration Guide

### Migrating from Legacy Code

**Step 1**: Import new pipeline modules

```python
# Old
from selfai.core.planner_ollama_interface import PlannerOllamaInterface
from selfai.core.execution_dispatcher import ExecutionDispatcher

# New
from src.pipeline import Planner, PlannerConfig
from src.pipeline import Executor, ExecutorConfig
```

**Step 2**: Replace config dictionaries with Pydantic models

```python
# Old
planner = PlannerOllamaInterface(
    base_url="http://localhost:11434",
    model="gemma3:1b",
    timeout=180.0,
    max_tokens=768,
    headers={}
)

# New
config = PlannerConfig(
    base_url="http://localhost:11434",
    model="gemma3:1b",
    timeout=180.0,
    max_tokens=768
)
planner = Planner(config)
```

**Step 3**: Remove UI dependencies

```python
# Old
dispatcher = ExecutionDispatcher(
    plan_path=plan_path,
    agent_manager=agent_manager,
    memory_system=memory_system,
    llm_backends=backends,
    ui=ui  # ❌ UI coupling
)

# New
executor = Executor(
    config=executor_config,
    agent_manager=agent_manager,
    memory_system=memory_system
    # ✅ No UI parameter
)
```

**Step 4**: Use callbacks instead of direct UI calls

```python
# Old
ui.status("Task started", "info")

# New
class MyProgressCallback:
    def on_subtask_start(self, subtask_id: str, title: str):
        ui.status(f"Task {subtask_id} started: {title}", "info")

executor.execute(plan, progress_callback=MyProgressCallback())
```

---

## Best Practices

### 1. Use Type Hints Everywhere

```python
def my_function(plan: ExecutionPlan) -> ExecutionResult:
    ...
```

### 2. Validate with Pydantic

```python
# Let Pydantic catch errors early
plan = ExecutionPlan(**plan_data)  # Raises ValidationError if invalid
```

### 3. Use Protocols for Flexibility

```python
# Accept any LLM that implements the protocol
def use_llm(llm: LLMInterface):
    response = llm.generate_response(...)
```

### 4. Dependency Injection

```python
# Inject dependencies via constructor
executor = Executor(config, agent_manager, memory_system)
```

### 5. Progress Callbacks are Optional

```python
# Works with or without callbacks
result = executor.execute(plan)  # Silent
result = executor.execute(plan, progress_callback=my_callback)  # With updates
```

---

## Future Enhancements

### Planned Features

- [ ] **Parallel Execution**: Execute subtasks in parallel based on `parallel_group`
- [ ] **Retry Policies**: Configurable retry strategies (exponential backoff, circuit breaker)
- [ ] **Plan Optimization**: Automatic plan reordering for efficiency
- [ ] **Telemetry**: Built-in metrics collection (latency, token usage)
- [ ] **Async Support**: Async/await for I/O-bound operations
- [ ] **Plan Caching**: Cache similar plans to avoid regeneration

### Extension Points

- **Custom Engines**: Implement `LLMInterface` for new backends
- **Custom Validators**: Add validation logic to `Planner._normalize_plan_data()`
- **Custom Merge Strategies**: Subclass `Merger` for domain-specific merging

---

## API Reference

See individual module docstrings for detailed API documentation:

- [`models.py`](./models.py) - Data model reference
- [`planner.py`](./planner.py) - Planner API
- [`executor.py`](./executor.py) - Executor API
- [`merger.py`](./merger.py) - Merger API

---

## License

Same as parent project (see repository root LICENSE file)

---

## Contributing

When contributing to this pipeline:

1. **Preserve Protocols**: Don't break existing protocols
2. **Add Tests**: All new features need tests
3. **Update Docstrings**: Google-style docstrings required
4. **Type Hints**: All functions must have type annotations
5. **No UI Coupling**: Use callbacks/protocols only

---

**Last Updated**: 2025-01-19
**Version**: 2.0.0 (Refactored)
**Legacy Reference**: `legacy_reference/selfai/`
