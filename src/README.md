# SelfAI Refactored Source - Clean Architecture

**A modular, type-safe, testable reimplementation of SelfAI core components**

---

## Overview

This directory contains the **refactored** version of SelfAI's core components, following **clean code principles**, **SOLID design**, and **modern Python best practices**.

The legacy (but functional) code remains in `../legacy_reference/` for reference and fallback.

---

## Why Refactor?

### Problems with Legacy Code

| Issue | Impact | Example |
|-------|--------|---------|
| **God Classes** | Hard to test, maintain | `selfai.py` (1479 lines) |
| **UI Coupling** | Can't reuse logic | `ui.status()` calls everywhere |
| **No Type Safety** | Runtime errors | Raw `dict` everywhere |
| **Mixed Concerns** | Hard to understand | Orchestration + business logic mixed |
| **Poor Testability** | Hard to test | Global state, UI dependencies |

### Goals of Refactoring

✅ **Modularity**: Single responsibility per module
✅ **Type Safety**: Pydantic models + type hints
✅ **Decoupling**: No UI dependencies (protocols/callbacks)
✅ **Testability**: Dependency injection, pure functions
✅ **Documentation**: Comprehensive docstrings
✅ **SOLID Principles**: Clean architecture throughout

---

## Directory Structure

```
src/
├── README.md                    # This file
├── __init__.py                  # Package marker
│
└── pipeline/                    # Core pipeline implementation
    ├── README.md                # Pipeline documentation
    ├── __init__.py              # Package exports
    ├── models.py                # Pydantic data models
    ├── planner.py               # Task decomposition
    ├── executor.py              # Subtask execution
    └── merger.py                # Result synthesis
```

---

## Packages

### `pipeline/` - Core Pipeline

**Purpose**: Modular implementation of Planner → Executor → Merger

**Key Features**:
- ✅ Pydantic data models (type-safe communication)
- ✅ No UI coupling (callbacks via protocols)
- ✅ Multi-backend LLM fallback (AnythingLLM → QNN → CPU)
- ✅ Comprehensive error handling
- ✅ Full type hints and docstrings

**Quick Start**:

```python
from src.pipeline import (
    Planner, PlannerConfig, PlannerContext,
    Executor, ExecutorConfig,
    Merger, MergerConfig
)

# Configure pipeline
planner = Planner(PlannerConfig(...))
executor = Executor(ExecutorConfig(...), agent_manager, memory_system)
merger = Merger(MergerConfig(...), agent_manager, memory_system)

# Run pipeline
context = PlannerContext(agents=[...], goal="...")
plan = planner.generate_plan(context)
result = executor.execute(plan)
merged = merger.merge(plan, result)
```

See [`pipeline/README.md`](./pipeline/README.md) for detailed documentation.

---

## Design Principles

### 1. Single Responsibility Principle (SRP)

Each module has one clear purpose:

- `planner.py` - Generate plans (only)
- `executor.py` - Execute subtasks (only)
- `merger.py` - Merge results (only)
- `models.py` - Define data structures (only)

**Anti-pattern** (legacy):
```python
# selfai.py does EVERYTHING:
# - UI management
# - Plan generation
# - Execution orchestration
# - Merge logic
# - Memory management
# - Backend switching
# - Configuration loading
```

**Clean pattern** (refactored):
```python
# Each concern in its own module
from src.pipeline import Planner  # Only planning
from src.pipeline import Executor # Only execution
from src.pipeline import Merger   # Only merging
```

---

### 2. Open/Closed Principle (OCP)

Open for extension, closed for modification.

**Example**: Adding new LLM backends

```python
# No need to modify Executor code
class MyCustomLLM:
    def generate_response(self, system_prompt, user_prompt, ...):
        # Custom implementation
        ...

    def stream_generate_response(self, ...):
        # Custom implementation
        ...

# Just pass it to executor
config = ExecutorConfig(
    backends=[
        BackendConfig(interface=MyCustomLLM(), name="custom", ...),
    ]
)
executor = Executor(config, ...)
```

---

### 3. Liskov Substitution Principle (LSP)

Any LLM implementing `LLMInterface` protocol can replace another.

```python
# Protocol defines contract
class LLMInterface(Protocol):
    def generate_response(...) -> str: ...
    def stream_generate_response(...) -> Iterable[str]: ...

# All implementations are interchangeable
backends = [
    BackendConfig(interface=AnythingLLM(), ...),
    BackendConfig(interface=QNN_LLM(), ...),
    BackendConfig(interface=CPU_LLM(), ...),
]
```

---

### 4. Interface Segregation Principle (ISP)

Clients shouldn't depend on interfaces they don't use.

**Example**: Separate protocols for different needs

```python
# Executor only needs these methods
class AgentManagerInterface(Protocol):
    def get(self, key: str) -> Optional[AgentInterface]: ...

# Doesn't force implementation of unused methods like:
# - list_agents()
# - switch_agent()
# - load_agent_from_disk()
```

