# AI NPU Agent - Refactoring Guide

## Overview

This document describes the refactored infrastructure for the AI NPU Agent project, following Clean Code principles and SOLID design patterns.

## Refactoring Goals

1. **Safety**: Preserve all functional behavior from legacy code
2. **Structure**: Eliminate "god classes" through strict modularization
3. **Documentation**: Comprehensive docstrings (Google Style) and type hints
4. **Maintainability**: Clean separation of concerns following SOLID principles

## Architecture Changes

### Legacy vs. Refactored Structure

```
BEFORE (legacy_reference/):
├── config_loader.py        # Monolithic configuration loader
├── selfai/
│   ├── core/               # Mixed responsibilities
│   └── ...

AFTER (src/):
├── core/                   # Core infrastructure
│   ├── config.py           # Pydantic-based configuration
│   ├── logger.py           # Structured logging
│   ├── exceptions.py       # Custom exception hierarchy
│   └── __init__.py         # Public API
└── __init__.py
```

## Module Documentation

### 1. Configuration System (`src/core/config.py`)

**Purpose**: Type-safe, validated configuration management using Pydantic BaseSettings.

**Key Features**:
- Automatic validation with helpful error messages
- Environment variable interpolation (`${VAR_NAME}`)
- YAML configuration file support
- Backward compatibility with legacy formats
- Full IDE autocomplete support

**Migration from Legacy**:

```python
# BEFORE (legacy)
from config_loader import load_configuration

config = load_configuration()
base_url = config.npu_provider.base_url  # No type safety

# AFTER (refactored)
from src.core import load_settings

settings = load_settings()
base_url = settings.npu_provider.base_url  # Full type safety + autocomplete
```

**Example Usage**:

```python
from src.core import load_settings, Settings

# Load configuration (reads config.yaml + .env)
settings = load_settings()

# Access with full type safety
print(settings.npu_provider.base_url)
print(settings.cpu_fallback.n_ctx)
print(settings.planner.enabled)

# Iterate over providers
for provider in settings.planner.providers:
    print(f"{provider.name}: {provider.model}")
```

**Configuration Models**:

| Model | Description | Key Fields |
|-------|-------------|------------|
| `Settings` | Root configuration | All subsystem settings |
| `NPUProviderSettings` | AnythingLLM backend | `api_key`, `base_url`, `workspace_slug` |
| `CPUFallbackSettings` | CPU inference | `model_path`, `n_ctx`, `n_gpu_layers` |
| `SystemSettings` | General settings | `streaming_enabled`, `stream_timeout` |
| `AgentSettings` | Agent configuration | `default_agent` |
| `PlannerSettings` | Planning phase | `enabled`, `execution_timeout`, `providers` |
| `MergeSettings` | Merge phase | `enabled`, `providers` |
| `ProviderSettings` | LLM provider | `name`, `type`, `base_url`, `model`, `timeout` |

**Validation Examples**:

```python
# Automatic validation catches errors at startup
# ❌ Invalid URL format
npu_provider:
  base_url: "localhost:3001"  # Missing http://
# Error: base_url must start with http:// or https://

# ❌ Planner enabled without providers
planner:
  enabled: true
  providers: []
# Error: Planner is enabled but no providers are configured

# ❌ Invalid timeout
planner:
  execution_timeout: -10
# Error: execution_timeout must be > 0
```

---

### 2. Logging System (`src/core/logger.py`)

**Purpose**: Structured, production-ready logging with JSON output and colored console.

**Key Features**:
- JSON-formatted logs for machine parsing
- Color-coded console output (development)
- Configurable log levels per module
- Performance logging utilities
- Context injection for scoped logging

**Migration from Legacy**:

```python
# BEFORE (legacy)
import logging
logger = logging.getLogger(__name__)
logger.info("Starting inference")

# AFTER (refactored)
from src.core import setup_logging, get_logger

# Initialize logging system (once at startup)
setup_logging(log_level="INFO", log_file="logs/selfai.log", json_output=True)

# Get logger for your module
logger = get_logger(__name__)
logger.info("Starting inference", extra={
    "backend": "anythingllm",
    "model": "Phi-3.5-Mini",
    "tokens": 512
})
```

**Console Output** (colored):
```
2025-01-19 12:30:45 | INFO     | selfai.core.agent              | Starting inference
2025-01-19 12:30:46 | WARNING  | selfai.core.backend            | NPU connection slow
2025-01-19 12:30:47 | ERROR    | selfai.core.backend            | Connection failed
```

