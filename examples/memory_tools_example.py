"""Example usage of the refactored memory and tools systems.

This script demonstrates the key features of the new architecture.
"""

from pathlib import Path

# Import memory components
from src.memory import MemoryManager, ContextManager

# Import tool components
from src.tools import (
    ToolRegistry,
    FileSystemTool,
    ShellTool,
    CalendarTool,
    ProjectTool,
)


def memory_example():
    """Demonstrate memory management features."""
    print("=" * 60)
    print("MEMORY SYSTEM EXAMPLE")
    print("=" * 60)

    # Initialize manager
    manager = MemoryManager(Path("./example_memory"))

    # Save some conversations
    print("\n1. Saving conversations...")

    memory_id1 = manager.save_conversation(
        agent_key="code_helper",
        agent_name="Code Helper",
        workspace_slug="main",
        system_prompt="You are a helpful coding assistant.",
        user_message="How do I sort a list in Python?",
        assistant_message="You can use sorted() for a new sorted list, or list.sort() to sort in-place.",
        category="coding",
        tags=["python", "sorting", "list"],
    )
    print(f"   Saved memory: {memory_id1}")

    memory_id2 = manager.save_conversation(
        agent_key="code_helper",
        agent_name="Code Helper",
        workspace_slug="main",
        system_prompt="You are a helpful coding assistant.",
        user_message="How do I reverse a string in Python?",
        assistant_message="You can use slicing: reversed_str = my_str[::-1]",
        category="coding",
        tags=["python", "string"],
    )
    print(f"   Saved memory: {memory_id2}")

    # Query memories
    print("\n2. Querying memories...")
    memories = manager.query_memories(
        agent_key="code_helper",
        category="coding",
        limit=10,
    )
    print(f"   Found {len(memories)} memories in 'coding' category")

    # Get context for LLM
    print("\n3. Getting context for LLM...")
    context = manager.get_context_messages(
        agent_key="code_helper",
        category="coding",
        limit=2,
    )
    print(f"   Retrieved {len(context)} context messages")
    for msg in context:
        role = msg["role"]
        content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
        print(f"   - {role}: {content}")

    # Statistics
    print("\n4. Memory statistics...")
    stats = manager.get_statistics()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Categories: {stats['categories']}")
    print(f"   Agents: {stats['agents']}")
    print(f"   Top tags: {list(stats['top_tags'].keys())[:5]}")


def context_example():
    """Demonstrate intelligent context retrieval."""
    print("\n" + "=" * 60)
    print("CONTEXT MANAGER EXAMPLE")
    print("=" * 60)

    manager = MemoryManager(Path("./example_memory"))
    context_mgr = ContextManager(manager, default_threshold=0.3)

    # Save diverse conversations
    print("\n1. Saving diverse conversations...")
    conversations = [
        {
            "user": "How do I sort a dictionary in Python?",
            "assistant": "Use sorted() with dict.items()...",
            "tags": ["python", "sorting", "dict"],
        },
        {
            "user": "How do I debug JavaScript?",
            "assistant": "Use console.log() and browser dev tools...",
            "tags": ["javascript", "debugging"],
        },
        {
            "user": "How do I optimize Python code?",
            "assistant": "Use profiling tools like cProfile...",
            "tags": ["python", "optimization"],
        },
    ]

    for conv in conversations:
        manager.save_conversation(
            agent_key="code_helper",
            agent_name="Code Helper",
            workspace_slug="main",
            system_prompt="You are helpful.",
            user_message=conv["user"],
            assistant_message=conv["assistant"],
            category="coding",
            tags=conv["tags"],
        )

    # Get relevant context
    print("\n2. Getting relevant context for query...")
    query = "How can I make my Python code faster?"

    context = context_mgr.get_relevant_context(
        agent_key="code_helper",
        query_text=query,
        limit=2,
    )

    print(f"   Query: '{query}'")
    print(f"   Found {len(context)} relevant context messages")
    for msg in context:
        if msg["role"] == "user":
            print(f"   - Relevant Q: {msg['content'][:60]}...")


