"""Tool Registry - Centralized management of all available tools.

This module provides registration, discovery, and execution of tools
with a standardized interface.
"""

from __future__ import annotations

from typing import Any

from .base_tool import BaseTool, ToolResult


class ToolRegistry:
    """Central registry for managing agent tools.

    The registry provides:
    - Tool registration and discovery
    - Standardized execution interface
    - Schema generation for LLMs
    - Tool validation

    Example:
        >>> from src.tools import ToolRegistry, FileSystemTool, ShellTool
        >>>
        >>> # Create registry
        >>> registry = ToolRegistry()
        >>>
        >>> # Register tools
        >>> registry.register(FileSystemTool())
        >>> registry.register(ShellTool())
        >>>
        >>> # List available tools
        >>> tools = registry.list_tools()
        >>>
        >>> # Execute a tool
        >>> result = registry.execute("filesystem", operation="list", path=".")
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with this name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool by name.

        Args:
            tool_name: Name of tool to remove

        Returns:
            True if tool was removed, False if tool was not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance if found, None otherwise
        """
        return self._tools.get(tool_name)

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of tool names
        """
        return sorted(list(self._tools.keys()))

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get JSON schemas for all registered tools.

        Returns:
            List of tool schemas suitable for LLM function calling

        Examples:
            >>> registry = ToolRegistry()
            >>> registry.register(FileSystemTool())
            >>> schemas = registry.get_all_schemas()
            >>> # schemas = [
            >>> #     {
            >>> #         "name": "filesystem",
            >>> #         "description": "...",
            >>> #         "parameters": {...}
            >>> #     }
            >>> # ]
        """
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome

        Examples:
            >>> registry = ToolRegistry()
            >>> registry.register(FileSystemTool())
            >>> result = registry.execute(
            ...     "filesystem",
            ...     operation="list",
            ...     path="."
            ... )
            >>> if result.success:
            ...     print(result.output)
        """
        tool = self.get_tool(tool_name)

        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found",
            )

        # Use safe_execute which includes validation and error handling
        return tool.safe_execute(**kwargs)

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is registered.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is registered, False otherwise
        """
        return tool_name in self._tools

    def tool_count(self) -> int:
        """Get the number of registered tools.

        Returns:
            Number of registered tools
        """
        return len(self._tools)

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """Get information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with tool information, or None if not found

        Examples:
            >>> info = registry.get_tool_info("filesystem")
            >>> # {
            >>> #     "name": "filesystem",
            >>> #     "description": "...",
            >>> #     "parameters": [...],
            >>> #     "parameter_count": 4
            >>> # }
        """
        tool = self.get_tool(tool_name)
        if tool is None:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in tool.parameters
            ],
            "parameter_count": len(tool.parameters),
        }

    def clear(self) -> None:
        """Clear all registered tools.

        Useful for testing or resetting the registry.
        """
        self._tools.clear()

    def __repr__(self) -> str:
        """String representation of the registry."""
        return f"<ToolRegistry tools={self.tool_count()}>"

    def __str__(self) -> str:
        """Human-readable string representation."""
        tools_list = ", ".join(self.list_tools())
        return f"ToolRegistry with {self.tool_count()} tools: {tools_list}"
