"""
Unified tool-calling interface that supports multiple calling formats.

This module provides a flexible tool execution layer that can handle:
1. JSON-based tool calls (OpenAI format)
2. Text-based tool calls (function_name(args))
3. Smolagents-style tool execution

Usage:
    interface = ToolCallingInterface(llm_interface, tools)
    response = interface.execute_with_tools(prompt, system_prompt)
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

from selfai.tools.tool_registry import RegisteredTool, get_tool, get_all_tool_schemas


class ToolCallingError(RuntimeError):
    """Raised when tool execution fails."""


class ToolCallingInterface:
    """
    Wrapper around an LLM interface that adds tool-calling capabilities.

    Supports multiple tool-calling formats:
    - JSON: {"tool_name": "search", "arguments": {...}}
    - Text: search_project_files("query here")
    - Smolagents: Action: {"name": "search", "arguments": {...}}
    """

    def __init__(
        self,
        llm_interface: Any,
        *,
        tool_names: Sequence[str] | None = None,
        max_iterations: int = 5,
        ui: Any | None = None,
    ):
        """
        Initialize the tool-calling interface.

        Args:
            llm_interface: The underlying LLM interface (AnythingLLM, Local, etc.)
            tool_names: List of tool names to enable (None = all tools)
            max_iterations: Maximum number of tool-calling iterations
            ui: Optional UI for status messages
        """
        self.llm_interface = llm_interface
        self.max_iterations = max_iterations
        self.ui = ui

        # Resolve tools
        if tool_names is None:
            # Use all available tools
            all_schemas = get_all_tool_schemas()
            self.tools = {schema["name"]: get_tool(schema["name"]) for schema in all_schemas}
        else:
            self.tools = {}
            for name in tool_names:
                tool = get_tool(name)
                if tool is None:
                    raise ToolCallingError(f"Tool '{name}' not found in registry.")
                self.tools[name] = tool

        self.tool_schemas = [tool.schema for tool in self.tools.values()]

    def _build_tool_system_prompt(self, base_system_prompt: str = "") -> str:
        """Build system prompt that includes tool descriptions."""
        tool_descriptions = []

        for tool in self.tools.values():
            schema = tool.schema
            name = schema.get("name", tool.name)
            description = schema.get("description", tool.description)
            params = schema.get("parameters", {}).get("properties", {})

            param_desc = []
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "string")
                param_desc_text = param_info.get("description", "")
                param_desc.append(f"  - {param_name} ({param_type}): {param_desc_text}")

            tool_desc = f"**{name}**: {description}"
            if param_desc:
                tool_desc += "\n" + "\n".join(param_desc)

            tool_descriptions.append(tool_desc)

        tools_text = "\n\n".join(tool_descriptions)

        prompt = f"""{base_system_prompt}

# Available Tools

You have access to the following tools:

{tools_text}

# How to Use Tools

To use a tool, respond with ONE of these formats:

**Format 1 (JSON):**
```json
{{
    "tool_name": "tool_name_here",
    "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
    }}
}}
```

**Format 2 (Function call):**
```
tool_name(arg1="value1", arg2="value2")
```

**Format 3 (Smolagents):**
```
Action: {{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}
```

If no tool is needed, respond normally with text.

