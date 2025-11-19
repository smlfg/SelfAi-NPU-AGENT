
# Memory & Tools Refactoring - Clean Architecture

This document describes the refactored memory and tools systems in the `src/` directory.

## Overview

The refactored architecture provides:

1. **JSON-based Memory Management** - Structured, queryable conversation storage
2. **Standardized Tool Interface** - Type-safe, consistent tool execution
3. **Security & Validation** - Built-in parameter validation and security checks
4. **Comprehensive Documentation** - Google-style docstrings throughout

---

## Memory System (`src/memory/`)

### Architecture

```
src/memory/
├── __init__.py
├── memory_manager.py      # JSON-based memory storage
└── context_manager.py     # Intelligent context retrieval
```

### Key Improvements over Legacy System

| Aspect | Legacy | Refactored |
|--------|--------|------------|
| **Storage Format** | Text files with `---` delimiters | Structured JSON with index |
| **Querying** | Manual file parsing | Fast index-based queries |
| **Tags** | Manual extraction from text | Automatic extraction + manual override |
| **Context Filtering** | Basic tag matching | Relevance scoring with Jaccard similarity |
| **Metadata** | Embedded in text | Separate structured metadata |
| **Search** | File system scan | Index-based with filters |

### MemoryManager

**Storage Structure:**
```
memory/
├── index.json              # Master index for fast queries
├── entries/
│   ├── {uuid}.json        # Individual conversation entries
│   └── ...
└── plans/
    └── {timestamp}_goal.json
```

**Usage Example:**

```python
from pathlib import Path
from src.memory import MemoryManager

# Initialize
manager = MemoryManager(Path("./memory"))

# Save conversation
memory_id = manager.save_conversation(
    agent_key="code_helper",
    agent_name="Code Helper",
    workspace_slug="main",
    system_prompt="You are a helpful coding assistant.",
    user_message="How do I sort a list in Python?",
    assistant_message="You can use sorted() or list.sort()...",
    category="coding",
    tags=["python", "sorting"]  # Optional - auto-extracted if not provided
)

# Query memories
memories = manager.query_memories(
    agent_key="code_helper",
    category="coding",
    tags=["python"],
    limit=5
)

# Get context for LLM
context = manager.get_context_messages(
    agent_key="code_helper",
    category="coding",
    limit=3
)
# Returns: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]

# Statistics
stats = manager.get_statistics()
print(f"Total memories: {stats['total_entries']}")
print(f"Categories: {stats['categories']}")
```

### ContextManager

Provides intelligent context retrieval with relevance scoring.

**Usage Example:**

```python
from src.memory import MemoryManager, ContextManager

manager = MemoryManager(Path("./memory"))
context_manager = ContextManager(manager, default_threshold=0.3)

# Get relevant context for a query
context = context_manager.get_relevant_context(
    agent_key="code_helper",
    query_text="How do I sort a dictionary in Python?",
    limit=3
)
# Automatically:
# - Extracts tags from query ("python", "sorting", "dict")
# - Scores memories by relevance
# - Returns top N most relevant conversations
```

**Relevance Scoring:**
- Uses Jaccard similarity: `intersection(tags) / union(tags)`
- Scores range from 0.0 to 1.0
- Default threshold: 0.3 (configurable)

---

## Tools System (`src/tools/`)

### Architecture

```
src/tools/
├── __init__.py
├── base_tool.py           # Abstract base class
├── tool_registry.py       # Central tool registry
├── filesystem_tools.py    # File operations
├── shell_tools.py         # Shell command execution (secure)
├── calendar_tools.py      # Calendar event management
└── project_tools.py       # Project file search & analysis
```

### Key Improvements over Legacy System

| Aspect | Legacy | Refactored |
|--------|--------|------------|
| **Interface** | Inconsistent (RegisteredTool wrapper + plain functions) | Unified BaseTool interface |
| **Type Safety** | Partial type hints | Full type hints throughout |
| **Validation** | Manual in each tool | Automatic parameter validation |
| **Error Handling** | Inconsistent | Standardized ToolResult |
| **Security** | `shell=True` (injection risk) | `shlex.split()` + command validation |
| **Documentation** | Mixed quality | Comprehensive Google-style docstrings |

### BaseTool Interface

All tools implement this interface:

```python
class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier"""

    @property
    @abstractmethod
    def description(self) -> str:
        """LLM-readable description"""

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """Parameter definitions"""

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute tool logic"""
```