**JSON Log Output**:
```json
{
  "timestamp": "2025-01-19 12:30:45",
  "level": "INFO",
  "logger": "selfai.core.agent",
  "message": "Starting inference",
  "module": "agent",
  "function": "__init__",
  "line": 42,
  "process": 1234,
  "thread": 5678,
  "backend": "anythingllm",
  "model": "Phi-3.5-Mini",
  "tokens": 512
}
```

**Advanced Usage**:

```python
from src.core import get_logger, log_performance, LogContext

logger = get_logger(__name__)

# Performance logging
import time
start = time.time()
result = generate_response(prompt)
log_performance(
    logger,
    operation="inference",
    duration_seconds=time.time() - start,
    backend="anythingllm",
    tokens=512
)

# Scoped context logging
with LogContext(logger, request_id="req_123", user="admin"):
    logger.info("Processing request")  # Includes request_id and user
    logger.debug("Loaded memory")      # Includes request_id and user
```

**Dynamic Log Levels**:

```python
from src.core import set_log_level

# Enable debug logging for specific module
set_log_level("selfai.core.agent", "DEBUG")

# Reduce noise from memory system
set_log_level("selfai.core.memory_system", "WARNING")
```

---

### 3. Exception Hierarchy (`src/core/exceptions.py`)

**Purpose**: Comprehensive exception hierarchy for specific, actionable error handling.

**Key Features**:
- Specific exception types for each failure mode
- Contextual information for debugging
- Exception chaining for root cause analysis
- Error code registry for programmatic handling

**Exception Hierarchy**:

```
SelfAIException (Base)
├── ConfigurationError
│   ├── MissingConfigError
│   ├── InvalidConfigError
│   └── EnvironmentVariableError
├── BackendError
│   ├── NPUConnectionError
│   ├── AnythingLLMError
│   ├── QNNError
│   ├── CPUFallbackError
│   └── BackendUnavailableError
├── InferenceError
│   ├── ModelLoadError
│   ├── TokenizationError
│   ├── GenerationError
│   └── StreamingError
├── PlanningError
│   ├── PlanValidationError
│   ├── PlanExecutionError
│   ├── SubtaskError
│   └── MergeError
├── AgentError
│   ├── AgentNotFoundError
│   ├── AgentLoadError
│   └── ToolExecutionError
└── MemoryError
    ├── MemoryLoadError
    ├── MemoryWriteError
    └── ContextFilterError
```

**Migration from Legacy**:

```python
# BEFORE (legacy)
raise ValueError("NPU connection failed")

# AFTER (refactored)
from src.core import NPUConnectionError

raise NPUConnectionError(
    "Failed to connect to AnythingLLM server",
    context={
        "url": "http://localhost:3001",
        "timeout": 30,
        "retry_attempt": 3
    }
)
```

**Exception Usage Examples**:

```python
from src.core import (
    NPUConnectionError,
    FallbackTriggered,
    PlanValidationError,
    get_logger
)

logger = get_logger(__name__)

# Backend connection error
try:
    connect_to_anythingllm(url, timeout=30)
except Exception as e:
    raise NPUConnectionError(
        "Connection to AnythingLLM failed",
        context={"url": url, "timeout": 30},
        original_error=e
    )

# Fallback notification
try:
    use_anythingllm()
except NPUConnectionError as e:
    logger.warning(f"NPU failed, falling back: {e.context}")
    raise FallbackTriggered("anythingllm", "qnn", reason="connection_timeout") from e

# Plan validation error
if "subtasks" not in plan_data:
    raise PlanValidationError(
        "Plan missing required 'subtasks' field",
        context={"plan_id": plan_id, "available_keys": list(plan_data.keys())}
    )

# Exception chaining for debugging
try:
    load_model(model_path)
except FileNotFoundError as e:
    raise ModelLoadError(
        f"Model file not found: {model_path}",
        context={"model_path": model_path, "cwd": os.getcwd()},
        original_error=e
    ) from e
```

**Error Registry** (for programmatic handling):

```python
from src.core import ERROR_REGISTRY, get_exception_class

# Get exception class by error code
ExceptionClass = get_exception_class("NPU_CONNECTION")
raise ExceptionClass(
    "Connection failed",
    context={"url": "localhost:3001"}
)

# Available error codes
print(ERROR_REGISTRY.keys())
# dict_keys(['CONFIG_MISSING', 'CONFIG_INVALID', 'NPU_CONNECTION', ...])
```

---

## Installation & Setup

### 1. Install Dependencies

