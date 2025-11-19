"""Tool provider interface for function calling.

This module defines the protocol for tool providers that enable
LLMs to execute functions and interact with external systems.
"""

from typing import Protocol, Any


class IToolProvider(Protocol):
    """Protocol defining the interface for tool providers.

    Tool providers manage a registry of executable functions that LLMs
    can call to perform actions or retrieve information.

    Methods:
        get_tool_schemas: Retrieve schemas for all available tools.
        execute_tool: Execute a tool by name with arguments.
        list_tool_names: Get names of all registered tools.
    """

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Retrieve JSON schemas for all registered tools.

        Returns schema definitions suitable for LLM function calling.

        Returns:
            List of tool schema dictionaries in OpenAI function calling format:
            [
                {
                    "name": "get_current_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"}
                        },
                        "required": ["location"]
                    }
                },
                ...
            ]

        Example:
            >>> tools = ToolRegistry()
            >>> schemas = tools.get_tool_schemas()
            >>> print(schemas[0]["name"])
            "get_current_weather"
        """
        ...

    def execute_tool(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a tool by name with the provided arguments.

        Args:
            tool_name: Name of the tool to execute.
            **kwargs: Keyword arguments for the tool function.

        Returns:
            Tool execution result (type depends on tool).

        Raises:
            KeyError: If tool_name is not registered.
            TypeError: If required arguments are missing or types are wrong.
            ValueError: If argument validation fails.

        Example:
            >>> tools = ToolRegistry()
            >>> result = tools.execute_tool(
            ...     "get_current_weather",
            ...     location="San Francisco",
            ...     unit="celsius"
            ... )
            >>> print(result)
            '{"location": "San Francisco", "temperature": "22", "unit": "celsius"}'
        """
        ...

    def list_tool_names(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names.

        Example:
            >>> tools = ToolRegistry()
            >>> names = tools.list_tool_names()
            >>> print(names)
            ["get_current_weather", "find_train_connections", "add_calendar_event"]
        """
        ...