### Available Tools

#### 1. FileSystemTool

**Operations:** `read`, `write`, `list`

```python
from pathlib import Path
from src.tools import FileSystemTool

tool = FileSystemTool(project_root=Path.cwd())

# Read a file
result = tool.execute(operation="read", path="README.md")
if result.success:
    print(result.output)

# Write a file
result = tool.execute(
    operation="write",
    path="test.txt",
    content="Hello, world!",
    create_dirs=True
)

# List directory
result = tool.execute(operation="list", path=".")
```

**Security:**
- All paths validated against project root
- No access outside project directory
- Automatic path resolution

#### 2. ShellTool

**Operations:** Execute shell commands safely

```python
from src.tools import ShellTool

# Whitelist approach (recommended)
tool = ShellTool(
    allowed_commands=["ls", "git", "cat", "grep"],
    timeout=30
)

# Blacklist approach (default)
tool = ShellTool()  # Uses DEFAULT_BLACKLIST (rm, sudo, etc.)

result = tool.execute(command="ls -la")
if result.success:
    print(result.output)
    print(f"Exit code: {result.metadata['exit_code']}")
```

**Security Features:**
- Command whitelist/blacklist
- No `shell=True` (uses `shlex.split()`)
- Timeout enforcement
- Working directory restriction
- Dangerous commands blocked (rm, sudo, chmod, etc.)

#### 3. CalendarTool

**Operations:** `add`, `list`, `query`

```python
from src.tools import CalendarTool

tool = CalendarTool()

# Add event
result = tool.execute(
    operation="add",
    title="Team Meeting",
    date="2025-11-20",
    start_time="14:00",
    location="Conference Room A"
)

# List upcoming events
result = tool.execute(operation="list", limit=10)

# Query by date
result = tool.execute(operation="query", date="2025-11-20")
```

**Features:**
- JSON storage (not iCal/vCal)
- Date/time normalization (multiple formats supported)
- UUID-based event IDs
- Simple filtering

#### 4. ProjectTool

**Operations:** `find`, `search`, `read`

```python
from src.tools import ProjectTool

tool = ProjectTool()

# Find files by pattern
result = tool.execute(
    operation="find",
    pattern="*.py",
    path="src",
    max_results=20
)

# Search file contents
result = tool.execute(
    operation="search",
    pattern="class MemoryManager",
    path="*.py",
    max_results=10
)

# Read file safely
result = tool.execute(
    operation="read",
    path="src/memory/memory_manager.py",
    max_chars=4000
)
```

### ToolRegistry

Central management for all tools:

```python
from src.tools import (
    ToolRegistry,
    FileSystemTool,
    ShellTool,
    CalendarTool,
    ProjectTool,
)

# Create registry
registry = ToolRegistry()

# Register tools
registry.register(FileSystemTool())
registry.register(ShellTool(allowed_commands=["git", "ls", "cat"]))
registry.register(CalendarTool())
registry.register(ProjectTool())

# List available tools
print(registry.list_tools())
# ['calendar', 'filesystem', 'project', 'shell']

# Get tool schemas for LLM
schemas = registry.get_all_schemas()
# Returns: [
#     {
#         "name": "filesystem",
#         "description": "...",
#         "parameters": {
#             "type": "object",
#             "properties": {...},
#             "required": [...]
#         }
#     },
#     ...
# ]

# Execute a tool
result = registry.execute(
    "filesystem",
    operation="list",
    path="."
)

# Get tool info
info = registry.get_tool_info("filesystem")
print(info["description"])
print(f"Parameters: {info['parameter_count']}")
```

---

## Migration Guide

### From Legacy Memory System

**Before (legacy_reference/selfai/core/memory_system.py):**
```python
from selfai.core.memory_system import MemorySystem

memory = MemorySystem(Path("./memory"))
memory.save_conversation(agent, user_prompt, llm_response)
context = memory.load_relevant_context(agent, current_text, limit=3)
```

**After (src/memory/):**
```python
from src.memory import MemoryManager, ContextManager

manager = MemoryManager(Path("./memory"))
context_mgr = ContextManager(manager)

# Save conversation
manager.save_conversation(
    agent_key=agent.key,
    agent_name=agent.display_name,
    workspace_slug=agent.workspace_slug,
    system_prompt=agent.system_prompt,
    user_message=user_prompt,
    assistant_message=llm_response,
    category=agent.memory_categories[0] if agent.memory_categories else "general"
)

# Get relevant context
context = context_mgr.get_relevant_context(
    agent_key=agent.key,
    query_text=current_text,
    limit=3
)
```

