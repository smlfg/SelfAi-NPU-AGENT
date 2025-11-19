# Clean Architecture Refactoring Plan

## Executive Summary

This document outlines the refactoring strategy for the SelfAI NPU Agent project, transforming it from a monolithic structure to a clean, modular architecture following SOLID principles.

## Current State Analysis

### Critical Issues

#### 1. **selfai.py (1479 lines)** - God Module
- **Violations**: Single Responsibility Principle (SRP), Open/Closed Principle (OCP)
- **Problems**:
  - Mixed concerns: UI, business logic, I/O, orchestration
  - 40+ functions in global scope
  - Difficult to test in isolation
  - Tight coupling to all infrastructure layers

#### 2. **config_loader.py (440 lines)** - Acceptable but improvable
- **Strengths**: Good use of dataclasses, type hints
- **Issues**:
  - Configuration normalization too complex
  - Mixed validation and transformation logic
  - Hard to extend with new config types

#### 3. **tool_registry.py (661 lines)** - Mixed Concerns
- **Critical Issues**:
  - Tool implementations mixed with registry logic
  - **BUG**: `find_train_connections` registered TWICE (lines 423 and 619)
  - Hard-coded paths violating dependency inversion
  - Impossible to mock for testing

### Dependency Graph Problems

```
Current (Circular/Tangled):
┌─────────────┐
│  selfai.py  │◄─────┐
│   (main)    │      │
└──────┬──────┘      │
       │             │
       ▼             │
┌─────────────┐      │
│ config_     │      │
│ loader.py   │      │
└──────┬──────┘      │
       │             │
       ▼             │
┌─────────────┐      │
│   core/     │──────┘
│  modules    │
└─────────────┘
```

## Target Architecture: Clean Architecture (Hexagonal)

### Layer Structure

```
┌────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
│              (CLI, Commands, Entry Points)                  │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                         │
│          (Use Cases, Services, Orchestration)               │
│  - PlanningService, ExecutionService, MergeService         │
│  - ChatService, AgentSwitchService                         │
└────────────────┬───────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│                     DOMAIN LAYER                            │
│         (Entities, Business Logic, Interfaces)              │
│  - Agent, Plan, Subtask, Conversation                      │
│  - Interfaces: ILLMProvider, IStorage, IUIPresenter        │
└────────────────────────────────────────────────────────────┘
                 ▲
                 │
┌────────────────┴───────────────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                        │
│                (Adapters, Implementations)                  │
│  - LLM Adapters: AnythingLLM, NPU, CPU, Ollama            │
│  - Storage: FileSystemMemoryRepository                     │
│  - Config: YAMLConfigLoader                                │
│  - UI: TerminalUIPresenter                                 │
└────────────────────────────────────────────────────────────┘
```

### Dependency Rule

**Key Principle**: Dependencies point INWARD only.
- Infrastructure → Domain (implements interfaces)
- Application → Domain (uses entities and interfaces)
- Presentation → Application (calls use cases)
- **NEVER**: Domain → Infrastructure

## Refactored Directory Structure