IMPORTANT: Only use tools when they are actually helpful for the task. Don't force tool usage."""

        return prompt.strip()

    def _parse_tool_call(self, response: str) -> tuple[str | None, dict[str, Any] | None]:
        """
        Parse tool call from LLM response.

        Returns:
            (tool_name, arguments) if tool call found, otherwise (None, None)
        """
        # Try Format 3: Smolagents style
        # Action: {"name": "tool_name", "arguments": {...}}
        smolagent_match = re.search(r'Action:\s*(\{[^}]+\})', response, re.IGNORECASE)
        if smolagent_match:
            try:
                data = json.loads(smolagent_match.group(1))
                tool_name = data.get("name")
                arguments = data.get("arguments", {})
                if tool_name:
                    return tool_name, arguments
            except json.JSONDecodeError:
                pass

        # Try Format 1: JSON object
        # {"tool_name": "...", "arguments": {...}}
        json_match = re.search(r'\{[^}]*"tool_name"[^}]*\}', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                tool_name = data.get("tool_name")
                arguments = data.get("arguments", {})
                if tool_name:
                    return tool_name, arguments
            except json.JSONDecodeError:
                pass

        # Try Format 2: Function call syntax
        # tool_name(arg1="val1", arg2="val2")
        func_match = re.search(r'(\w+)\((.*?)\)', response)
        if func_match:
            tool_name = func_match.group(1)
            args_str = func_match.group(2)

            # Only proceed if this looks like a registered tool
            if tool_name in self.tools:
                # Parse arguments (simple key=value parsing)
                arguments = {}
                if args_str.strip():
                    # Split by comma, handle quoted strings
                    for arg_part in re.findall(r'(\w+)\s*=\s*(["\']?)([^,"\']+)\2', args_str):
                        arg_name, _, arg_value = arg_part
                        arguments[arg_name] = arg_value.strip()

                return tool_name, arguments

        return None, None

    def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool with given arguments."""
        tool = self.tools.get(tool_name)
        if tool is None:
            return f"Error: Tool '{tool_name}' not found."

        if self.ui:
            self.ui.status(f"🔧 Executing tool: {tool_name}", "info")

        try:
            result = tool.run(**arguments)
            return str(result)
        except Exception as exc:
            error_msg = f"Error executing tool '{tool_name}': {exc}"
            if self.ui:
                self.ui.status(error_msg, "error")
            return error_msg

    def execute_with_tools(
        self,
        user_prompt: str,
        *,
        system_prompt: str = "",
        history: Iterable[dict[str, str]] | None = None,
        timeout: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """
        Execute a prompt with tool-calling support.

        Args:
            user_prompt: The user's input
            system_prompt: Base system prompt (tools will be appended)
            history: Conversation history
            timeout: LLM timeout
            max_output_tokens: Maximum tokens to generate

        Returns:
            Final response after tool execution (if any)
        """
        # Build enhanced system prompt with tools
        enhanced_system = self._build_tool_system_prompt(system_prompt)

        # Conversation state
        conversation_history = list(history) if history else []
        current_prompt = user_prompt

        for iteration in range(self.max_iterations):
            # Call LLM
            try:
                response = self.llm_interface.generate_response(
                    system_prompt=enhanced_system,
                    user_prompt=current_prompt,
                    history=conversation_history,
                    timeout=timeout,
                    max_output_tokens=max_output_tokens,
                )
            except Exception as exc:
                if self.ui:
                    self.ui.status(f"LLM error: {exc}", "error")
                raise ToolCallingError(f"LLM generation failed: {exc}") from exc

            # Check if response contains a tool call
            tool_name, arguments = self._parse_tool_call(response)

            if tool_name is None:
                # No tool call found - this is the final response
                return response

            # Execute the tool
            tool_result = self._execute_tool(tool_name, arguments)

            # Update conversation history
            conversation_history.append({"role": "user", "content": current_prompt})
            conversation_history.append({"role": "assistant", "content": response})

            # Prepare next iteration with tool result
            current_prompt = f"Tool '{tool_name}' returned:\n\n{tool_result}\n\nPlease provide a final answer based on this result."

        # Max iterations reached
        if self.ui:
            self.ui.status(f"⚠️ Reached maximum tool-calling iterations ({self.max_iterations})", "warning")

        return response

    def stream_execute_with_tools(
        self,
        user_prompt: str,
        *,
        system_prompt: str = "",
        history: Iterable[dict[str, str]] | None = None,
        timeout: float | None = None,
        max_output_tokens: int | None = None,
    ):
        """
        Execute a prompt with tool-calling support and streaming.

        Note: This is a simplified version that buffers tool-calling responses
        and only streams the final answer.

        Yields:
            Response chunks
        """
        # For now, use non-streaming execution for tool calls
        # Only stream the final response

        enhanced_system = self._build_tool_system_prompt(system_prompt)
        conversation_history = list(history) if history else []
        current_prompt = user_prompt

        for iteration in range(self.max_iterations):
            # Check if interface supports streaming
            if hasattr(self.llm_interface, "stream_generate_response"):
                # Collect streaming response
                chunks = []
                for chunk in self.llm_interface.stream_generate_response(
                    system_prompt=enhanced_system,
                    user_prompt=current_prompt,
                    history=conversation_history,
                    timeout=timeout,
                    max_output_tokens=max_output_tokens,
                ):
                    chunks.append(chunk)
                    # Only yield on final iteration (no tool call)

                response = "".join(chunks)
            else:
                # Fallback to non-streaming
                response = self.llm_interface.generate_response(
                    system_prompt=enhanced_system,
                    user_prompt=current_prompt,
                    history=conversation_history,
                    timeout=timeout,
                    max_output_tokens=max_output_tokens,
                )

            # Check for tool call
            tool_name, arguments = self._parse_tool_call(response)

            if tool_name is None:
                # No tool call - stream/yield final response
                for chunk in chunks if chunks else [response]:
                    yield chunk
                return

            # Execute tool
            tool_result = self._execute_tool(tool_name, arguments)

            # Update history
            conversation_history.append({"role": "user", "content": current_prompt})
            conversation_history.append({"role": "assistant", "content": response})

            # Continue with tool result
            current_prompt = f"Tool '{tool_name}' returned:\n\n{tool_result}\n\nPlease provide a final answer based on this result."

        # Max iterations - yield last response
        yield response
