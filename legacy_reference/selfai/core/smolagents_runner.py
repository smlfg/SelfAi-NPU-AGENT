"""Integration helpers for running smolagents with SelfAI backends."""

from __future__ import annotations

import json
from typing import Any, Iterable, List, Sequence, Tuple
from uuid import uuid4

try:
    from smolagents.agents import LogLevel, RunResult, ToolCallingAgent
    from smolagents.models import (
        ChatMessage,
        ChatMessageToolCall,
        ChatMessageToolCallFunction,
        MessageRole,
        Model,
    )
    from smolagents.monitoring import TokenUsage
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "smolagents is not installed. Install it to enable tool-capable agents."
    ) from exc

from selfai.tools.tool_registry import RegisteredTool, get_tool, get_all_tool_schemas


class SmolAgentError(RuntimeError):
    """Wrapper for smolagent-related execution errors."""


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float)):
        return str(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text_value = item.get("text")
                if text_value:
                    parts.append(str(text_value))
                continue
            parts.append(str(item))
        return "\n".join(parts)
    if isinstance(content, dict):
        return str(content)
    return str(content)


class _SelfAIModel(Model):
    """
    Adapter that makes a SelfAI LLM interface compatible with the `smolagents` model API.
    """

    def __init__(self, llm_interface: Any, *, model_id: str | None = None):
        super().__init__(model_id=model_id or getattr(llm_interface, "model_id", None), flatten_messages_as_text=True)
        self.llm_interface = llm_interface

    def generate(
        self,
        messages: list[ChatMessage],
        stop_sequences: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools_to_call_from: list[Any] | None = None,
        **kwargs: Any,
    ) -> ChatMessage:
        completion_kwargs = self._prepare_completion_kwargs(
            messages,
            stop_sequences=stop_sequences,
            response_format=response_format,
            tools_to_call_from=tools_to_call_from,
            **kwargs,
        )

        message_dicts: list[dict[str, Any]] = completion_kwargs.pop("messages", [])

        system_prompt_parts: list[str] = []
        history: list[dict[str, str]] = []
        user_prompt: str = ""

        for index, message in enumerate(message_dicts):
            role = message.get("role", "")
            content = _normalize_content(message.get("content"))

            if role == "system":
                system_prompt_parts.append(content)
                continue

            if index == len(message_dicts) - 1 and role in {"user", "assistant"}:
                user_prompt = content
                continue

            history.append({"role": role, "content": content})

        if not user_prompt and message_dicts:
            last_message = message_dicts[-1]
            user_prompt = _normalize_content(last_message.get("content"))

        system_prompt = "\n\n".join(part for part in system_prompt_parts if part)

        try:
            response_text = self.llm_interface.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt or "",
                history=history or None,
                timeout=completion_kwargs.get("timeout"),
                max_output_tokens=completion_kwargs.get("max_tokens"),
            )
        except Exception as exc:  # pragma: no cover - passthrough for agent error handling
            raise SmolAgentError(f"SelfAI LLM konnte keine Antwort generieren: {exc}") from exc

        tool_calls, cleaned_content = self._parse_tool_calls(response_text)

        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=None if tool_calls else cleaned_content,
            tool_calls=tool_calls or None,
            token_usage=TokenUsage(input_tokens=0, output_tokens=0),
            raw=response_text,
        )

    @staticmethod
    def _parse_tool_calls(text: str) -> Tuple[list[ChatMessageToolCall], str]:
        """
        Extrahiere Tool-Aufrufe aus dem vom LLM gelieferten Text.
        Erkennt Sequenzen der Form 'Action: { ... }' und wandelt sie in ToolCall-Objekte um.
        """
        tool_calls: list[ChatMessageToolCall] = []
        cursor = 0
        length = len(text)

        def _extract_json_block(source: str, start_index: int) -> Tuple[str | None, int]:
            depth = 0
            in_string = False
            escape = False
            for idx in range(start_index, len(source)):
                char = source[idx]
                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                    continue
                if char == "{":
                    depth += 1
                    continue
                if char == "}":
                    depth -= 1
                    if depth == 0:
                        return source[start_index : idx + 1], idx + 1
            return None, start_index

        while cursor < length:
            action_idx = text.find("Action:", cursor)
            if action_idx == -1:
                break
            brace_idx = text.find("{", action_idx)
            if brace_idx == -1:
                break

            json_block, next_idx = _extract_json_block(text, brace_idx)
            if not json_block:
                cursor = brace_idx + 1
                continue

            try:
                payload = json.loads(json_block)
            except json.JSONDecodeError:
                cursor = next_idx
                continue

            tool_name = payload.get("name")
            if not tool_name:
                cursor = next_idx
                continue

            arguments = payload.get("arguments", {})
            tool_calls.append(
                ChatMessageToolCall(
                    function=ChatMessageToolCallFunction(
                        arguments=arguments, name=str(tool_name)
                    ),
                    id=f"call_{uuid4().hex}",
                    type="function",
                )
            )
            cursor = next_idx

        cleaned_text = text if not tool_calls else ""
        return tool_calls, cleaned_text