```
selfai/
│
├── domain/                          # CORE BUSINESS LOGIC
│   ├── __init__.py
│   ├── entities/                    # Domain entities
│   │   ├── __init__.py
│   │   ├── agent.py                 # Agent entity with behavior
│   │   ├── plan.py                  # Plan domain model
│   │   ├── subtask.py               # Subtask entity
│   │   ├── conversation.py          # Conversation entity
│   │   └── execution_result.py      # Result wrapper
│   │
│   ├── value_objects/               # Immutable value objects
│   │   ├── __init__.py
│   │   ├── agent_key.py
│   │   ├── plan_metadata.py
│   │   └── execution_status.py
│   │
│   └── interfaces/                  # Abstract interfaces (ports)
│       ├── __init__.py
│       ├── llm_provider.py          # ILLMProvider protocol
│       ├── storage.py               # IStorageRepository protocol
│       ├── ui_presenter.py          # IUIPresenter protocol
│       ├── planner.py               # IPlannerService protocol
│       └── tool_provider.py         # IToolProvider protocol
│
├── application/                     # USE CASES & SERVICES
│   ├── __init__.py
│   ├── services/                    # Application services
│   │   ├── __init__.py
│   │   ├── planning_service.py      # Orchestrates planning phase
│   │   ├── execution_service.py     # Orchestrates execution phase
│   │   ├── merge_service.py         # Orchestrates merge phase
│   │   ├── chat_service.py          # Handles chat interactions
│   │   └── agent_service.py         # Agent management logic
│   │
│   ├── use_cases/                   # Specific use cases
│   │   ├── __init__.py
│   │   ├── create_plan.py           # CreatePlanUseCase
│   │   ├── execute_plan.py          # ExecutePlanUseCase
│   │   ├── merge_results.py         # MergeResultsUseCase
│   │   ├── chat_interaction.py      # ChatInteractionUseCase
│   │   └── switch_agent.py          # SwitchAgentUseCase
│   │
│   └── dto/                         # Data Transfer Objects
│       ├── __init__.py
│       ├── plan_request.py
│       ├── chat_request.py
│       └── execution_response.py
│
├── infrastructure/                  # EXTERNAL ADAPTERS
│   ├── __init__.py
│   │
│   ├── llm/                         # LLM provider implementations
│   │   ├── __init__.py
│   │   ├── base_llm_adapter.py      # Common adapter logic
│   │   ├── anythingllm_adapter.py   # Refactored from anythingllm_interface.py
│   │   ├── npu_adapter.py           # Refactored from npu_llm_interface.py
│   │   ├── cpu_adapter.py           # Refactored from local_llm_interface.py
│   │   ├── ollama_planner_adapter.py
│   │   └── ollama_merge_adapter.py
│   │
│   ├── storage/                     # Storage implementations
│   │   ├── __init__.py
│   │   ├── filesystem_repository.py # Refactored from memory_system.py
│   │   ├── plan_repository.py       # Plan storage logic
│   │   └── state_repository.py      # Active provider state
│   │
│   ├── config/                      # Configuration management
│   │   ├── __init__.py
│   │   ├── models.py                # Config dataclasses (from config_loader)
│   │   ├── loader.py                # YAML loading logic
│   │   ├── validator.py             # Configuration validation
│   │   └── env_resolver.py          # Environment variable resolution
│   │
│   └── ui/                          # UI implementations
│       ├── __init__.py
│       └── terminal_presenter.py    # Refactored from terminal_ui.py
│
├── tools/                           # TOOL SYSTEM
│   ├── __init__.py
│   ├── registry/                    # Tool registration logic
│   │   ├── __init__.py
│   │   ├── tool_registry.py         # Central registry (clean)
│   │   └── tool_wrapper.py          # RegisteredTool wrapper
│   │
│   └── implementations/             # Individual tool implementations
│       ├── __init__.py
│       ├── base_tool.py             # Abstract base tool
│       ├── weather_tool.py
│       ├── calendar_tool.py
│       ├── filesystem_tool.py
│       └── train_tool.py
│
├── presentation/                    # ENTRY POINTS
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                  # Refactored selfai.py (slim)
│   │   └── app_factory.py           # Dependency injection container
│   │
│   └── commands/                    # Command handlers
│       ├── __init__.py
│       ├── base_command.py
│       ├── plan_command.py
│       ├── chat_command.py
│       ├── memory_command.py
│       └── switch_command.py
│
└── core/                            # LEGACY COMPATIBILITY LAYER
    ├── __init__.py                  # (Keep temporarily for gradual migration)
    └── [existing modules]           # Mark as deprecated
```

## Migration Strategy

### Phase 1: Foundation (Domain Layer)
**Goal**: Create pure business logic with no dependencies

**Tasks**:
1. Create `domain/entities/agent.py` with comprehensive docstrings
2. Create `domain/entities/plan.py` with validation logic
3. Create `domain/entities/subtask.py`
4. Create `domain/interfaces/` protocols
5. Add comprehensive type hints and Google-style docstrings

**Success Criteria**: All domain entities testable in isolation

### Phase 2: Application Services
**Goal**: Extract orchestration logic from selfai.py

**Tasks**:
1. Create `application/services/planning_service.py`
   - Extract planning logic from selfai.py
   - Inject dependencies via constructor
2. Create `application/services/execution_service.py`
   - Extract execution dispatcher logic
3. Create `application/services/merge_service.py`
   - Extract merge phase logic

**Success Criteria**: Services are pure, no I/O in logic

### Phase 3: Infrastructure Adapters
**Goal**: Implement interfaces with existing functionality

**Tasks**:
1. Refactor `config_loader.py` → `infrastructure/config/`
   - Separate models, loading, validation
2. Refactor LLM interfaces → `infrastructure/llm/`
   - Implement `ILLMProvider` protocol
3. Refactor `memory_system.py` → `infrastructure/storage/`
   - Implement `IStorageRepository` protocol
4. Refactor `terminal_ui.py` → `infrastructure/ui/`
   - Implement `IUIPresenter` protocol

**Success Criteria**: All adapters swappable via DI

### Phase 4: Tools Modularization
**Goal**: Fix tool registry duplication and separation

**Tasks**:
1. Extract individual tools to `tools/implementations/`
2. Create clean registry in `tools/registry/`
3. Fix duplicate `find_train_connections` registration
4. Remove hard-coded paths

**Success Criteria**: Tools independently testable

### Phase 5: Presentation Layer
**Goal**: Slim main entry point using services

**Tasks**:
1. Create `presentation/cli/main.py` (≤200 lines)
2. Create command handlers
3. Create dependency injection factory
4. Wire all components together

**Success Criteria**: Main.py has no business logic

## SOLID Principles Application

### Single Responsibility Principle (SRP)
**Before**: selfai.py handles UI, planning, execution, merging, I/O
**After**: Each service/entity has ONE reason to change

### Open/Closed Principle (OCP)
**Before**: Adding new LLM requires modifying selfai.py
**After**: Implement `ILLMProvider`, register in DI container

### Liskov Substitution Principle (LSP)
**Before**: Interfaces don't exist, can't substitute
**After**: Any `ILLMProvider` implementation works interchangeably