```bash
# Install refactored infrastructure dependencies
pip install -r requirements-refactored.txt

# Or install individually
pip install pydantic>=2.5.0 pydantic-settings>=2.1.0 PyYAML>=6.0 python-dotenv>=1.0.0 colorama>=0.4.6
```

### 2. Configuration

```bash
# Ensure config.yaml exists
cp config.yaml.template config.yaml

# Ensure .env exists with API_KEY
cp .env.example .env
# Edit .env and set: API_KEY=your-actual-api-key
```

### 3. Test the Infrastructure

```bash
# Test configuration loading
python -m src.core.config

# Test logging system
python -c "
from src.core import setup_logging, get_logger
setup_logging(log_level='INFO', console_colors=True)
logger = get_logger(__name__)
logger.info('Test message', extra={'test': True})
"

# Test exception handling
python -c "
from src.core import NPUConnectionError
try:
    raise NPUConnectionError('Test error', context={'url': 'localhost:3001'})
except NPUConnectionError as e:
    print(f'Caught: {e}')
    print(f'Context: {e.context}')
"
```

---

## Usage Examples

### Complete Application Setup

```python
#!/usr/bin/env python3
"""Main application entry point using refactored infrastructure."""

from src.core import (
    setup_logging,
    get_logger,
    load_settings,
    NPUConnectionError,
    FallbackTriggered,
)

def main():
    # 1. Initialize logging
    setup_logging(
        log_level="INFO",
        log_file="logs/selfai.log",
        json_output=True,
        console_colors=True
    )
    logger = get_logger(__name__)

    try:
        # 2. Load configuration
        settings = load_settings()
        logger.info("Configuration loaded", extra={
            "npu_url": settings.npu_provider.base_url,
            "default_agent": settings.agent_config.default_agent
        })

        # 3. Connect to backends
        try:
            backend = connect_anythingllm(settings.npu_provider)
            logger.info("Connected to AnythingLLM NPU backend")
        except NPUConnectionError as e:
            logger.warning("NPU unavailable, using fallback", exc_info=e)
            backend = load_cpu_fallback(settings.cpu_fallback)

        # 4. Run application
        run_inference_loop(backend, settings)

    except Exception as e:
        logger.critical("Fatal error", exc_info=e)
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
```

### Configuration-Driven Feature Flags

```python
from src.core import load_settings

settings = load_settings()

# Use configuration to enable/disable features
if settings.planner.enabled:
    from planning import PlannerEngine
    planner = PlannerEngine(settings.planner)
    plan = planner.create_plan(user_goal)
else:
    # Direct execution without planning
    execute_directly(user_goal)

if settings.merge.enabled:
    from planning import MergeEngine
    merger = MergeEngine(settings.merge)
    final_result = merger.synthesize(subtask_results)
else:
    # Simple concatenation
    final_result = "\n".join(subtask_results)
```

---

## SOLID Principles Applied

### Single Responsibility Principle (SRP)

Each module has one reason to change:
- `config.py`: Configuration loading and validation
- `logger.py`: Logging setup and utilities
- `exceptions.py`: Exception definitions

### Open/Closed Principle (OCP)

The system is open for extension but closed for modification:
- New exception types can be added by inheriting from base classes
- New configuration sections can be added by extending `Settings`
- New log formatters can be added by inheriting from `logging.Formatter`

### Liskov Substitution Principle (LSP)

All exception subclasses are substitutable for their base class:
```python
def handle_error(error: SelfAIException):
    logger.error(f"Error: {error.message}", extra=error.context)

# Works with any exception type
handle_error(NPUConnectionError(...))
handle_error(PlanValidationError(...))
```

### Interface Segregation Principle (ISP)

Clients depend only on the interfaces they use:
- Configuration users import only `load_settings` and `Settings`
- Logging users import only `setup_logging` and `get_logger`
- Exception handlers import only the specific exceptions they need

### Dependency Inversion Principle (DIP)

High-level modules depend on abstractions, not concrete implementations:
- Configuration is injected via `Settings` object
- Logging is accessed via `get_logger()` interface
- Exceptions follow a common base interface

---

## Migration Strategy

### Phase 1: Infrastructure (COMPLETED ✓)

- [x] Configuration system (`src/core/config.py`)
- [x] Logging system (`src/core/logger.py`)
- [x] Exception hierarchy (`src/core/exceptions.py`)
- [x] Legacy backup (`legacy_reference/`)

### Phase 2: Backend Interfaces (TODO)

