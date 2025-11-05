"""
Tool validation module to prevent hallucination of non-existent tools.

This module provides strict validation to ensure agents only use real, registered tools.
"""

from __future__ import annotations

import json
from typing import Any

from selfai.tools.tool_registry import get_tool, get_all_tool_schemas


class ToolValidationError(ValueError):
    """Raised when tool validation fails."""


def get_valid_tool_names() -> set[str]:
    """
    Get set of all valid tool names.

    Returns:
        Set of registered tool names.
    """
    schemas = get_all_tool_schemas()
    return {schema.get("name") for schema in schemas if schema.get("name")}


def validate_tool_name(tool_name: str) -> tuple[bool, str]:
    """
    Validate if a tool name is registered.

    Args:
        tool_name: Name of the tool to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, "error description")
    """
    if not tool_name or not isinstance(tool_name, str):
        return False, "Tool-Name muss ein nicht-leerer String sein"

    valid_tools = get_valid_tool_names()

    if tool_name not in valid_tools:
        # Provide helpful error message with similar tools
        similar = [t for t in valid_tools if tool_name.lower() in t.lower() or t.lower() in tool_name.lower()]
        if similar:
            return False, f"Tool '{tool_name}' existiert nicht. Meintest du vielleicht: {', '.join(similar[:3])}?"
        else:
            return False, f"Tool '{tool_name}' existiert nicht. Verfügbare Tools: {', '.join(sorted(valid_tools))}"

    return True, ""


def validate_plan_tools(plan_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate all tools referenced in a plan.

    Args:
        plan_data: The plan dictionary

    Returns:
        Tuple of (all_valid, error_messages)
    """
    errors = []
    valid_tools = get_valid_tool_names()

    subtasks = plan_data.get("subtasks", [])
    if not isinstance(subtasks, list):
        return False, ["Plan enthält keine gültige 'subtasks' Liste"]

    for idx, task in enumerate(subtasks):
        if not isinstance(task, dict):
            errors.append(f"Subtask {idx} ist kein Dictionary")
            continue

        task_id = task.get("id", f"#{idx}")
        engine = task.get("engine", "")

        # Only validate tools for smolagent engine
        if engine != "smolagent":
            continue

        tools = task.get("tools")
        if tools is None:
            # No tools specified - this is OK for smolagent
            continue

        if not isinstance(tools, list):
            errors.append(f"Subtask {task_id}: 'tools' muss eine Liste sein, ist {type(tools).__name__}")
            continue

        for tool_name in tools:
            if not isinstance(tool_name, str):
                errors.append(f"Subtask {task_id}: Tool-Name muss String sein, ist {type(tool_name).__name__}")
                continue

            if tool_name not in valid_tools and tool_name != "final_answer":
                # Tool doesn't exist!
                similar = [t for t in valid_tools if tool_name.lower() in t.lower()]
                if similar:
                    errors.append(
                        f"Subtask {task_id}: Tool '{tool_name}' existiert nicht. "
                        f"Meintest du vielleicht: {', '.join(similar[:3])}?"
                    )
                else:
                    errors.append(
                        f"Subtask {task_id}: Tool '{tool_name}' existiert nicht. "
                        f"Verfügbare Tools: {', '.join(sorted(list(valid_tools)[:10]))}... "
                        f"(insgesamt {len(valid_tools)} Tools)"
                    )

    return len(errors) == 0, errors


def sanitize_plan_tools(plan_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Remove invalid tools from a plan and return sanitized version.

    Args:
        plan_data: The plan dictionary

    Returns:
        Tuple of (sanitized_plan, removed_tools)
    """
    removed = []
    valid_tools = get_valid_tool_names()
    sanitized = json.loads(json.dumps(plan_data))  # Deep copy

    subtasks = sanitized.get("subtasks", [])
    for task in subtasks:
        if not isinstance(task, dict):
            continue

        engine = task.get("engine", "")
        if engine != "smolagent":
            continue

        tools = task.get("tools")
        if not isinstance(tools, list):
            continue

        valid_task_tools = []
        for tool_name in tools:
            if not isinstance(tool_name, str):
                continue

            if tool_name in valid_tools or tool_name == "final_answer":
                valid_task_tools.append(tool_name)
            else:
                removed.append(f"{task.get('id', '?')}: {tool_name}")

        task["tools"] = valid_task_tools

    return sanitized, removed


def generate_tool_whitelist_prompt() -> str:
    """
    Generate a prompt snippet listing all valid tools.

    Returns:
        Formatted string with tool whitelist
    """
    schemas = get_all_tool_schemas()

    if not schemas:
        return "**WICHTIG:** Keine Tools verfügbar. Verwende NUR 'final_answer'."

    tool_list = []
    for schema in schemas:
        name = schema.get("name", "")
        desc = schema.get("description", "")[:60]
        tool_list.append(f"  - {name}: {desc}")

    tool_list.append("  - final_answer: Abschluss der Ausführung")

    return f"""**KRITISCH - Tool-Whitelist:**
Diese Tools existieren WIRKLICH und dürfen verwendet werden:

{chr(10).join(tool_list)}

ERFINDE KEINE ANDEREN TOOLS! Verwende NUR Tools aus dieser Liste.
Ungültige Tool-Namen führen zum Abbruch der Ausführung.
"""


def validate_tool_call_runtime(tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a tool call at runtime before execution.

    Args:
        tool_name: Name of the tool
        arguments: Tool arguments

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if tool exists
    tool = get_tool(tool_name)
    if tool is None:
        valid_tools = get_valid_tool_names()
        return False, f"Tool '{tool_name}' existiert nicht. Verfügbare: {', '.join(sorted(valid_tools))}"

    # Check if arguments is dict
    if not isinstance(arguments, dict):
        return False, f"Tool-Argumente müssen ein Dictionary sein, nicht {type(arguments).__name__}"

    # Get required parameters from schema
    schema = tool.schema
    params = schema.get("parameters", {})
    required = params.get("required", [])

    # Check if all required parameters are present
    missing = [param for param in required if param not in arguments]
    if missing:
        return False, f"Tool '{tool_name}' fehlen erforderliche Parameter: {', '.join(missing)}"

    return True, ""
