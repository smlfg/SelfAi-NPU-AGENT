# SelfAI NPU Agent Test Suite

Comprehensive test suite for the SelfAI NPU Agent project, ensuring reliability, correctness, and maintainability.

## 📋 Table of Contents

- [Overview](#overview)
- [Test Organization](#test-organization)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Coverage](#test-coverage)
- [Continuous Integration](#continuous-integration)

---

## Overview

This test suite provides **comprehensive coverage** of the SelfAI NPU Agent codebase, including:

- ✅ **Configuration Loading**: Validates YAML parsing, environment variable resolution, and dataclass creation
- ✅ **Backend Fallback**: Tests the critical fallback chain (AnythingLLM → QNN → CPU)
- ✅ **Planning Pipeline**: Validates DPPM plan generation, validation, and persistence
- ✅ **Execution Dispatcher**: Tests subtask execution, dependency handling, and retry logic
- ✅ **Memory System**: Validates conversation storage and retrieval
- ✅ **Agent Management**: Tests agent switching and context loading

### Why Testing Matters

The SelfAI system has **critical failure modes**:
- Configuration errors prevent startup
- Backend failures lose user work
- Invalid plans cause execution deadlock
- Missing retries make the system brittle

These tests **catch failures before users see them**.

---

## Test Organization

```
tests/
├── conftest.py                      # Shared fixtures and mocks
├── test_config_loader.py            # Configuration loading tests
├── test_fallback.py                 # Backend fallback mechanism tests
├── test_pipeline.py                 # Planner logic tests
├── test_execution_dispatcher.py     # Execution phase tests
├── fixtures/                        # Additional test data
│   ├── __init__.py
│   └── test_data/
└── README.md                        # This file
```

### Test File Descriptions

#### `conftest.py`
**Purpose**: Shared pytest fixtures and mocks

**Key Fixtures**:
- `mock_env_vars`: Mocked environment variables (.env)
- `sample_config_dict`: Valid test configuration
- `temp_config_file`: Temporary config.yaml file
- `mock_anythingllm_interface`: Mocked NPU backend
- `mock_qnn_interface`: Mocked QNN backend
- `mock_cpu_interface`: Mocked CPU backend
- `mock_planner_interface`: Mocked planner (Ollama)
- `sample_agent_manager`: Configured AgentManager
- `sample_memory_system`: Configured MemorySystem
- `mock_terminal_ui`: Mocked terminal UI (no console spam)

#### `test_config_loader.py`
**Purpose**: Configuration loading and validation

**Tests**:
- ✅ Successful config loading with all fields
- ✅ Missing config file detection
- ✅ Missing API_KEY detection
- ✅ Environment variable resolution (`${VAR}`)
- ✅ Config format normalization (simple ↔ extended)
- ✅ Planner/merge provider validation
- ✅ Default value application

#### `test_fallback.py`
**Purpose**: Backend fallback mechanism

**Tests**:
- ✅ All backends succeed → use primary (AnythingLLM)
- ✅ NPU fails → fallback to QNN
- ✅ All NPU fail → fallback to CPU (last resort)
- ✅ All backends fail → graceful error
- ✅ Streaming fallback to blocking mode
- ✅ Backend loading with missing dependencies
- ✅ Main loop integration test

**Why This Matters**: The fallback chain is the **safety net** that ensures SelfAI works even without NPU hardware or running services.

#### `test_pipeline.py`
**Purpose**: Planner logic and DPPM validation

**Tests**:
- ✅ Valid plan generation
- ✅ Complex dependency chains
- ✅ Circular dependency detection
- ✅ Invalid dependency detection
- ✅ Parallel group validation
- ✅ Plan persistence (save/load)
- ✅ Fallback plan generation
- ✅ Planner context building
- ✅ Multi-provider planner fallback
- ✅ Plan streaming callbacks

**Why This Matters**: Invalid plans cause **execution deadlock** or **runtime errors**. Validation catches these at planning time.

#### `test_execution_dispatcher.py`
**Purpose**: Subtask execution orchestration

**Tests**:
- ✅ Single subtask execution
- ✅ Multi-subtask with dependencies
- ✅ Backend fallback during execution
- ✅ Retry logic on transient failures
- ✅ Failure handling after retries exhausted
- ✅ Agent context loading
- ✅ Result saving with metadata
- ✅ UI progress updates

**Why This Matters**: Execution is where **plans become reality**. Failures here waste user time and lose work.

---

## Quick Start

### 1. Install Test Dependencies

```bash
# Install all dependencies including tests
pip install -r requirements.txt -r requirements-test.txt

# Or just test dependencies
pip install -r requirements-test.txt
```

### 2. Run All Tests

```bash
pytest
```

Expected output:
```
================================ test session starts =================================
platform linux -- Python 3.12.0, pytest-8.0.0, pluggy-1.4.0
rootdir: /home/user/SelfAi-NPU-AGENT
configfile: pytest.ini
testpaths: tests
plugins: cov-4.1.0, mock-3.12.0, timeout-2.2.0
collected 45 items

tests/test_config_loader.py ............                                       [ 26%]
tests/test_fallback.py .........                                               [ 46%]
tests/test_pipeline.py ..........                                              [ 68%]
tests/test_execution_dispatcher.py ..........                                  [100%]

================================= 45 passed in 2.34s =================================
```

### 3. Check Coverage

```bash
pytest --cov=selfai --cov=config_loader --cov-report=html --cov-report=term
```

Then open `htmlcov/index.html` in your browser.

---

## Running Tests

### Run Specific Tests

```bash
# Single test file
pytest tests/test_fallback.py

# Single test function
pytest tests/test_fallback.py::test_fallback_chain_all_backends_succeed

# Tests matching a pattern
pytest -k "fallback"

# Tests with specific marker
pytest -m unit
```

### Run with Different Verbosity

```bash
# Verbose (show test names)
pytest -v

# Very verbose (show full diffs)
pytest -vv

# Quiet (minimal output)
pytest -q

# Show print statements
pytest -s
```

### Run in Parallel (faster)

```bash
# Use all CPU cores
pytest -n auto

# Use specific number of workers
pytest -n 4
```

### Run Only Failed Tests

```bash
# Re-run only tests that failed last time
pytest --lf

# Re-run failures first, then others
pytest --ff
```

### Debug Failing Tests

```bash
# Drop into PDB debugger on failure
pytest --pdb

# Drop into debugger on first failure
pytest -x --pdb

# Show local variables in traceback
pytest -l
```

---

## Writing Tests

### Test Naming Conventions

```python
# ✅ GOOD: Descriptive test names
def test_fallback_from_npu_to_cpu_when_npu_unavailable():
    pass

# ❌ BAD: Vague test names
def test_fallback():
    pass
```

### Test Structure: Arrange-Act-Assert

```python
def test_configuration_loading_with_valid_file():
    """
    Test that configuration loads successfully with valid config.yaml.

    WHY TEST THIS:
        This is the happy path - when config is correct, system should start.

    SCENARIO:
        - config.yaml exists with all required fields
        - API_KEY is in environment
        - Expected: AppConfig loaded without errors
    """
    # Arrange: Set up test conditions
    config_path = tmp_path / "config.yaml"
    create_valid_config(config_path)

    # Act: Perform the action being tested
    config = load_configuration(str(config_path))

    # Assert: Verify the results
    assert config is not None
    assert config.npu_provider.api_key == "test-key"
```

### Use Fixtures for Shared Setup

```python
def test_planner_uses_agent_context(sample_agent_manager, mock_planner_interface):
    """Fixtures handle setup automatically."""
    # No need to manually create agent_manager or planner
    # Fixtures from conftest.py provide them

    context = build_planner_context(sample_agent_manager)
    plan = mock_planner_interface.plan("goal", context)

    assert plan is not None
```

### Mock External Dependencies

```python
def test_backend_calls_anythingllm_api(mock_anythingllm_interface):
    """Mock prevents actual network calls."""
    # This doesn't make real HTTP requests
    response = mock_anythingllm_interface.generate_response(
        system_prompt="You are helpful",
        user_prompt="Hello"
    )

    # Assert mock was called correctly
    assert mock_anythingllm_interface.generate_response.called
    assert "test response" in response
```

### Test Both Success AND Failure Cases

```python
def test_success_case():
    """Test when everything works."""
    result = function_under_test(valid_input)
    assert result == expected_output

def test_failure_case():
    """Test when input is invalid."""
    with pytest.raises(ValueError):
        function_under_test(invalid_input)
```

---

## Test Coverage

### Current Coverage Goals

- **Overall Coverage**: ≥ 70%
- **Core Modules**: ≥ 80%
  - `config_loader.py`
  - `selfai/core/execution_dispatcher.py`
  - `selfai/core/planner_validator.py`

### Generate Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov=selfai --cov=config_loader --cov-report=term-missing

# HTML report (interactive)
pytest --cov=selfai --cov=config_loader --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov=selfai --cov=config_loader --cov-report=xml
```

### Interpret Coverage

```
Name                                      Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------
config_loader.py                            200     15    92%   145-148, 230-235
selfai/core/execution_dispatcher.py         180     25    86%   67-70, 120-125
selfai/core/planner_validator.py             85      8    91%   45-50
-----------------------------------------------------------------------
TOTAL                                      1234    123    90%
```

- **Stmts**: Total lines of code
- **Miss**: Lines not covered by tests
- **Cover**: Coverage percentage
- **Missing**: Specific line numbers not covered

---

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt -r requirements-test.txt

      - name: Run tests
        run: |
          pytest --cov=selfai --cov=config_loader --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Tests fail with "No module named 'selfai'"

**Solution**: Install the package in development mode:
```bash
pip install -e .
```

### Tests fail with "API_KEY not found"

**Solution**: The tests mock environment variables automatically. If this error appears, check that `conftest.py` is being loaded:
```bash
pytest --fixtures
```

### Coverage is lower than expected

**Solution**: Check what's missing:
```bash
pytest --cov=selfai --cov-report=html
open htmlcov/index.html
# Look for red (uncovered) lines
```

### Tests hang or timeout

**Solution**: Use timeout plugin:
```bash
pytest --timeout=10  # 10 seconds per test
```

---

## Best Practices

### ✅ DO

- Write descriptive test names explaining WHAT and WHY
- Test both success and failure paths
- Use fixtures for shared setup
- Mock external dependencies (APIs, file system, etc.)
- Keep tests fast (< 1 second each)
- Document WHY you test something, not WHAT you test

### ❌ DON'T

- Don't test implementation details (test behavior)
- Don't make tests depend on each other
- Don't use sleep() for timing (use mocks)
- Don't leave print() statements in tests
- Don't skip tests without good reason

---

## Contributing

When adding new features:

1. **Write tests FIRST** (TDD approach)
2. **Run tests** to see them fail
3. **Implement feature**
4. **Run tests** to see them pass
5. **Check coverage** (should not decrease)
6. **Commit** with descriptive message

---

## Questions?

- 📖 **Documentation**: See `CLAUDE.md` for architecture
- 🐛 **Issues**: Check existing tests for examples
- 💬 **Discussion**: Tests ARE documentation - read them!

---

**Happy Testing! 🧪**