def tool_registry_example():
    """Demonstrate tool registry usage."""
    print("\n" + "=" * 60)
    print("TOOL REGISTRY EXAMPLE")
    print("=" * 60)

    # Create registry
    registry = ToolRegistry()

    # Register tools
    print("\n1. Registering tools...")
    registry.register(FileSystemTool())
    registry.register(ShellTool(allowed_commands=["ls", "git", "cat"]))
    registry.register(CalendarTool())
    registry.register(ProjectTool())

    print(f"   Registered tools: {registry.list_tools()}")
    print(f"   Total: {registry.tool_count()} tools")

    # Get tool schemas for LLM
    print("\n2. Getting tool schemas for LLM...")
    schemas = registry.get_all_schemas()
    for schema in schemas:
        print(f"   - {schema['name']}: {schema['description'][:60]}...")

    # Execute tools
    print("\n3. Executing tools...")

    # Filesystem tool
    result = registry.execute("filesystem", operation="list", path=".")
    print(f"   Filesystem (list): {result.success}")
    if result.success:
        files = result.output.split("\n")[:3]
        print(f"   First 3 files: {files}")

    # Shell tool
    result = registry.execute("shell", command="git status", timeout=5)
    print(f"   Shell (git status): {result.success}")

    # Calendar tool
    result = registry.execute(
        "calendar",
        operation="add",
        title="Example Event",
        date="2025-12-25",
        start_time="10:00",
    )
    print(f"   Calendar (add event): {result.success}")

    # Tool info
    print("\n4. Getting tool info...")
    info = registry.get_tool_info("filesystem")
    print(f"   Tool: {info['name']}")
    print(f"   Description: {info['description'][:60]}...")
    print(f"   Parameters: {info['parameter_count']}")


def individual_tool_examples():
    """Demonstrate individual tool usage."""
    print("\n" + "=" * 60)
    print("INDIVIDUAL TOOL EXAMPLES")
    print("=" * 60)

    # FileSystemTool
    print("\n1. FileSystemTool")
    fs_tool = FileSystemTool()

    result = fs_tool.execute(
        operation="write",
        path="example_output.txt",
        content="Hello from SelfAI!",
    )
    print(f"   Write file: {result.success}")

    result = fs_tool.execute(operation="read", path="example_output.txt")
    print(f"   Read file: {result.success}")
    if result.success:
        print(f"   Content: {result.output}")

    # ShellTool
    print("\n2. ShellTool (with whitelist)")
    shell_tool = ShellTool(allowed_commands=["echo", "date", "pwd"])

    result = shell_tool.execute(command="echo 'Hello World'")
    print(f"   Echo: {result.success}")
    if result.success:
        print(f"   Output: {result.output.strip()}")

    # Blocked command
    result = shell_tool.execute(command="rm -rf /")
    print(f"   Dangerous command: {result.success} (should be False)")
    if not result.success:
        print(f"   Error: {result.error}")

    # CalendarTool
    print("\n3. CalendarTool")
    cal_tool = CalendarTool(Path("./example_calendar.json"))

    result = cal_tool.execute(
        operation="add",
        title="Team Meeting",
        date="2025-11-20",
        start_time="14:00",
        location="Room A",
    )
    print(f"   Add event: {result.success}")

    result = cal_tool.execute(operation="list", limit=5)
    print(f"   List events: {result.success}")
    if result.success:
        print(f"   {result.output}")

    # ProjectTool
    print("\n4. ProjectTool")
    proj_tool = ProjectTool()

    result = proj_tool.execute(
        operation="find",
        pattern="*.md",
        path=".",
        max_results=5,
    )
    print(f"   Find files: {result.success}")
    if result.success:
        files = result.output.split("\n")[:3]
        print(f"   Found files: {files}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("SelfAI Memory & Tools - Refactored Architecture")
    print("=" * 60)

    try:
        memory_example()
        context_example()
        tool_registry_example()
        individual_tool_examples()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as exc:
        print(f"\nError running examples: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
