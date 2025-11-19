# SelfAI Refactoring Design Document

## Executive Summary

This document outlines the refactoring strategy for `selfai/selfai.py` (1478 lines), which currently violates multiple SOLID principles and exhibits classic "god class" anti-patterns.

**Goal**: Transform the monolithic `main()` function (811 lines) into a modular, maintainable, and testable architecture while ensuring **functional equivalence** with the original code.

---

## Current Architecture Analysis

### File: `selfai/selfai.py` - 1478 lines

**The main() Function** (lines 667-1478, ~811 lines):

#### Responsibilities Identified:

1. **Initialization** (~60 lines)
   - UI setup
   - Agent manager setup
   - Memory system setup
   - Configuration loading

2. **Provider Management** (~100 lines)
   - Planner provider initialization (Ollama)
   - Merge provider initialization (Ollama)
   - Provider state persistence

3. **Backend Management** (~50 lines)
   - AnythingLLM backend loading
   - QNN backend loading
   - CPU fallback backend loading

4. **Agent Selection** (~30 lines)
   - Default agent selection
   - Fallback logic

5. **Command Loop** (~570 lines)
   - `/memory` command handler
   - `/memory clear` command handler
   - `/planner list` and `/planner use` command handlers
   - `/plan` command handler (**~350 lines!**)
   - `/switch` command handler
   - Default chat handler with backend fallback

#### Nested Functions:
- `_generate_with_backend()` (inside main)
- `_planner_stream()` callback (inside main)

---

## SOLID Violations Identified

### 1. **Single Responsibility Principle (SRP) - VIOLATED**

The `main()` function has **at least 10 distinct responsibilities**:
- System initialization
- Configuration management
- Provider lifecycle management
- Backend lifecycle management
- Command parsing
- Command routing
- Plan generation
- Plan execution
- Merge orchestration
- Conversation management

**Impact**: Any change to one responsibility requires modifying this massive function, increasing risk and complexity.

### 2. **Open/Closed Principle (OCP) - VIOLATED**

Adding a new command (e.g., `/export`, `/config`) requires:
- Modifying the main loop
- Adding more if/elif statements
- Increasing function complexity

**Impact**: Not extensible without modification.

### 3. **Dependency Inversion Principle (DIP) - VIOLATED**

The `main()` function directly instantiates all dependencies:
- Hard-coded backend loading
- Direct provider initialization
- Tight coupling to concrete implementations

**Impact**: Difficult to test, difficult to mock, difficult to swap implementations.

### 4. **God Class Anti-Pattern**

The file contains 26+ functions, many of which are tightly coupled to the main loop's state.

---

## Proposed Refactored Architecture

### New Directory Structure:

```
selfai/
├── __init__.py
├── selfai.py                       # NEW: Thin entry point (< 50 lines)
│
├── core/
│   ├── application.py              # NEW: Application orchestrator
│   ├── initialization.py           # NEW: System initialization
│   ├── backend_factory.py          # NEW: Backend creation (factory pattern)
│   ├── provider_factory.py         # NEW: Provider creation (factory pattern)
│   ├── conversation_handler.py     # NEW: Chat conversation logic
│   ├── [existing files...]
│
├── commands/
│   ├── __init__.py
│   ├── base_command.py             # NEW: Abstract command interface
│   ├── memory_command.py           # NEW: /memory handler
│   ├── planner_command.py          # NEW: /planner handler
│   ├── plan_command.py             # NEW: /plan handler
│   ├── switch_command.py           # NEW: /switch handler
│   ├── command_registry.py         # NEW: Command registration & dispatch
│
├── services/
│   ├── __init__.py
│   ├── plan_service.py             # NEW: Plan generation logic
│   ├── execution_service.py        # NEW: Plan execution logic
│   ├── merge_service.py            # NEW: Merge phase logic
│   ├── state_service.py            # NEW: Provider state persistence
│
├── tools/
│   └── [existing files...]
│
└── ui/
    └── terminal_ui.py              # Existing, minimal changes
```

---

## Refactoring Strategy: Phase-by-Phase

### Phase 1: Extract Service Layer

**Goal**: Move business logic out of main() into dedicated services.

**New Files**:

1. **`services/state_service.py`**
   - Extract: `_planner_state_path()`, `_load_active_planner()`, `_save_active_planner()`
   - Extract: `_merge_state_path()`, `_load_active_merge()`, `_save_active_merge()`
   - Extract: `_load_plan_file()`, `_save_plan_file()`, `_read_result_file()`

   ```python
   class StateService:
       """Manages persistence of provider and plan state."""

       def __init__(self, memory_system: MemorySystem):
           """Initialize state service with memory system."""

       def load_active_planner(self) -> str | None:
           """Load the active planner provider name from state."""

       def save_active_planner(self, provider_name: str) -> None:
           """Save the active planner provider name to state."""
   ```

2. **`services/plan_service.py`**
   - Extract: `_build_fallback_plan()`, `_sanitize_plan_agents()`, `_announce_plan_agents()`
   - Extract: `_build_planner_context()`

   ```python
   class PlanService:
       """Handles plan creation and validation."""

       def __init__(self, agent_manager: AgentManager, memory_system: MemorySystem):
           """Initialize plan service."""

       def build_planner_context(self) -> PlannerContext:
           """Build context for planner with agent and memory info."""

       def build_fallback_plan(self, goal_text: str, agent_key: str) -> dict:
           """Create a fallback plan when planner fails."""

       def sanitize_plan_agents(self, plan_data: dict) -> None:
           """Validate and fix agent keys in plan."""
   ```

3. **`services/merge_service.py`**
   - Extract: `_execute_merge_phase()`, `_select_merge_backend()`, `_select_merge_agent_from_plan()`
   - Extract: `_collect_subtask_entries()`, `_render_fallback_merge()`

   ```python
   class MergeService:
       """Orchestrates the merge phase of plan execution."""

       def __init__(self, memory_system: MemorySystem, ui: TerminalUI):
           """Initialize merge service."""

       def execute_merge_phase(
           self,
           plan_path: Path,
           merge_backend: dict,
           agent_manager: AgentManager,
           execution_timeout: float | None = None,
       ) -> bool:
           """Execute merge phase with given backend."""
   ```

### Phase 2: Extract Factory Pattern for Backend/Provider Creation

**New Files**:

1. **`core/backend_factory.py`**
   - Extract: `_load_anythingllm()`, `_load_qnn()`, `_load_cpu()`

   ```python
   class BackendFactory:
       """Factory for creating LLM backend instances."""

       def __init__(self, models_root: Path, ui: TerminalUI):
           """Initialize backend factory."""

       def create_anythingllm_backend(
           self, config: AppConfig, streaming_enabled: bool
       ) -> tuple[AnythingLLMInterface | None, str | None]:
           """Create AnythingLLM backend if configured."""

       def create_qnn_backend(
           self
       ) -> tuple[NpuLLMInterface | None, str | None]:
           """Create QNN backend if available."""

       def create_cpu_backend(
           self
       ) -> tuple[LocalLLMInterface | None, str | None]:
           """Create CPU fallback backend."""

       def create_all_backends(
           self, config: AppConfig | None, streaming_enabled: bool
       ) -> list[dict[str, object]]:
           """Create all available backends in priority order."""
   ```

2. **`core/provider_factory.py`**
   - Extract planner provider initialization logic
   - Extract merge provider initialization logic

   ```python
   class ProviderFactory:
       """Factory for creating planner and merge provider instances."""

       def __init__(self, ui: TerminalUI):
           """Initialize provider factory."""

       def create_planner_providers(
           self, planner_cfg: PlannerConfig
       ) -> tuple[dict[str, dict], list[str]]:
           """Create all planner providers from config."""

       def create_merge_providers(
           self, merge_cfg: MergeConfig
       ) -> tuple[dict[str, dict], list[str]]:
           """Create all merge providers from config."""
   ```

### Phase 3: Command Pattern for User Commands

**New Files**:

1. **`commands/base_command.py`**

   ```python
   from abc import ABC, abstractmethod
   from typing import Any

   class BaseCommand(ABC):
       """Abstract base class for all commands."""

       @property
       @abstractmethod
       def name(self) -> str:
           """Command name (e.g., 'memory', 'plan')."""

       @property
       @abstractmethod
       def aliases(self) -> list[str]:
           """Command aliases (e.g., ['mem', 'm'])."""

       @abstractmethod
       def execute(self, args: str, context: dict[str, Any]) -> bool:
           """
           Execute the command.

           Args:
               args: Raw argument string after command name
               context: Shared context (agent_manager, memory_system, etc.)

           Returns:
               True to continue loop, False to exit
           """
   ```

2. **`commands/memory_command.py`**

   ```python
   class MemoryCommand(BaseCommand):
       """Handles /memory and /memory clear commands."""

       @property
       def name(self) -> str:
           return "memory"

       @property
       def aliases(self) -> list[str]:
           return ["mem"]

       def execute(self, args: str, context: dict[str, Any]) -> bool:
           """Execute memory command."""
   ```