### From Legacy Tools

**Before (legacy_reference/selfai/tools/):**
```python
from selfai.tools.filesystem_tools import read_file, write_file

content = read_file("test.txt")
write_file("output.txt", "content")
```

**After (src/tools/):**
```python
from src.tools import FileSystemTool

tool = FileSystemTool()

result = tool.execute(operation="read", path="test.txt")
if result.success:
    content = result.output

result = tool.execute(operation="write", path="output.txt", content="content")
```

---

## Testing

Example test structure:

```python
import pytest
from pathlib import Path
from src.memory import MemoryManager
from src.tools import ToolRegistry, FileSystemTool

def test_memory_save_and_query():
    manager = MemoryManager(Path("./test_memory"))

    memory_id = manager.save_conversation(
        agent_key="test",
        agent_name="Test Agent",
        workspace_slug="test",
        system_prompt="Test prompt",
        user_message="Test question",
        assistant_message="Test answer",
        category="testing"
    )

    assert memory_id is not None

    memories = manager.query_memories(category="testing", limit=1)
    assert len(memories) == 1
    assert memories[0].user_message == "Test question"

def test_tool_registry():
    registry = ToolRegistry()
    tool = FileSystemTool()

    registry.register(tool)

    assert registry.has_tool("filesystem")
    assert registry.tool_count() == 1

    result = registry.execute("filesystem", operation="list", path=".")
    assert result.success
```

---

## Design Principles

### 1. Single Responsibility Principle (SRP)
- `MemoryManager`: Storage and retrieval
- `ContextManager`: Context filtering and relevance
- Each tool: One specific capability

### 2. Open/Closed Principle (OCP)
- New tools extend `BaseTool` without modifying existing code
- Registry accepts any `BaseTool` implementation

### 3. Dependency Inversion Principle (DIP)
- Code depends on `BaseTool` interface, not concrete implementations
- Easy to mock for testing

### 4. Type Safety
- Full type hints throughout
- Dataclasses for structured data
- Type checking with mypy-compatible syntax

### 5. Documentation
- Google-style docstrings
- Examples in docstrings
- Clear parameter descriptions for LLMs

---

## Performance Considerations

### Memory System
- **Index-based queries**: O(N) for index scan, O(1) for file lookup
- **Pagination**: Limit results to avoid loading entire dataset
- **Lazy loading**: Only load full memory entries when needed

### Tools
- **Path validation**: Cached path resolution where possible
- **File operations**: Stream large files instead of loading into memory
- **Search**: Early exit when reaching result limits

---

## Security Considerations

### Memory System
- No arbitrary file access (controlled directory structure)
- JSON validation on load
- Safe string encoding (UTF-8)

### Tools

**FileSystemTool:**
- Path validation against project root
- No directory traversal attacks
- Explicit directory creation flag

**ShellTool:**
- No `shell=True` (prevents injection)
- Command whitelist/blacklist
- Timeout enforcement
- Dangerous command blocking

**ProjectTool:**
- Path validation
- Content size limits
- Pattern-based file selection

---

## Future Enhancements

Potential improvements:

1. **Memory System**
   - Vector embeddings for semantic search
   - SQLite backend for advanced queries
   - Compression for large conversations
   - Export/import functionality

2. **Tools**
   - Async tool execution
   - Tool composition (chain multiple tools)
   - Rate limiting
   - Audit logging

3. **Integration**
   - Smolagents compatibility layer
   - LangChain tool adapters
   - OpenAI function calling format

---

## API Reference

See individual module docstrings for detailed API documentation:

- `src/memory/memory_manager.py` - MemoryManager, MemoryEntry, MemoryMetadata
- `src/memory/context_manager.py` - ContextManager
- `src/tools/base_tool.py` - BaseTool, ToolParameter, ToolResult
- `src/tools/tool_registry.py` - ToolRegistry
- `src/tools/filesystem_tools.py` - FileSystemTool
- `src/tools/shell_tools.py` - ShellTool
- `src/tools/calendar_tools.py` - CalendarTool
- `src/tools/project_tools.py` - ProjectTool

---

**Version:** 2.0.0
**Last Updated:** 2025-11-19
**Status:** Production Ready
