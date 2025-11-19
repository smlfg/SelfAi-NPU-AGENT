"""Validation helpers for planner outputs."""

from __future__ import annotations

from typing import Any, Iterable


class PlanValidationError(ValueError):
    """Raised when the planner response violates the expected schema."""


def _ensure_type(value: Any, expected_type: type | tuple[type, ...], path: str) -> None:
    if not isinstance(value, expected_type):
        raise PlanValidationError(f"{path} muss vom Typ {expected_type}, erhalten: {type(value).__name__}")


def _validate_string(value: Any, path: str, max_len: int = 160) -> None:
    _ensure_type(value, str, path)
    if "\n" in value:
        raise PlanValidationError(f"{path} darf keine Zeilenumbrüche enthalten")
    if len(value) > max_len:
        raise PlanValidationError(f"{path} überschreitet {max_len} Zeichen")


DEFAULT_AGENT_KEYS = {"code_helfer", "research_assistant", "doc_scout", "projektmanager"}
DEFAULT_ENGINES = {"anythingllm", "qnn", "cpu", "smolagent"}


def validate_plan_structure(
    plan: dict[str, Any],
    *,
    allowed_agent_keys: Iterable[str] | None = None,
    allowed_engines: Iterable[str] | None = None,
    ui: Any | None = None,
    translations: dict[str, str] | None = None,
    agent_manager: Any | None = None,
) -> None:
    """Validates that the plan adheres to the expected DPPM schema."""

    if not isinstance(plan, dict):
        raise PlanValidationError("Plan muss ein JSON-Objekt sein")

    agent_whitelist = set(allowed_agent_keys or DEFAULT_AGENT_KEYS)
    if not agent_whitelist:
        agent_whitelist = DEFAULT_AGENT_KEYS

    engine_whitelist = set(allowed_engines or DEFAULT_ENGINES)
    if not engine_whitelist:
        engine_whitelist = DEFAULT_ENGINES

    subtasks = plan.get("subtasks")
    _ensure_type(subtasks, list, "subtasks")
    if not subtasks:
        raise PlanValidationError("subtasks darf nicht leer sein")
    if len(subtasks) > 5:
        raise PlanValidationError("Maximal 5 Subtasks erlaubt")

    task_ids: set[str] = set()
    for index, task in enumerate(subtasks, start=1):
        path = f"subtasks[{index}]"
        _ensure_type(task, dict, path)

        task_id = task.get("id")
        _validate_string(task_id, f"{path}.id")
        if task_id in task_ids:
            raise PlanValidationError(f"Doppelte Task-ID: {task_id}")
        task_ids.add(task_id)

        agent_key = task.get("agent_key")
        _validate_string(agent_key, f"{path}.agent_key")
        if agent_key not in agent_whitelist:
            raise PlanValidationError(
                f"{path}.agent_key '{agent_key}' ist nicht erlaubt"
            )

        engine = task.get("engine")
        _validate_string(engine, f"{path}.engine")
        if engine not in engine_whitelist:
            raise PlanValidationError(f"{path}.engine '{engine}' ist nicht erlaubt")

        _validate_string(task.get("title"), f"{path}.title")
        _validate_string(task.get("objective"), f"{path}.objective")
        notes_field = task.get("notes", "")
        _validate_string(notes_field, f"{path}.notes")

        parallel_group = task.get("parallel_group")
        _ensure_type(parallel_group, int, f"{path}.parallel_group")
        if parallel_group < 1:
            raise PlanValidationError(f"{path}.parallel_group muss >= 1 sein")

        depends_on = task.get("depends_on", [])
        _ensure_type(depends_on, list, f"{path}.depends_on")
        for dep in depends_on:
            _validate_string(dep, f"{path}.depends_on[*]")

        if "tools" in task:
            tools_value = task.get("tools")
            _ensure_type(tools_value, list, f"{path}.tools")
            for tool_name in tools_value:
                _validate_string(tool_name, f"{path}.tools[*]")

    merge = plan.get("merge")
    _ensure_type(merge, dict, "merge")
    _validate_string(merge.get("strategy", ""), "merge.strategy")

    steps = merge.get("steps", [])
    _ensure_type(steps, list, "merge.steps")
    for index, step in enumerate(steps, start=1):
        step_path = f"merge.steps[{index}]"
        _ensure_type(step, dict, step_path)
        _validate_string(step.get("title"), f"{step_path}.title")
        _validate_string(step.get("description"), f"{step_path}.description")
        deps = step.get("depends_on", [])
        _ensure_type(deps, list, f"{step_path}.depends_on")
        for dep in deps:
            _validate_string(dep, f"{step_path}.depends_on[*]")
            if dep not in task_ids:
                raise PlanValidationError(
                    f"{step_path}.depends_on verweist auf unbekannte ID '{dep}'"
                )


def validate_plan_logic(plan_dict: dict[str, Any]) -> list[str]:
    """Prüft zusätzliche logische Konsistenzbedingungen."""
    errors: list[str] = []
    subtasks = plan_dict.get("subtasks") or []

    # Check 1: Duplikate bei Titeln/Zielen
    titles = [str(s.get("title", "")).strip().lower() for s in subtasks]
    if len(titles) != len(set(titles)):
        errors.append("WARNUNG: Duplikat-Titel erkannt. Subtasks sollten eindeutig sein.")

    objectives = [str(s.get("objective", "")).strip().lower() for s in subtasks]
    if len(objectives) != len(set(objectives)):
        errors.append("WARNUNG: Duplikat-Objectives erkannt. Jeder Subtask muss einen eigenen Mehrwert liefern.")

    # Check 2: Selbstabhängigkeiten
    for subtask in subtasks:
        task_id = subtask.get("id")
        deps = subtask.get("depends_on") or []
        if isinstance(deps, list) and task_id and task_id in deps:
            errors.append(f"FEHLER: Subtask {task_id} hängt von sich selbst ab.")

    # Check 3: Abhängigkeiten ohne Mehrwert
    for subtask in subtasks:
        deps = subtask.get("depends_on") or []
        if isinstance(deps, list) and len(deps) == 1:
            parent_id = deps[0]
            parent = next((s for s in subtasks if s.get("id") == parent_id), None)
            if parent:
                child_obj = str(subtask.get("objective", "")).strip()
                parent_obj = str(parent.get("objective", "")).strip()
                if child_obj and child_obj == parent_obj:
                    errors.append(
                        f"WARNUNG: Subtask {subtask.get('id')} wiederholt {parent_id} ohne neuen Wert."
                    )

    # Check 4: Fehlende Dependencies in späteren Schritten
    for index, subtask in enumerate(subtasks):
        if index > 0:
            deps = subtask.get("depends_on") or []
            if not deps:
                errors.append(
                    f"WARNUNG: Subtask {subtask.get('id')} steht nach Schritt {index} ohne depends_on. Prüfe die Abhängigkeitskette."
                )

    # Check 5: Merge-Strategie darf nicht generisch sein
    merge = plan_dict.get("merge") or {}
    strategy = str(merge.get("strategy", "")).strip().lower()
    if not strategy or strategy in {"kombiniere alle outputs.", "kombiniere alle outputs", "kombiniere alles", "combine all outputs", "kombiniere die outputs"}:
        errors.append("WARNUNG: Merge-Strategie ist zu generisch. Beschreibe, wie die Ergebnisse zusammengeführt werden sollen.")

    return errors
