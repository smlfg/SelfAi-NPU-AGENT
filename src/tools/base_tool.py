"""Base tool interface for SelfAI agent tools.

This module defines the abstract base class for all tools, ensuring
a consistent interface and proper type safety.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolParameter:
    """Definition of a tool parameter.

    Attributes:
        name: Parameter name
        type: Parameter type (e.g., "string", "integer", "boolean")
        description: Human-readable description for the LLM
        required: Whether this parameter is required (default: True)
        default: Default value if parameter is optional
    """

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert parameter to dictionary format.

        Returns:
            Dictionary representation suitable for LLM tool schemas
        """
        param_dict = {
            "type": self.type,
            "description": self.description,
        }

        if not self.required and self.default is not None:
            param_dict["default"] = self.default

        return param_dict


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        success: Whether the tool executed successfully
        output: The tool's output (string or structured data)
        error: Error message if execution failed
        metadata: Optional metadata about the execution
    """

    success: bool
    output: Any
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def __str__(self) -> str:
        """String representation of the result."""
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    All tools must inherit from this class and implement the required methods.
    This ensures a consistent interface for the agent framework.

    Subclasses must implement:
        - name (property): Unique tool identifier
        - description (property): Clear description for LLM understanding
        - parameters (property): List of tool parameters
        - execute(): The actual tool logic

    Example:
        >>> class MyTool(BaseTool):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_tool"
        ...
        ...     @property
        ...     def description(self) -> str:
        ...         return "Does something useful"
        ...
        ...     @property
        ...     def parameters(self) -> list[ToolParameter]:
        ...         return [
        ...             ToolParameter(
        ...                 name="input",
        ...                 type="string",
        ...                 description="Input text"
        ...             )
        ...         ]
        ...
        ...     def execute(self, **kwargs) -> ToolResult:
        ...         input_text = kwargs.get("input", "")
        ...         return ToolResult(success=True, output=f"Processed: {input_text}")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool.

        Returns:
            Tool name (lowercase, no spaces)
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does.

        This description is shown to the LLM to help it understand when
        to use this tool.

        Returns:
            Clear, concise description
        """

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """List of parameters this tool accepts.

        Returns:
            List of ToolParameter definitions
        """

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Named parameters matching the tool's parameter definitions

        Returns:
            ToolResult with success status and output/error

        Raises:
            Should NOT raise exceptions - catch all errors and return
            ToolResult with success=False and error message
        """

    def validate_parameters(self, **kwargs: Any) -> tuple[bool, str | None]:
        """Validate provided parameters against tool definition.

        Args:
            **kwargs: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if parameters are valid
            - error_message: Error description if invalid, None otherwise
        """
        # Check required parameters
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

        # Check for unknown parameters
        valid_param_names = {p.name for p in self.parameters}
        for key in kwargs:
            if key not in valid_param_names:
                return False, f"Unknown parameter: {key}"

        return True, None

    def to_schema(self) -> dict[str, Any]:
        """Convert tool to JSON schema format for LLM.

        Returns:
            Dictionary with tool schema in OpenAI function calling format

        Examples:
            >>> tool = MyTool()
            >>> schema = tool.to_schema()
            >>> # {
            >>> #     "name": "my_tool",
            >>> #     "description": "Does something useful",
            >>> #     "parameters": {
            >>> #         "type": "object",
            >>> #         "properties": {
            >>> #             "input": {
            >>> #                 "type": "string",
            >>> #                 "description": "Input text"
            >>> #             }
            >>> #         },
            >>> #         "required": ["input"]
            >>> #     }
            >>> # }
        """
        properties = {param.name: param.to_dict() for param in self.parameters}
        required = [param.name for param in self.parameters if param.required]

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def safe_execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with parameter validation and error handling.

        This method wraps execute() with:
        - Parameter validation
        - Exception handling
        - Consistent error responses

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        # Validate parameters
        is_valid, error_msg = self.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(success=False, output="", error=error_msg)

        # Execute with error handling
        try:
            return self.execute(**kwargs)
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution failed: {str(exc)}",
            )

    def __repr__(self) -> str:
        """String representation of the tool."""
        return f"<{self.__class__.__name__} name='{self.name}'>"