3. **`commands/plan_command.py`**

   ```python
   class PlanCommand(BaseCommand):
       """Handles /plan <goal> command - the most complex command."""

       def __init__(self, plan_service: PlanService, merge_service: MergeService):
           """Initialize with required services."""

       @property
       def name(self) -> str:
           return "plan"

       def execute(self, args: str, context: dict[str, Any]) -> bool:
           """Execute plan creation and execution."""
   ```

4. **`commands/command_registry.py`**

   ```python
   class CommandRegistry:
       """Registry and dispatcher for user commands."""

       def __init__(self):
           """Initialize command registry."""
           self._commands: dict[str, BaseCommand] = {}

       def register(self, command: BaseCommand) -> None:
           """Register a command."""

       def dispatch(self, user_input: str, context: dict[str, Any]) -> bool:
           """
           Parse and dispatch user input to appropriate command.

           Returns:
               True to continue loop, False to exit
           """
   ```

### Phase 4: Application Orchestrator

**New Files**:

1. **`core/initialization.py`**

   ```python
   from dataclasses import dataclass
   from pathlib import Path
   from typing import Any

   @dataclass
   class ApplicationContext:
       """Container for all application dependencies."""
       ui: TerminalUI
       agent_manager: AgentManager
       memory_system: MemorySystem
       config: AppConfig | None
       execution_backends: list[dict[str, object]]
       planner_providers: dict[str, dict[str, object]]
       planner_provider_order: list[str]
       active_planner_provider: str | None
       merge_providers: dict[str, dict[str, object]]
       merge_provider_order: list[str]
       active_merge_provider: str | None
       streaming_enabled: bool

   class ApplicationInitializer:
       """Initializes all application components."""

       def __init__(self, project_root: Path):
           """Initialize with project root path."""
           self.project_root = project_root

       def initialize(self) -> ApplicationContext:
           """
           Initialize all application components.

           Returns:
               ApplicationContext with all initialized components

           Raises:
               RuntimeError: If critical initialization fails
           """
   ```

2. **`core/application.py`**

   ```python
   class SelfAIApplication:
       """Main application orchestrator."""

       def __init__(self, context: ApplicationContext):
           """Initialize application with context."""
           self.context = context
           self._setup_commands()

       def _setup_commands(self) -> None:
           """Register all available commands."""

       def run(self) -> None:
           """Run the main application loop."""
   ```

3. **`core/conversation_handler.py`**

   ```python
   class ConversationHandler:
       """Handles regular chat conversations (non-command messages)."""

       def __init__(
           self,
           agent_manager: AgentManager,
           memory_system: MemorySystem,
           execution_backends: list[dict[str, object]],
           ui: TerminalUI,
           streaming_enabled: bool,
       ):
           """Initialize conversation handler."""

       def handle_message(self, user_input: str) -> None:
           """
           Process a user message and generate response.

           Args:
               user_input: The user's message
           """
   ```

4. **`selfai/selfai.py`** (NEW - Thin entry point)

   ```python
   """SelfAI - AI-powered terminal chatbot with multi-backend support."""

   import sys
   from pathlib import Path

   # Add project root to path
   project_root = Path(__file__).resolve().parent
   sys.path.insert(0, str(project_root.parent))

   from selfai.core.initialization import ApplicationInitializer
   from selfai.core.application import SelfAIApplication

   def main() -> None:
       """Application entry point."""
       project_root_path = Path(__file__).resolve().parent

       # Initialize all components
       initializer = ApplicationInitializer(project_root_path)
       context = initializer.initialize()

       # Run application
       app = SelfAIApplication(context)
       app.run()

   if __name__ == "__main__":
       main()
   ```

---

## Type Hints and Docstrings Standard

All new code will follow:

### Type Hints:
- **All** function parameters must have type hints
- **All** return types must be specified
- Use `typing` module for complex types: `list[dict[str, object]]`, `tuple[str | None, bool]`
- Use `| None` for optional types (Python 3.10+ syntax)

### Docstrings (Google Style):