---

### 5. Dependency Inversion Principle (DIP)

Depend on abstractions, not concretions.

**Legacy** (depends on concrete `TerminalUI`):
```python
class ExecutionDispatcher:
    def __init__(self, ..., ui: TerminalUI):
        self.ui = ui  # ❌ Concrete dependency

    def run(self):
        self.ui.status("Starting...", "info")  # ❌ Tight coupling
```

**Refactored** (depends on abstract `ProgressCallback`):
```python
class Executor:
    def execute(
        self,
        plan: ExecutionPlan,
        progress_callback: Optional[ProgressCallback] = None  # ✅ Abstract
    ):
        if progress_callback:
            progress_callback.on_subtask_start(...)  # ✅ Decoupled
```

---

## Type Safety

### Pydantic Models

All data structures use Pydantic for validation:

```python
from src.pipeline.models import ExecutionPlan, Subtask

# Automatic validation
plan = ExecutionPlan(
    subtasks=[
        Subtask(
            id="S1",
            title="Analyze data",
            objective="Perform statistical analysis",
            agent_key="analyst",
            engine=EngineType.ANYTHINGLLM,
            parallel_group=1
        )
    ],
    merge=MergeStrategy(strategy="Combine results")
)

# Invalid data raises ValidationError
try:
    bad_plan = ExecutionPlan(
        subtasks=[
            Subtask(id="Invalid")  # ❌ Missing required fields
        ]
    )
except ValidationError as e:
    print(e)
```

### Type Hints

Every function has comprehensive type annotations:

```python
def generate_plan(
    self,
    context: PlannerContext,
    progress_callback: Optional[ProgressCallback] = None,
) -> ExecutionPlan:
    """Generate an execution plan.

    Args:
        context: Planning context with agents and goal
        progress_callback: Optional callback for progress

    Returns:
        Validated execution plan

    Raises:
        PlanGenerationError: If generation fails
    """
    ...
```

---

## Testability

### Unit Testing

Clean architecture makes unit testing trivial:

```python
import pytest
from unittest.mock import Mock
from src.pipeline import Executor, ExecutorConfig, BackendConfig

def test_executor_fallback():
    # Mock backends
    failing_backend = Mock()
    failing_backend.generate_response.side_effect = Exception("Failed")

    working_backend = Mock()
    working_backend.generate_response.return_value = "Success"

    # Configure executor
    config = ExecutorConfig(
        backends=[
            BackendConfig(interface=failing_backend, name="fail", label="Fail"),
            BackendConfig(interface=working_backend, name="work", label="Work"),
        ]
    )

    # Mock dependencies
    agent_manager = Mock()
    memory_system = Mock()

    executor = Executor(config, agent_manager, memory_system)

    # Execute
    result = executor.execute(test_plan)

    # Verify fallback worked
    assert result.overall_status == ExecutionStatus.COMPLETED
    assert working_backend.generate_response.called
```

### Integration Testing

```python
def test_full_pipeline_integration():
    # Real components, real flow
    planner = Planner(planner_config)
    executor = Executor(executor_config, agent_manager, memory_system)
    merger = Merger(merger_config, agent_manager, memory_system)

    # Run end-to-end
    context = create_test_context()
    plan = planner.generate_plan(context)
    exec_result = executor.execute(plan)
    merge_result = merger.merge(plan, exec_result)

    # Verify complete pipeline
    assert exec_result.overall_status == ExecutionStatus.COMPLETED
    assert not merge_result.is_fallback
```

---

## Documentation Standards

### Google-Style Docstrings

All classes and functions follow Google style:

```python
def merge(
    self,
    plan: ExecutionPlan,
    execution_result: ExecutionResult,
    *,
    progress_callback: Optional[ProgressCallback] = None,
) -> MergeResult:
    """Merge all subtask results into a final answer.

    This method synthesizes all subtask outputs using the merge strategy
    defined in the execution plan. It uses the configured LLM backend
    to generate a coherent final answer, with automatic fallback to
    internal summarization if the LLM fails.

    Args:
        plan: Original execution plan with merge strategy
        execution_result: Execution results to merge
        progress_callback: Optional callback for progress updates

    Returns:
        MergeResult containing the final synthesized output

    Raises:
        MergeError: If merge fails and fallback is disabled

    Example:
        ```python
        merger = Merger(config, agent_manager, memory_system)
        result = merger.merge(plan, exec_result, progress_callback=my_callback)
        print(f"Final answer: {result.final_output}")
        ```
    """
    ...
```

---

## Migration Strategy

### Phase 1: Coexistence (Current)

Both legacy and refactored code exist:

```
Project Root
├── legacy_reference/        # Original working code
│   └── selfai/
│       ├── core/
│       │   ├── planner_ollama_interface.py
│       │   ├── execution_dispatcher.py
│       │   └── merge_ollama_interface.py
│       └── selfai.py        # Main orchestrator
│
└── src/                     # Refactored code
    └── pipeline/
        ├── planner.py       # ✅ Clean
        ├── executor.py      # ✅ Clean
        └── merger.py        # ✅ Clean
```