class SmolAgentRunner:
    """Convenience wrapper that runs smolagents using the currently active SelfAI LLM interface."""

    def __init__(
        self,
        llm_backends: Sequence[dict[str, Any]],
        *,
        default_tools: Sequence[str] | None = None,
        max_steps: int = 12,
        verbosity: LogLevel = LogLevel.ERROR,
        ui: Any | None = None,
    ) -> None:
        if not llm_backends:
            raise ValueError("Keine LLM-Backends für smolagents verfügbar.")

        self.llm_backends = list(llm_backends)
        self.active_backend_index = 0
        self.default_tools = list(default_tools) if default_tools is not None else None
        self.max_steps = max_steps
        self.verbosity = verbosity
        self.ui = ui

    def _set_backend(self, index: int) -> dict[str, Any]:
        backend = self.llm_backends[index]
        self.active_backend_index = index
        interface = backend.get("interface")
        label = backend.get("label") or backend.get("name") or "smolagent"
        return {"interface": interface, "label": label}

    @staticmethod
    def available_tools() -> List[dict[str, Any]]:
        """Return JSON schemas of all registered tools."""
        return get_all_tool_schemas()

    def _resolve_tools(self, tool_names: Sequence[str] | None) -> list[Any]:
        resolved_tools: list[Any] = []
        names = tool_names or self.default_tools

        if names is None:
            names = [schema["name"] for schema in get_all_tool_schemas()]

        for name in names:
            tool = get_tool(name)
            if tool is None:
                raise SmolAgentError(f"Unbekanntes Tool: '{name}'.")
            resolved_tools.append(self._to_smol_tool(tool))
        return resolved_tools

    @staticmethod
    def _to_smol_tool(reg_tool: RegisteredTool) -> Any:
        try:
            return reg_tool.to_smol_tool()
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SmolAgentError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise SmolAgentError(f"Tool '{reg_tool.name}' konnte nicht initialisiert werden: {exc}") from exc

    def run(
        self,
        *,
        task: str,
        system_prompt: str = "",
        history: Iterable[dict[str, str]] | None = None,
        tool_names: Sequence[str] | None = None,
        max_steps: int | None = None,
        return_full_result: bool = True,
    ) -> RunResult | Any:
        """
        Execute a tool-enabled task using smolagents.

        Args:
            task: Klartext-Aufgabe für den Agenten.
            system_prompt: Ergänzende Verhaltens- oder Rollenbeschreibung.
            history: Vorherige Dialognachrichten (role/content Paare).
            tool_names: Optionale Auswahl an Tools; None nutzt Defaults bzw. alle.
            max_steps: Schrittbegrenzung für den Agenten.
            return_full_result: Steuert, ob ein `RunResult` zurückgegeben wird.

        Returns:
            Ergebnis des Agentenlaufes.
        """
        last_error: Exception | None = None

        order = [self.active_backend_index] + [
            idx for idx in range(len(self.llm_backends)) if idx != self.active_backend_index
        ]

        for index in order:
            backend = self._set_backend(index)
            tools = self._resolve_tools(tool_names)
            model = _SelfAIModel(backend["interface"], model_id=backend["label"])

            agent = ToolCallingAgent(
                tools=tools,
                model=model,
                instructions=system_prompt or None,
                max_steps=max_steps or self.max_steps,
                add_base_tools=False,
                verbosity_level=self.verbosity,
                return_full_result=return_full_result,
            )

            if history:
                for message in history:
                    role = message.get("role", "").lower()
                    content = message.get("content", "")
                    if not content:
                        continue
                    agent.logger.log_markdown(
                        level=LogLevel.DEBUG,
                        title=f"History ({role})",
                        content=str(content),
                    )

            try:
                return agent.run(
                    task,
                    stream=False,
                    reset=True,
                    return_full_result=return_full_result,
                )
            except Exception as exc:  # pylint: disable=broad-except
                last_error = exc
                if self.ui is not None:
                    self.ui.status(
                        f"SmolAgent Backend '{backend['label']}' fehlgeschlagen: {exc}",
                        "warning",
                    )
                continue

        raise SmolAgentError(
            f"SmolAgent konnte mit keinem Backend ausgeführt werden: {last_error}"
        )