- [ ] Base model interface (`src/models/base.py`)
- [ ] AnythingLLM interface (`src/models/anythingllm.py`)
- [ ] QNN interface (`src/models/qnn.py`)
- [ ] CPU fallback interface (`src/models/cpu.py`)
- [ ] Fallback orchestrator (`src/models/orchestrator.py`)

### Phase 3: Agent System (TODO)

- [ ] Agent model (`src/agents/agent.py`)
- [ ] Agent manager (`src/agents/manager.py`)
- [ ] Tool registry (`src/agents/tools/`)

### Phase 4: Planning System (TODO)

- [ ] Planner interface (`src/planning/planner.py`)
- [ ] Execution dispatcher (`src/planning/dispatcher.py`)
- [ ] Plan validator (`src/planning/validator.py`)
- [ ] Merge engine (`src/planning/merge.py`)

### Phase 5: Memory System (TODO)

- [ ] Memory storage (`src/memory/storage.py`)
- [ ] Context filter (`src/memory/context.py`)
- [ ] Memory manager (`src/memory/manager.py`)

### Phase 6: Integration & Testing (TODO)

- [ ] Main application refactor (`src/main.py`)
- [ ] Integration tests
- [ ] Documentation updates
- [ ] Deprecate legacy code

---

## Testing

### Manual Testing

```bash
# Test configuration loading
python -m src.core.config

# Expected output:
# ==============================================================
# CONFIGURATION LOADED SUCCESSFULLY
# ==============================================================
#
# --- NPU Provider ---
# Base URL: http://localhost:3001/api/v1
# Workspace: main
# API Key Set: Yes
# ...
```

### Unit Testing (TODO)

Create `tests/core/` with:
- `test_config.py`: Configuration loading and validation
- `test_logger.py`: Logging functionality
- `test_exceptions.py`: Exception handling

---

## Best Practices

### 1. Always Use Type Hints

```python
# ❌ Bad
def load_model(path):
    return Model(path)

# ✓ Good
def load_model(path: str) -> Model:
    return Model(path)
```

### 2. Use Structured Logging

```python
# ❌ Bad
logger.info(f"User {user} connected from {ip}")

# ✓ Good
logger.info("User connected", extra={"user": user, "ip": ip})
```

### 3. Specific Exception Handling

```python
# ❌ Bad
try:
    connect_to_npu()
except Exception as e:
    print(f"Error: {e}")

# ✓ Good
from src.core import NPUConnectionError, FallbackTriggered

try:
    connect_to_npu()
except NPUConnectionError as e:
    logger.error("NPU connection failed", exc_info=e, extra=e.context)
    raise FallbackTriggered("anythingllm", "qnn") from e
```

### 4. Dependency Injection

```python
# ❌ Bad
def run_inference():
    settings = load_settings()  # Hidden dependency
    logger = get_logger(__name__)
    # ...

# ✓ Good
def run_inference(settings: Settings, logger: Logger):
    # Explicit dependencies
    # ...
```

---

## Troubleshooting

### Import Errors

```
ModuleNotFoundError: No module named 'pydantic_settings'
```

**Solution**:
```bash
pip install pydantic-settings>=2.1.0
```

### Configuration Validation Errors

```
InvalidConfigError: base_url must start with http:// or https://
```

**Solution**: Check `config.yaml` and ensure URLs are properly formatted:
```yaml
npu_provider:
  base_url: "http://localhost:3001/api/v1"  # ✓ Correct
  # base_url: "localhost:3001"              # ✗ Wrong
```

### Environment Variable Not Found

```
EnvironmentVariableError: API_KEY environment variable is not set
```

**Solution**:
1. Copy `.env.example` to `.env`
2. Set `API_KEY=your-actual-api-key` in `.env`
3. Ensure `.env` is in the project root

---

## Contributing

When extending the refactored codebase:

1. **Follow the established patterns**: Use Pydantic for validation, structured logging, specific exceptions
2. **Add comprehensive docstrings**: Google Style with examples
3. **Include type hints**: For all function parameters and return values
4. **Write tests**: For all new functionality
5. **Update documentation**: Keep this guide in sync with code changes

---

## References

- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Python Logging HOWTO**: https://docs.python.org/3/howto/logging.html
- **SOLID Principles**: https://en.wikipedia.org/wiki/SOLID
- **Google Python Style Guide**: https://google.github.io/styleguide/pyguide.html

---

**Last Updated**: 2025-01-19
**Version**: 2.0.0
**Status**: Phase 1 Complete (Infrastructure)