### Interface Segregation Principle (ISP)
**Before**: Monolithic classes with many methods
**After**: Small, focused interfaces (ILLMProvider, IUIPresenter, etc.)

### Dependency Inversion Principle (DIP)
**Before**: High-level logic depends on low-level details (e.g., direct file access)
**After**: All layers depend on abstractions (interfaces)

## Documentation Standards

### Docstring Template (Google Style)

```python
def execute_subtask(
    self,
    subtask: Subtask,
    llm_provider: ILLMProvider,
    context: ExecutionContext
) -> ExecutionResult:
    """Execute a single subtask using the provided LLM provider.

    This method orchestrates the execution of a subtask by:
    1. Loading relevant context from memory
    2. Constructing the prompt
    3. Calling the LLM provider
    4. Saving the result to storage
    5. Updating task status

    Args:
        subtask: The subtask entity to execute.
        llm_provider: The LLM provider implementation to use.
        context: Execution context containing agent and memory.

    Returns:
        ExecutionResult containing the LLM response and metadata.

    Raises:
        ExecutionError: If the LLM provider fails after all retries.
        ValidationError: If the subtask is invalid or incomplete.

    Example:
        >>> service = ExecutionService(storage=repo, ui=terminal)
        >>> result = service.execute_subtask(task, llm, ctx)
        >>> print(result.output)
        "Task completed successfully"
    """
    # Implementation...
```

### Type Hints Standard

**All functions MUST have**:
1. Parameter type hints
2. Return type hints
3. Generic types where applicable (`list[Agent]`, not `List`)
4. Protocol types for interfaces

```python
from typing import Protocol, Optional
from pathlib import Path

class IStorageRepository(Protocol):
    """Protocol defining storage operations."""

    def save_conversation(
        self,
        agent_key: str,
        user_prompt: str,
        llm_response: str
    ) -> Path:
        """Save a conversation to persistent storage.

        Args:
            agent_key: Unique identifier for the agent.
            user_prompt: The user's input message.
            llm_response: The LLM's generated response.

        Returns:
            Path to the saved conversation file.
        """
        ...
```

## Testing Strategy

### Unit Tests (Domain Layer)
- **Target**: 100% coverage of domain entities
- **No mocking needed**: Pure business logic
- Example: `tests/domain/test_agent.py`

### Integration Tests (Application Layer)
- **Target**: 90% coverage of services
- **Mock**: All infrastructure dependencies
- Example: `tests/application/test_planning_service.py`

### Adapter Tests (Infrastructure Layer)
- **Target**: 80% coverage
- **Integration**: Test with real external systems
- Example: `tests/infrastructure/test_filesystem_repository.py`

## Validation Checklist

Before marking refactoring complete, verify:

- [ ] All new code has comprehensive docstrings (Google style)
- [ ] All functions have complete type hints
- [ ] No circular dependencies (run `pydeps selfai`)
- [ ] All domain entities are pure (no I/O)
- [ ] All services use dependency injection
- [ ] All adapters implement protocols correctly
- [ ] Legacy code still works (functional equivalence)
- [ ] Tool duplication bug fixed
- [ ] No hard-coded paths remain
- [ ] Main entry point is < 200 lines
- [ ] Git branch pushed successfully

## Risk Mitigation

### Breaking Changes
**Risk**: Refactoring breaks existing functionality
**Mitigation**:
1. Keep `legacy_reference/` as ground truth
2. Maintain `selfai/core/` as compatibility layer temporarily
3. Run functional tests comparing old vs new outputs

### Incomplete Migration
**Risk**: Half-refactored codebase is worse than monolith
**Mitigation**:
1. Complete one layer fully before moving to next
2. Each phase must result in working code
3. Use feature flags to toggle between old/new implementations

### Scope Creep
**Risk**: Adding new features during refactoring
**Mitigation**:
1. **STRICT RULE**: No new features, only structural changes
2. Document feature ideas in `FUTURE_ENHANCEMENTS.md`
3. Validate functional equivalence with legacy code

## Timeline Estimate

- **Phase 1 (Domain)**: 2-3 hours
- **Phase 2 (Application)**: 3-4 hours
- **Phase 3 (Infrastructure)**: 4-5 hours
- **Phase 4 (Tools)**: 2-3 hours
- **Phase 5 (Presentation)**: 2-3 hours
- **Validation & Testing**: 2-3 hours

**Total**: ~15-20 hours of focused work

## Success Metrics

### Code Quality
- Lines per file: **< 300** (vs current max 1479)
- Functions per module: **< 20** (vs current 40+)
- Cyclomatic complexity: **< 10 per function**

### Maintainability
- New LLM provider: Add 1 file, register in DI (vs modifying 5 files)
- New command: Add 1 file in `presentation/commands/` (vs modifying main.py)
- Testing: Mock 1 interface (vs mocking 10 globals)

### Documentation
- Docstring coverage: **100%** for public APIs
- Type hint coverage: **100%** for all functions
- Architecture diagram: **Generated from code** (via pydeps)

---

**Document Status**: Draft v1.0
**Last Updated**: 2025-11-19
**Author**: Claude (Senior Software Architect)
