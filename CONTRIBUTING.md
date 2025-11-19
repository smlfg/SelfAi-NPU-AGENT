# Contributing to SelfAI NPU Agent

Thank you for your interest in contributing to the SelfAI NPU Agent project! This guide will help you set up your development environment and understand our contribution workflow.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
  - [Prerequisites](#prerequisites)
  - [CPU-Only Setup (Quick Start)](#cpu-only-setup-quick-start)
  - [NPU Setup (Snapdragon X Elite)](#npu-setup-snapdragon-x-elite)
  - [Docker Setup (CPU Fallback)](#docker-setup-cpu-fallback)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Troubleshooting](#troubleshooting)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## Getting Started

### Quick Overview

SelfAI NPU Agent is a sophisticated AI chatbot with:
- **3-Phase Pipeline**: Planning → Execution → Merge
- **Multi-Backend Support**: AnythingLLM (NPU), QNN (NPU), CPU (GGUF)
- **Clean Architecture**: Domain → Application → Infrastructure → Presentation

Before contributing, please:
1. Read the [Architecture Documentation](CLAUDE.md)
2. Review the [Refactoring Plan](REFACTORING_PLAN.md)
3. Check existing [Issues](https://github.com/smlfg/SelfAi-NPU-AGENT/issues)

---

## Development Setup

### Prerequisites

**Required:**
- **Python 3.12+** (ARM64 build for NPU support on Windows ARM)
- **Git** (for version control)
- **8GB+ RAM** (16GB recommended for NPU optimization)

**Optional:**
- **Snapdragon X Elite** (for NPU acceleration)
- **AnythingLLM Desktop** (for NPU backend)
- **Ollama** (for planning/merge phases)
- **Docker** (for containerized CPU fallback)

---

### CPU-Only Setup (Quick Start)

This setup works on any platform (Windows, Linux, macOS) without NPU hardware.

#### 1. Clone the Repository

```bash
git clone https://github.com/smlfg/SelfAi-NPU-AGENT.git
cd SelfAi-NPU-AGENT
```

#### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Dependencies

```bash
# Install core dependencies (CPU fallback)
pip install -e ".[dev]"

# Or install from requirements files
pip install -r requirements-core.txt
pip install -r requirements.txt  # Includes dev dependencies
```

#### 4. Download Models

Download a GGUF model for CPU inference:

```bash
# Create models directory
mkdir -p models

# Download Phi-3-mini (recommended)
wget https://huggingface.co/TheBloke/Phi-3-Mini-4K-Instruct-GGUF/resolve/main/phi-3-mini-4k-instruct.Q4_K_M.gguf \
     -O models/Phi-3-mini-4k-instruct.Q4_K_M.gguf
```

**Alternative models:**
- [Phi-3-mini-4k-instruct (Q4_K_M)](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf)
- [DeepSeek-LLM-7B-Chat (Q4_K_M)](https://huggingface.co/deepseek-ai/deepseek-llm-7b-chat)

#### 5. Configure Environment

```bash
# Copy example configuration
cp config.yaml.template config.yaml
cp .env.example .env

# Edit .env and add a placeholder API key (not needed for CPU-only)
echo "API_KEY=cpu-fallback-only" >> .env
```

#### 6. Set Up Agents

```bash
# Create default agent directory
mkdir -p agents/code_helfer

# Create system prompt
cat > agents/code_helfer/system_prompt.md << 'EOF'
You are Code Helper, an expert Python developer and software architect.
Your role is to assist with code writing, debugging, and best practices.
EOF

# Create memory categories
echo "coding" > agents/code_helfer/memory_categories.txt

# Create workspace slug
echo "default" > agents/code_helfer/workspace_slug.txt

# Create description
echo "Assists with code writing and debugging" > agents/code_helfer/description.txt
```

#### 7. Run CPU-Only Mode

```bash
# Run SelfAI with CPU fallback
python selfai/selfai.py
```

You should see:
```
✓ CPU-Modell 'Phi-3-mini-4k-instruct.Q4_K_M.gguf' erfolgreich geladen und aktiv.
Aktiver Agent: Code Helper
```

---

### NPU Setup (Snapdragon X Elite)

For hardware-accelerated inference on Windows on ARM.

#### Prerequisites

- **Windows 11 on ARM** (Snapdragon X Elite)
- **Python 3.12 ARM64** build
- **AnythingLLM Desktop ARM64** (optional but recommended)

#### 1. Install NPU Dependencies

```bash
# Activate virtual environment first
.\.venv\Scripts\activate

# Install NPU-specific packages
pip install -r requirements-npu.txt
pip install -e ".[npu]"
```

#### 2. Set Up AnythingLLM (Recommended)

**Download and Install:**
1. Download [AnythingLLM Desktop](https://anythingllm.com/download) (ARM64 build)
2. Install and launch AnythingLLM
3. Create a workspace (e.g., "main")
4. Configure your preferred LLM provider (OpenAI, Ollama, local models)

**Get API Key:**
1. In AnythingLLM, go to **Settings → API Keys**
2. Generate a new API key
3. Copy the key

**Configure:**
```bash
# Edit .env file
echo "API_KEY=your-anythingllm-api-key-here" > .env

# Edit config.yaml
# Set npu_provider.base_url to http://localhost:3001/api/v1
# Set npu_provider.workspace_slug to your workspace name
```

#### 3. Run with NPU Acceleration

```bash
python selfai/selfai.py
```

You should see:
```
✓ AnythingLLM-Verbindung aktiv. NPU-Inferenz bereit.
```

#### 4. QNN Backend (Direct NPU)

For direct QNN model execution without AnythingLLM:

```bash
# Download QNN models to models/ directory
# Example: Phi-3.5-Mini-Instruct from QAI Hub
# Then run:
python llm_chat.py
```

---

### Docker Setup (CPU Fallback)

For isolated CPU-only execution using Docker.

#### 1. Install Docker

- **Windows/macOS**: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: `sudo apt-get install docker.io docker-compose`

#### 2. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f selfai

# Access the container
docker-compose exec selfai bash

# Inside container, run SelfAI
python selfai/selfai.py
```

#### 3. Stop the Service

```bash
docker-compose down
```

---

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

**Branch Naming Convention:**
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/fixes

### 2. Set Up Pre-Commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually (optional)
pre-commit run --all-files
```

This automatically runs:
- **Black** (code formatting)
- **isort** (import sorting)
- **mypy** (type checking)
- **pylint** (linting)

### 3. Make Your Changes

Follow our [Code Standards](#code-standards) below.

### 4. Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_domain.py

# Run with coverage
pytest --cov=selfai --cov-report=html

# Run only unit tests (fast)
pytest -m unit

# Run integration tests
pytest -m integration
```

### 5. Format and Lint

```bash
# Format code
black selfai/ tests/
isort selfai/ tests/

# Type check
mypy selfai/

# Lint
pylint selfai/

# Or use ruff (faster alternative)
ruff check selfai/
ruff format selfai/
```

### 6. Commit Your Changes

We use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git add .
git commit -m "feat: add new planning algorithm"
```

**Commit Message Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build/tooling changes

**Examples:**
```bash
git commit -m "feat(domain): add Subtask entity with lifecycle management"
git commit -m "fix(llm): handle timeout errors in AnythingLLM adapter"
git commit -m "docs(contributing): add NPU setup instructions"
git commit -m "refactor(storage): extract FileSystemRepository from memory_system"
```

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Code Standards

### Architecture Principles

**Follow Clean Architecture:**
```
Presentation → Application → Domain ← Infrastructure
```

- **Domain Layer**: Pure business logic, no external dependencies
- **Application Layer**: Use cases and orchestration
- **Infrastructure Layer**: External adapters (LLM, storage, UI)
- **Presentation Layer**: CLI entry points

**SOLID Principles:**
- **S**ingle Responsibility: One reason to change
- **O**pen/Closed: Open for extension, closed for modification
- **L**iskov Substitution: Implementations are interchangeable
- **I**nterface Segregation: Small, focused interfaces
- **D**ependency Inversion: Depend on abstractions

### Python Style Guide

**Follow PEP 8 with Black defaults:**
- Line length: **88 characters**
- Indentation: **4 spaces** (no tabs)
- String quotes: **Double quotes** preferred
- Imports: Sorted by **isort**

**Type Hints (Required):**
```python
def execute_subtask(
    self,
    subtask: Subtask,
    llm_provider: ILLMProvider,
    timeout: Optional[float] = None,
) -> ExecutionResult:
    ...
```

**Docstrings (Required - Google Style):**
```python
def plan(
    self,
    goal: str,
    context: PlannerContext,
) -> dict[str, object]:
    """Generate an execution plan for the given goal.

    Creates a structured plan (DPPM format) decomposing the goal into
    subtasks, specifying dependencies and merge strategy.

    Args:
        goal: The user's high-level objective.
        context: Planning context with available agents.

    Returns:
        Plan dictionary with subtasks and merge strategy.

    Raises:
        PlannerError: If planning fails.
        ValidationError: If generated plan is invalid.

    Example:
        >>> planner = OllamaPlanner()
        >>> plan = planner.plan("Create web app", context)
        >>> print(len(plan["subtasks"]))
        3
    """
```

### File Organization

**Naming Conventions:**
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/Methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

**Module Structure:**
```python
"""Module docstring explaining purpose."""

# 1. Standard library imports
import json
from pathlib import Path
from typing import Optional

# 2. Third-party imports
import yaml
from dotenv import load_dotenv

# 3. Local imports
from selfai.domain.entities import Agent
from selfai.domain.interfaces import ILLMProvider

# 4. Constants
DEFAULT_TIMEOUT = 60.0

# 5. Classes and functions
class MyClass:
    ...

def my_function():
    ...
```

---

## Testing

### Test Structure

```
tests/
├── unit/                    # Fast, no I/O
│   ├── domain/              # Domain entity tests
│   │   ├── test_agent.py
│   │   ├── test_subtask.py
│   │   └── test_plan.py
│   └── value_objects/       # Value object tests
│       └── test_agent_key.py
│
├── integration/             # With I/O, slower
│   ├── test_llm_adapters.py
│   ├── test_storage.py
│   └── test_planning.py
│
└── e2e/                     # End-to-end tests
    └── test_full_pipeline.py
```

### Writing Tests

**Unit Test Example:**
```python
"""Unit tests for Agent entity."""

import pytest
from selfai.domain.entities import Agent
from selfai.domain.value_objects import AgentKey


class TestAgent:
    """Test suite for Agent entity."""

    def test_agent_creation_success(self):
        """Test successful agent creation with valid data."""
        agent = Agent(
            key=AgentKey("code_helper"),
            display_name="Code Helper",
            system_prompt="You are helpful.",
            memory_categories=["coding"],
        )

        assert agent.display_name == "Code Helper"
        assert agent.has_category("coding")

    def test_agent_creation_fails_empty_prompt(self):
        """Test that agent creation fails with empty system prompt."""
        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            Agent(
                key=AgentKey("test"),
                display_name="Test",
                system_prompt="",  # Invalid!
                memory_categories=["test"],
            )
```

**Integration Test Example:**
```python
"""Integration tests for FileSystemRepository."""

import pytest
from pathlib import Path
from selfai.infrastructure.storage import FileSystemRepository


@pytest.mark.integration
class TestFileSystemRepository:
    """Test suite for file system storage."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create temporary storage directory."""
        return FileSystemRepository(base_dir=tmp_path)

    def test_save_and_load_conversation(self, temp_storage):
        """Test saving and loading conversations."""
        path = temp_storage.save_conversation(
            agent_key="test",
            user_prompt="Hello",
            llm_response="Hi there!",
        )

        assert path.exists()
        assert "test" in str(path)
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit  # Fast, no I/O
@pytest.mark.integration  # With I/O
@pytest.mark.slow  # Long-running tests
@pytest.mark.npu  # Requires NPU hardware
@pytest.mark.cpu  # CPU fallback tests
```

Run specific categories:
```bash
pytest -m unit              # Only unit tests
pytest -m "not slow"        # Skip slow tests
pytest -m "cpu and not npu" # CPU tests only
```

### Coverage Requirements

- **Minimum**: 80% overall coverage
- **Domain Layer**: 100% coverage (pure business logic)
- **Application Layer**: 90%+ coverage
- **Infrastructure Layer**: 70%+ coverage

Check coverage:
```bash
pytest --cov=selfai --cov-report=term-missing
```

---

## Documentation

### Code Documentation

**All public APIs must have:**
1. **Docstrings** (Google style)
2. **Type hints**
3. **Usage examples** in docstrings

**Example:**
```python
def execute_plan(
    self,
    plan: Plan,
    llm_backends: list[dict[str, object]],
) -> list[ExecutionResult]:
    """Execute all subtasks in the plan.

    Executes subtasks in dependency order, respecting parallel groups.
    Automatically retries failed tasks and falls back between LLM backends.

    Args:
        plan: The execution plan with subtasks.
        llm_backends: List of LLM backend configurations in priority order.

    Returns:
        List of execution results for each subtask.

    Raises:
        ExecutionError: If a critical subtask fails after all retries.

    Example:
        >>> service = ExecutionService(storage, ui)
        >>> results = service.execute_plan(plan, backends)
        >>> assert all(r.is_success() for r in results)
    """
```

### Documentation Files

**Update when relevant:**
- `README.md` - Project overview
- `CLAUDE.md` - Architecture details
- `REFACTORING_PLAN.md` - Refactoring strategy
- `UI_GUIDE.md` - Terminal UI features
- `CONTRIBUTING.md` - This file

---

## Pull Request Process

### Before Submitting

**Checklist:**
- [ ] Code follows style guide (Black, isort, mypy pass)
- [ ] All tests pass (`pytest`)
- [ ] Coverage meets requirements (≥80%)
- [ ] Docstrings added for new public APIs
- [ ] Type hints added for all functions
- [ ] Commit messages follow Conventional Commits
- [ ] Branch is up to date with main
- [ ] No merge conflicts

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #123

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated Checks**: CI runs tests, linting, type checking
2. **Code Review**: At least one maintainer review required
3. **Discussion**: Address feedback and questions
4. **Approval**: Merge after approval and passing CI

---

## Troubleshooting

### Common Issues

#### "API_KEY is not set"

**Solution:**
```bash
# For CPU-only mode, add a placeholder
echo "API_KEY=cpu-fallback-only" >> .env

# For AnythingLLM, add your real API key
echo "API_KEY=your-actual-api-key" >> .env
```

#### "No module named 'selfai'"

**Solution:**
```bash
# Install in editable mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### "ModuleNotFoundError: No module named 'llama_cpp'"

**Solution:**
```bash
# Reinstall llama-cpp-python
pip install --upgrade llama-cpp-python
```

#### "Model file not found"

**Solution:**
```bash
# Ensure model is in models/ directory
ls -lh models/

# Download if missing (example)
wget https://huggingface.co/.../model.gguf -O models/model.gguf
```

#### Tests Fail with Import Errors

**Solution:**
```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Or install test requirements
pip install pytest pytest-cov pytest-mock
```

#### Type Checking Fails

**Solution:**
```bash
# Install type stubs
pip install types-PyYAML types-tabulate

# Or ignore specific errors (add to pyproject.toml)
[[tool.mypy.overrides]]
module = "problematic_module.*"
ignore_missing_imports = true
```

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/smlfg/SelfAi-NPU-AGENT/issues)
- **Discussions**: [GitHub Discussions](https://github.com/smlfg/SelfAi-NPU-AGENT/discussions)
- **Documentation**: See [CLAUDE.md](CLAUDE.md) for architecture details

---

## Additional Resources

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [PEP 8](https://pep8.org/)
- [Type Hints (PEP 484)](https://peps.python.org/pep-0484/)

---

**Thank you for contributing to SelfAI NPU Agent!** 🚀

For questions or suggestions about this guide, please open an issue or discussion on GitHub.