```python
def example_function(param1: str, param2: int | None = None) -> tuple[bool, str]:
    """
    Brief description of what the function does.

    Longer description if needed. This can span multiple lines and explain
    the function's behavior in detail.

    Args:
        param1: Description of param1
        param2: Description of param2 (optional, defaults to None)

    Returns:
        Tuple of (success_flag, result_message)
        - success_flag: True if operation succeeded
        - result_message: Human-readable result message

    Raises:
        ValueError: If param1 is empty
        RuntimeError: If the operation fails critically

    Examples:
        >>> example_function("test", 42)
        (True, "Operation succeeded")
    """
```

---

## Migration Phases - Detailed Steps

### Step 1: Create Service Layer (Day 1)

1. Create `selfai/services/` directory
2. Implement `state_service.py` with full docstrings + type hints
3. Implement `plan_service.py` with full docstrings + type hints
4. Implement `merge_service.py` with full docstrings + type hints
5. **DO NOT** modify `selfai.py` yet - just create new files

### Step 2: Create Factories (Day 1-2)

1. Implement `core/backend_factory.py` with full docstrings + type hints
2. Implement `core/provider_factory.py` with full docstrings + type hints
3. **DO NOT** modify `selfai.py` yet

### Step 3: Create Command System (Day 2-3)

1. Create `selfai/commands/` directory
2. Implement `base_command.py` (abstract interface)
3. Implement `memory_command.py`
4. Implement `planner_command.py`
5. Implement `switch_command.py`
6. Implement `plan_command.py` (most complex - uses plan_service, merge_service)
7. Implement `command_registry.py`
8. **DO NOT** modify `selfai.py` yet

### Step 4: Create Application Layer (Day 3-4)

1. Implement `core/initialization.py` (ApplicationContext dataclass, ApplicationInitializer)
2. Implement `core/conversation_handler.py`
3. Implement `core/application.py` (SelfAIApplication)

### Step 5: Replace main() (Day 4)

1. **BACKUP**: Ensure `legacy_reference/selfai/selfai.py` exists
2. **CREATE**: New thin `selfai/selfai.py` with just imports + main()
3. **MOVE**: Old selfai.py to `legacy_reference/` if not already there
4. **TEST**: Run new code and verify functional equivalence

### Step 6: Testing & Validation (Day 5)

1. Manual testing: All commands work identically
2. Compare outputs between old and new implementation
3. Test edge cases (missing config, backend failures, etc.)
4. Verify memory persistence works
5. Verify plan execution works

---

## Benefits of Refactored Architecture

### Maintainability
- **Single Responsibility**: Each class has one clear purpose
- **Small Units**: No function > 100 lines, no class > 300 lines
- **Clear Naming**: Intent-revealing names throughout

### Testability
- **Dependency Injection**: All dependencies passed via constructor
- **Mockable**: Interfaces can be mocked for unit testing
- **Isolated Logic**: Business logic separated from I/O

### Extensibility
- **New Commands**: Just create a new `BaseCommand` subclass and register
- **New Backends**: Just extend `BackendFactory`
- **New Providers**: Just extend `ProviderFactory`

### Documentation
- **Every Class**: Comprehensive docstring
- **Every Method**: Google-style docstring with Args, Returns, Raises
- **Every Parameter**: Type-hinted

---

## Risks & Mitigation

### Risk 1: Functional Regression
**Mitigation**:
- Keep `legacy_reference/` untouched
- Test each command side-by-side
- Use identical test scenarios

### Risk 2: Performance Degradation
**Mitigation**:
- Minimize abstraction overhead
- Use dataclasses (fast)
- Avoid deep call stacks

### Risk 3: Breaking Changes
**Mitigation**:
- Keep `selfai/selfai.py` as entry point (same usage)
- Internal changes only
- No API changes for end users

---

## Success Criteria

1. ✅ **No file > 300 lines**
2. ✅ **No function > 100 lines**
3. ✅ **All functions have type hints**
4. ✅ **All classes/functions have Google-style docstrings**
5. ✅ **Legacy code remains in `legacy_reference/`**
6. ✅ **Functional equivalence verified**
7. ✅ **All commands work identically**
8. ✅ **Code passes basic smoke tests**

---

## Timeline Estimate

- **Day 1**: Services + Factories (6-8 hours)
- **Day 2**: Command system (6-8 hours)
- **Day 3**: Application layer (4-6 hours)
- **Day 4**: Integration + new main() (4-6 hours)
- **Day 5**: Testing + validation (4-6 hours)

**Total**: 24-34 hours of focused work

---

## Next Steps

1. Review this design document
2. Get approval to proceed
3. Start with Phase 1: Service Layer extraction

---

**Document Version**: 1.0
**Last Updated**: 2025-11-19
**Status**: Ready for Review