**Strategy**: Validate refactored code against legacy before replacing.

---

### Phase 2: Gradual Replacement

Replace legacy components one by one:

1. ✅ **Pipeline Core** (this refactoring)
   - `planner.py` replaces `planner_ollama_interface.py`
   - `executor.py` replaces `execution_dispatcher.py`
   - `merger.py` replaces `_execute_merge_phase()` in `selfai.py`

2. 🔄 **Agent System** (next)
   - Extract `AgentManager` logic
   - Clean up `Agent` class
   - Modularize agent loading

3. 🔄 **Memory System** (next)
   - Extract memory management
   - Add structured storage
   - Implement efficient retrieval

4. 🔄 **LLM Interfaces** (next)
   - Standardize interface protocols
   - Extract configuration
   - Add backend registry

5. 🔄 **Orchestration** (final)
   - Rewrite `selfai.py` using new components
   - Add CLI framework
   - Implement proper async support

---

### Phase 3: Legacy Deprecation

Once validated:
- Move `legacy_reference/` to `archive/`
- Update all imports to use `src/`
- Remove deprecated code

---

## Performance Considerations

### Memory Usage

**Legacy**:
- Large monolithic classes stay in memory
- No lazy loading
- Global state

**Refactored**:
- Smaller, focused classes
- Lazy initialization via config
- No global state (everything injected)

---

### Execution Speed

**Legacy**:
- Streaming tightly coupled to UI (slower)
- No parallel execution
- Retry logic hardcoded

**Refactored**:
- Streaming via callbacks (faster)
- Parallel execution ready (via `parallel_group`)
- Configurable retry strategies

---

## Security Improvements

### Input Validation

**Legacy**: Raw dicts, no validation
```python
# Anyone can pass anything
plan_data = {"subtasks": "not a list"}  # ❌ No validation
```

**Refactored**: Pydantic validation
```python
# Automatic validation
plan = ExecutionPlan(**plan_data)  # ✅ Raises ValidationError if invalid
```

---

### Secret Management

**Legacy**: Secrets mixed with code
```python
# Hardcoded or in global config
API_KEY = "sk-..."  # ❌ Dangerous
```

**Refactored**: Inject via config
```python
# Passed at runtime, never hardcoded
config = PlannerConfig(
    base_url=os.getenv("OLLAMA_URL"),
    headers={"Authorization": f"Bearer {os.getenv('API_KEY')}"}
)
```

---

## Future Refactoring Targets

### High Priority

1. **Agent System** (`selfai/core/agent_manager.py`)
   - Extract agent loading logic
   - Create `AgentRegistry` class
   - Implement lazy loading

2. **Memory System** (`selfai/core/memory_system.py`)
   - Add structured storage (SQLite?)
   - Implement efficient search (vector DB?)
   - Add memory policies (retention, cleanup)

3. **Configuration** (`config_loader.py`)
   - Use Pydantic settings
   - Add validation
   - Support multiple config sources

---

### Medium Priority

4. **LLM Interfaces**
   - Standardize all interfaces
   - Create backend registry
   - Add health checks

5. **Tool System** (`selfai/tools/`)
   - Clean up tool registry
   - Add tool validation
   - Implement tool categories

---

### Low Priority

6. **UI Layer** (`selfai/ui/terminal_ui.py`)
   - Extract from core logic
   - Create UI abstraction
   - Support multiple UIs (CLI, Web, TUI)

7. **Main Orchestrator** (`selfai/selfai.py`)
   - Rewrite using new components
   - Add proper CLI framework (Click/Typer)
   - Implement async/await

---

## Contributing Guidelines

When adding to `src/`:

### Code Style

- ✅ Use **Black** for formatting
- ✅ Use **isort** for import sorting
- ✅ Use **mypy** for type checking
- ✅ Follow **PEP 8** naming conventions

### Documentation

- ✅ Google-style docstrings for all public APIs
- ✅ Type hints on all function signatures
- ✅ Update README when adding new modules

### Testing

- ✅ Write unit tests for all new code
- ✅ Aim for >80% coverage
- ✅ Add integration tests for pipelines

### Architecture

- ✅ Follow SOLID principles
- ✅ Use dependency injection
- ✅ Avoid global state
- ✅ Protocol-based interfaces

---

## Resources

### Internal Documentation

- [Pipeline Architecture](./pipeline/README.md)
- [Legacy Reference](../legacy_reference/)
- [Architecture Summary](../ARCHITECTURE_SUMMARY.txt)

### External References

- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Python Type Hints (PEP 484)](https://peps.python.org/pep-0484/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)

---

**Maintained By**: SelfAI Refactoring Team
**Last Updated**: 2025-01-19
**Status**: 🟢 Active Development
