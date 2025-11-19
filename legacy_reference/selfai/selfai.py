import json
import sys
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

# Füge das Projekt-Stammverzeichnis zum Pfad hinzu, um Importe aus `core` zu ermöglichen
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root.parent))

from config_loader import load_configuration
from selfai.core.agent_manager import Agent, AgentManager
from selfai.core.anythingllm_interface import AnythingLLMInterface
from selfai.core.local_llm_interface import LocalLLMInterface
from selfai.core.execution_dispatcher import ExecutionDispatcher, ExecutionError
from selfai.core.memory_system import MemorySystem
from selfai.core.planner_ollama_interface import (
    PlannerContext,
    PlannerError,
    PlannerOllamaInterface,
)
from selfai.core.planner_validator import (
    PlanValidationError,
    validate_plan_logic,
)
from selfai.core.merge_ollama_interface import MergeOllamaInterface
from selfai.ui.terminal_ui import TerminalUI

PLANNER_STATE_FILENAME = "planner_state.json"
MERGE_STATE_FILENAME = "merge_state.json"


def _format_gigabytes(value_bytes: float) -> float:
    return value_bytes / (1024 ** 3)


def _show_system_resources(ui: TerminalUI) -> None:
    if psutil is None:
        ui.status("Systemmonitor nicht verfügbar (psutil nicht installiert).", "warning")
        return

    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
    except Exception as exc:
        ui.status(f"Systemmonitor konnte nicht abgerufen werden: {exc}", "warning")
        return

    total_gb = _format_gigabytes(mem.total)
    used_gb = _format_gigabytes(mem.total - mem.available)
    free_gb = _format_gigabytes(mem.available)

    status_parts = [
        f"RAM {used_gb:.1f}/{total_gb:.1f} GB ({mem.percent:.0f}%)",
        f"frei {free_gb:.1f} GB",
        f"CPU {cpu_percent:.0f}%",
    ]

    if swap and swap.total:
        swap_used = _format_gigabytes(swap.used)
        swap_total = _format_gigabytes(swap.total)
        status_parts.append(f"Swap {swap_used:.1f}/{swap_total:.1f} GB ({swap.percent:.0f}%)")

    ui.status(" | ".join(status_parts), "info")


def _show_pipeline_overview(ui: TerminalUI) -> None:
    ui.status("Pipeline: 1) Planner – zerlegt dein Ziel in Subtasks.", "info")
    ui.status(
        "Pipeline: 2) Execution – führt die Subtasks nacheinander oder parallel gemäß Plan aus.",
        "info",
    )
    ui.status(
        "Pipeline: 3) Merge – verdichtet alle Ergebnisse zu einer finalen Antwort.",
        "info",
    )


def _default_agent_key(agent_manager: AgentManager) -> str | None:
    if agent_manager.active_agent:
        return agent_manager.active_agent.key
    agents = agent_manager.list_agents()
    if agents:
        return agents[0].key
    return None


def _build_fallback_plan(goal_text: str, agent_key: str) -> dict[str, object]:
    sanitized_goal = goal_text.strip()
    return {
        "subtasks": [
            {
                "id": "S1",
                "title": "Analyse des Ziels",
                "objective": f"Analysiere das Ziel: {sanitized_goal}",
                "agent_key": agent_key,
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
                "notes": "Automatisch erzeugter Fallback-Plan – bitte Ergebnis kritisch prüfen.",
            },
            {
                "id": "S2",
                "title": "Antwort formulieren",
                "objective": f"Formuliere eine ausführliche Antwort für: {sanitized_goal}",
                "agent_key": agent_key,
                "engine": "anythingllm",
                "parallel_group": 2,
                "depends_on": ["S1"],
                "notes": "Automatisch erzeugter Fallback-Plan.",
            },
        ],
        "merge": {
            "strategy": "Analyse und Antwort zu einem konsistenten Ergebnis kombinieren.",
            "steps": [
                {
                    "title": "Synthese",
                    "description": "Fasse Analyse und Antwort in einer finalen Empfehlung zusammen.",
                    "depends_on": ["S2"],
                }
            ],
        },
    }


def _sanitize_plan_agents(
    plan_data: dict[str, object],
    agent_manager: AgentManager,
    ui: TerminalUI,
) -> None:
    valid_keys = {agent.key for agent in agent_manager.list_agents()}
    if not valid_keys:
        return

    fallback_key = _default_agent_key(agent_manager)
    if fallback_key is None:
        return

    changed = False
    for task in plan_data.get("subtasks", []) or []:
        key = task.get("agent_key")
        if key not in valid_keys:
            task["agent_key"] = fallback_key
            changed = True
    if changed:
        ui.status(
            f"Plan angepasst: Unbekannte Agenten wurden auf '{fallback_key}' gemappt.",
            "warning",
        )


def _announce_plan_agents(
    plan_data: dict[str, object],
    agent_manager: AgentManager,
    ui: TerminalUI,
) -> None:
    seen: set[str] = set()
    for task in plan_data.get("subtasks", []) or []:
        key = task.get("agent_key")
        if not key or key in seen:
            continue
        agent = agent_manager.get(key)
        if agent is None:
            continue
        description = agent.description.strip() if agent.description else ""
        if description:
            ui.status(
                f"Subtasks nutzen Agent '{agent.display_name}' – {description}",
                "info",
            )
        else:
            ui.status(
                f"Subtasks nutzen Agent '{agent.display_name}'.",
                "info",
            )
        seen.add(key)


def _build_planner_context(
    agent_manager: AgentManager, memory_system: MemorySystem
) -> PlannerContext:
    agents_data = []
    for agent in agent_manager.list_agents():
        categories = ", ".join(agent.memory_categories) or "-"
        details = [f"Memory: {categories}", f"Workspace: {agent.workspace_slug}"]
        if agent.description:
            details.insert(0, agent.description.strip())
        agents_data.append(
            {
                "key": agent.key,
                "display_name": agent.display_name,
                "description": "; ".join(details),
            }
        )

    plan_dir = getattr(memory_system, "plan_dir", None)
    summary = ""
    if plan_dir and plan_dir.exists():
        plan_files = sorted(plan_dir.glob("*.json"))
        if plan_files:
            summary = (
                f"{len(plan_files)} gespeicherte Pläne. Letzter: {plan_files[-1].name}"
            )
    if not summary:
        summary = "Noch keine Pläne gespeichert."

    return PlannerContext(agents=agents_data, memory_summary=summary)


def _planner_state_path(memory_system: MemorySystem) -> Path:
    return memory_system.memory_dir / PLANNER_STATE_FILENAME


def _load_active_planner(memory_system: MemorySystem) -> str | None:
    path = _planner_state_path(memory_system)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = data.get("active_provider")
        if isinstance(value, str) and value:
            return value
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _save_active_planner(memory_system: MemorySystem, provider_name: str) -> None:
    path = _planner_state_path(memory_system)
    try:
        path.write_text(
            json.dumps({"active_provider": provider_name}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _merge_state_path(memory_system: MemorySystem) -> Path:
    return memory_system.memory_dir / MERGE_STATE_FILENAME


def _load_active_merge(memory_system: MemorySystem) -> str | None:
    path = _merge_state_path(memory_system)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = data.get("active_provider")
        if isinstance(value, str) and value:
            return value
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _save_active_merge(memory_system: MemorySystem, provider_name: str) -> None:
    path = _merge_state_path(memory_system)
    try:
        path.write_text(
            json.dumps({"active_provider": provider_name}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _load_plan_file(plan_path: Path) -> dict:
    try:
        return json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_plan_file(plan_path: Path, data: dict) -> None:
    try:
        plan_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _read_result_file(result_path: Path) -> str:
    try:
        return result_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _collect_subtask_entries(plan_data: dict[str, object]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    subtasks = plan_data.get("subtasks", []) or []
    base_dir = project_root.parent
    for task in subtasks:
        if not isinstance(task, dict):
            continue
        result_ref = task.get("result_path")
        content = ""
        if result_ref:
            result_path = Path(result_ref)
            if not result_path.is_absolute():
                result_path = base_dir / result_path
            content = _read_result_file(result_path)
        entries.append(
            {
                "id": str(task.get("id", "?")),
                "title": str(task.get("title", "")),
                "objective": str(task.get("objective", "")),
                "output": content or "",
            }
        )
    return entries


def _render_fallback_merge(entries: list[dict[str, str]]) -> str:
    if not entries:
        return "SelfAI konnte keine Subtask-Ergebnisse finden."

    lines: list[str] = ["# Merge Summary (Fallback)", ""]
    for entry in entries:
        title = entry.get("title") or entry.get("id") or "Subtask"
        lines.append(f"## {entry.get('id', '?')} – {title}")
        objective = entry.get("objective", "").strip()
        if objective:
            lines.append(f"**Objective:** {objective}")
        output = entry.get("output", "").strip()
        if output:
            snippet = output if len(output) <= 600 else output[:600].rstrip() + "…"
            lines.append("```")
            lines.append(snippet)
            lines.append("```")
        else:
            lines.append("(Kein Output gespeichert.)")
        lines.append("")
    return "\n".join(lines).strip()


def _select_merge_agent_from_plan(
    merge_cfg: dict[str, object],
    agent_manager: AgentManager,
) -> Agent | None:
    merge_agent_key = None
    if isinstance(merge_cfg, dict):
        merge_agent_key = merge_cfg.get("agent_key")

    if merge_agent_key:
        agent = agent_manager.get(merge_agent_key)
        if agent:
            return agent

    agent = agent_manager.get("projektmanager")
    if agent:
        return agent

    return agent_manager.active_agent


def _execute_merge_phase(
    plan_path: Path,
    merge_backend: dict[str, object],
    agent_manager: AgentManager,
    memory_system: MemorySystem,
    ui: TerminalUI,
    execution_timeout: float | None,
) -> bool:
    llm_interface = merge_backend.get("interface")
    if llm_interface is None:
        ui.status("Kein Merge-Backend verfügbar.", "warning")
        return False

    merge_label = merge_backend.get("label", "Merge")
    try:
        merge_token_limit = int(merge_backend.get("max_tokens", 2048) or 2048)
    except (TypeError, ValueError):
        merge_token_limit = 2048

    timeout_value = merge_backend.get("timeout")
    if timeout_value is not None:
        try:
            timeout_value = float(timeout_value)
        except (TypeError, ValueError):
            timeout_value = execution_timeout
    else:
        timeout_value = execution_timeout

    plan_data = _load_plan_file(plan_path)
    merge_cfg = plan_data.get("merge") or {}
    if not merge_cfg:
        ui.status("Kein Merge-Schritt im Plan definiert.", "info")
        return True

    entries = _collect_subtask_entries(plan_data)
    outputs: list[str] = []
    for entry in entries:
        content = entry.get("output", "").strip()
        if not content:
            continue
        block = (
            f"Subtask {entry.get('id', '?')} – {entry.get('title', '')}\n"
            f"Objective: {entry.get('objective', '')}\n"
            f"Output:\n{content}"
        )
        outputs.append(block)

    if not outputs:
        ui.status("Keine Subtask-Ergebnisse für den Merge gefunden.", "warning")
        return False

    merge_agent = _select_merge_agent_from_plan(merge_cfg, agent_manager)
    if merge_agent is None:
        ui.status("Kein Agent für Merge verfügbar.", "warning")
        return False

    strategy = merge_cfg.get("strategy") or ""
    steps = merge_cfg.get("steps", []) or []
    steps_text = "".join(
        f"- {step.get('title', 'Schritt')}: {step.get('description', '').strip()}\n"
        for step in steps
    )

    combined_outputs = "\n\n".join(outputs)
    final_prompt = (
        "Du bist der Projektmanager. Die folgenden Subtasks wurden ausgeführt:\n\n"
        f"{combined_outputs}\n\n"
        "AUFGABE: Synthetisiere die Ergebnisse in eine KOHÄRENTE Antwort, die:\n"
        "1. Redundanz entfernt (nicht einfach alles wiederholen)\n"
        "2. Widersprüche identifiziert\n"
        "3. Eine klare Empfehlung oder Zusammenfassung gibt\n\n"
        "Wenn alle Subtasks dasselbe sagen, fasse es in EINEM Satz zusammen.\n"
    )
    if strategy:
        final_prompt += f"\nStrategie (vom Planner vorgeschlagen): {strategy}\n"
    if steps_text:
        final_prompt += f"Vorgeschlagene Schritte (vom Planner):\n{steps_text}\n"

    history = memory_system.load_relevant_context(
        merge_agent,
        final_prompt,
        limit=2,
    )
    ui.status(
        f"Merge-Ausgabe mit Agent '{merge_agent.display_name}' wird berechnet...",
        "info",
    )

    merge_response = ""
    displayed = False
    use_streaming = hasattr(llm_interface, "stream_chat") or hasattr(
        llm_interface, "stream_generate_response"
    )

    if use_streaming:
        try:
            chunks: list[str] = []
            ui.stream_prefix(f"{merge_label}")
            if hasattr(llm_interface, "stream_chat"):
                iterator = llm_interface.stream_chat(
                    system_prompt=merge_agent.system_prompt,
                    user_prompt=final_prompt,
                    timeout=timeout_value,
                    max_tokens=merge_token_limit,
                )
            else:
                iterator = llm_interface.stream_generate_response(
                    system_prompt=merge_agent.system_prompt,
                    user_prompt=final_prompt,
                    history=history,
                    timeout=timeout_value,
                    max_output_tokens=merge_token_limit,
                )
            for chunk in iterator:
                if chunk:
                    chunks.append(chunk)
                    ui.streaming_chunk(chunk)
            print()
            merge_response = "".join(chunks)
            displayed = True
        except Exception as stream_exc:
            ui.status(
                f"Merge-Streaming fehlgeschlagen ({stream_exc}). Fallback auf Block-Modus.",
                "warning",
            )
            print()
            use_streaming = False

    if not displayed:
        try:
            if hasattr(llm_interface, "chat"):
                merge_response = llm_interface.chat(
                    system_prompt=merge_agent.system_prompt,
                    user_prompt=final_prompt,
                    timeout=timeout_value,
                    max_tokens=merge_token_limit,
                )
            else:
                merge_response = llm_interface.generate_response(
                    system_prompt=merge_agent.system_prompt,
                    user_prompt=final_prompt,
                    history=history,
                    timeout=timeout_value,
                    max_output_tokens=merge_token_limit,
                )
            ui.stream_prefix(f"{merge_label}")
            ui.typing_animation(merge_response)
            displayed = True
        except Exception as exc:  # pragma: no cover
            ui.status(f"Merge-Ausgabe fehlgeschlagen: {exc}", "error")
            return False

    if not merge_response or not merge_response.strip():
        ui.status("Merge-Backend lieferte keinen Inhalt.", "warning")
        return False

    result_path = memory_system.save_conversation(
        merge_agent,
        final_prompt,
        merge_response,
    )

    if not displayed:
        ui.status("Merge-Ergebnis gespeichert.", "success")
    else:
        ui.status("Merge-Ergebnis abgeschlossen.", "success")

    plan_data.setdefault("metadata", {})
    plan_data["metadata"].update(
        {
            "merge_agent": merge_agent.key,
            "merge_provider": merge_backend.get("name"),
            "merge_provider_type": merge_backend.get("type"),
            "merge_model": merge_backend.get("model"),
            "merge_backend_label": merge_label,
            "merge_base_url": merge_backend.get("base_url"),
            "merge_max_tokens": merge_token_limit,
            "merge_timeout": timeout_value,
            "merge_result_path": str(result_path) if result_path else None,
        }
    )
    _save_plan_file(plan_path, plan_data)
    return True


def _select_merge_backend(
    ui: TerminalUI,
    llm_interface,
    backend_label: str | None,
    merge_providers: dict[str, dict[str, object]],
    active_merge_provider: str | None,
    merge_provider_order: list[str] | None = None,
) -> dict[str, object]:
    """Erlaubt dem Nutzer die Auswahl des Merge-Backends."""

    default_label = backend_label or "AnythingLLM"
    backends: list[dict[str, object]] = [
        {
            "label": default_label,
            "type": "anythingllm",
            "interface": llm_interface,
            "max_tokens": 2048,
            "name": "anythingllm",
        }
    ]
    options: list[str] = [f"{default_label} (aktuelles LLM)"]

    provider_names = list(merge_provider_order or merge_providers.keys())
    for name in provider_names:
        info = merge_providers.get(name)
        if not info:
            continue
        if "interface" not in info:
            continue
        backend_entry = dict(info)
        backend_entry.setdefault("label", name)
        backend_entry.setdefault("name", name)
        backends.append(backend_entry)
        options.append(
            f"{name} [{backend_entry.get('type', 'custom')}] {backend_entry.get('model')}"
        )

    if len(backends) == 1:
        return backends[0]

    default_index = 0
    if active_merge_provider:
        for idx, backend in enumerate(backends):
            if backend.get("name") == active_merge_provider:
                default_index = idx
                break

    choice = ui.choose_option(
        "Merge-Backend auswählen",
        options,
        default_index=default_index,
    )
    return backends[choice]

def _load_anythingllm(config, streaming_enabled, ui: TerminalUI):
    try:
        stream_timeout = getattr(config.system, "stream_timeout", None)
        timeout_value = float(stream_timeout) if stream_timeout is not None else 60.0
        interface = AnythingLLMInterface(
            api_key=config.npu_provider.api_key,
            base_url=config.npu_provider.base_url,
            workspace_slug=config.npu_provider.workspace_slug,
            stream=streaming_enabled,
            timeout=timeout_value,
        )
        ui.status("AnythingLLM-Verbindung aktiv. NPU-Inferenz bereit.", "success")
        return interface, "anythingllm"
    except Exception as exc:
        ui.status(f"AnythingLLM nicht verfügbar: {exc}", "warning")
        return None, None


def _load_qnn(models_root: Path, ui: TerminalUI):
    try:
        from selfai.core.npu_llm_interface import NpuLLMInterface, find_qnn_models
    except ImportError:
        ui.status("`npu_llm_interface` nicht gefunden. Überspringe QNN-Pfad.", "warning")
        return None, None

    qnn_models = find_qnn_models(models_root)
    if not qnn_models:
        ui.status("Keine QNN-Modelle gefunden.", "warning")
        return None, None

    ui.status(f"Gefunden: {len(qnn_models)} QNN (NPU) Modell(e).", "info")
    model_path = qnn_models[0]
    try:
        ui.status(f"Versuche QNN-Modell zu laden: {model_path.name}", "info")
        interface = NpuLLMInterface(model_path=str(model_path))
        ui.status(f"QNN-Modell '{model_path.name}' aktiv.", "success")
        return interface, f"qnn:{model_path.name}"
    except (ImportError, FileNotFoundError, RuntimeError) as exc:
        ui.status(f"Fehler beim Laden des QNN-Modells: {exc}", "warning")
        return None, None


def _load_cpu(models_root: Path, ui: TerminalUI):
    candidates = [
        "Phi-3-mini-4k-instruct.Q4_K_M.gguf",
        "deepseek-llm-7b-chat.Q4_K_M.gguf",
    ]
    for model_filename in candidates:
        model_path = models_root / model_filename
        if not model_path.exists():
            continue
        try:
            ui.status(f"Versuche CPU-Modell zu laden: {model_path}", "info")
            interface = LocalLLMInterface(model_path=str(model_path))
            ui.status(
                f"CPU-Modell '{model_filename}' erfolgreich geladen und aktiv.",
                "success",
            )
            return interface, f"cpu:{model_filename}"
        except (FileNotFoundError, RuntimeError, ImportError) as exc:
            ui.status(f"Fehler beim Laden von '{model_filename}': {exc}", "warning")

    return None, None


def main():
    ui = TerminalUI()
    ui.clear()
    ui.banner()
    ui.status("SelfAI wird gestartet...", "info")
    _show_pipeline_overview(ui)

    agents_path = project_root / "agents"
    agent_manager = AgentManager(agents_dir=agents_path)

    memory_path = project_root / "memory"
    memory_system = MemorySystem(memory_dir=memory_path)

    if not agent_manager.agents:
        ui.status("Keine Agenten gefunden. Das Programm wird beendet.", "error")
        return

    available_agents = agent_manager.list_agents()

    llm_interface = None
    backend_label = None
    models_root = project_root.parent / "models"

    config = None
    streaming_enabled = False
    planner_cfg = None
    planner_providers: dict[str, dict[str, object]] = {}
    planner_provider_order: list[str] = []
    active_planner_provider: str | None = None
    merge_cfg = None
    merge_providers: dict[str, dict[str, object]] = {}
    merge_provider_order: list[str] = []
    active_merge_provider: str | None = None
    ui.status("Verbinde mit AnythingLLM (NPU)...", "info")
    try:
        config = load_configuration()
        ui.status("Konfiguration geladen.", "success")
        streaming_enabled = bool(
            getattr(config.system, "streaming_enabled", False)
        )
        planner_cfg = getattr(config, "planner", None)
        merge_cfg = getattr(config, "merge", None)
        if planner_cfg and planner_cfg.enabled:
            provider_list = ", ".join(
                provider.name for provider in planner_cfg.providers
            ) or "(keine Provider)"
            ui.status(
                f"Planner aktiviert. Provider: {provider_list}",
                "info",
            )
        else:
            ui.status("Ollama-Planner deaktiviert.", "info")

        _show_system_resources(ui)
    except (FileNotFoundError, ValueError) as exc:
        ui.status(f"Konfiguration nicht verfügbar: {exc}", "warning")
    except Exception as exc:
        ui.status(f"Unerwarteter Konfigurationsfehler: {exc}", "error")

    if config and planner_cfg and planner_cfg.enabled:
        for provider_cfg in planner_cfg.providers:
            unresolved_headers = [
                value
                for value in provider_cfg.headers.values()
                if isinstance(value, str) and "${" in value
            ]
            if unresolved_headers:
                ui.status(
                    f"Planner-Provider '{provider_cfg.name}' übersprungen: fehlende Zugangsdaten.",
                    "warning",
                )
                continue
            try:
                interface = PlannerOllamaInterface(
                    base_url=provider_cfg.base_url,
                    model=provider_cfg.model,
                    timeout=provider_cfg.timeout,
                    max_tokens=provider_cfg.max_tokens,
                    headers=provider_cfg.headers,
                )
                interface.healthcheck()
                planner_providers[provider_cfg.name] = {
                    "type": provider_cfg.type,
                    "interface": interface,
                    "model": provider_cfg.model,
                    "base_url": provider_cfg.base_url,
                }
                planner_provider_order.append(provider_cfg.name)
                ui.status(
                    f"Planner-Provider '{provider_cfg.name}' ({provider_cfg.type}) aktiv.",
                    "success",
                )
            except PlannerError as exc:
                ui.status(
                    f"Planner-Provider '{provider_cfg.name}' nicht erreichbar: {exc}",
                    "warning",
                )
            except Exception as exc:  # pragma: no cover - defensive
                ui.status(
                    f"Planner-Provider '{provider_cfg.name}' Fehler: {exc}",
                    "warning",
                )

    if planner_providers:
        stored_provider = _load_active_planner(memory_system)
        if stored_provider and stored_provider in planner_providers:
            active_planner_provider = stored_provider
        else:
            active_planner_provider = planner_provider_order[0]
            _save_active_planner(memory_system, active_planner_provider)
        ui.status(
            f"Aktiver Planner-Provider: {active_planner_provider}", "info"
        )
    else:
        ui.status("Kein Planner-Provider verfügbar.", "warning")

    if merge_cfg and merge_cfg.enabled:
        for provider in merge_cfg.providers:
            try:
                interface = MergeOllamaInterface(
                    base_url=provider.base_url,
                    model=provider.model,
                    timeout=provider.timeout,
                    max_tokens=provider.max_tokens,
                    headers=provider.headers,
                )
                merge_providers[provider.name] = {
                    "type": provider.type,
                    "interface": interface,
                    "model": provider.model,
                    "base_url": provider.base_url,
                    "max_tokens": provider.max_tokens,
                    "timeout": provider.timeout,
                }
                merge_provider_order.append(provider.name)
                ui.status(
                    f"Merge-Provider '{provider.name}' ({provider.type}) aktiv.",
                    "info",
                )
            except Exception as exc:
                ui.status(
                    f"Merge-Provider '{provider.name}' Fehler: {exc}",
                    "warning",
                )

    if merge_providers:
        stored_merge = _load_active_merge(memory_system)
        if stored_merge and stored_merge in merge_providers:
            active_merge_provider = stored_merge
        else:
            active_merge_provider = merge_provider_order[0]
            _save_active_merge(memory_system, active_merge_provider)
        ui.status(
            f"Aktiver Merge-Provider: {active_merge_provider}", "info"
        )
    else:
        ui.status("Kein zusätzlicher Merge-Provider konfiguriert.", "info")

    execution_backends: list[dict[str, object]] = []

    if config:
        interface_any, label_any = _load_anythingllm(
            config, streaming_enabled, ui
        )
        if interface_any:
            execution_backends.append(
                {
                    "interface": interface_any,
                    "label": label_any or "AnythingLLM",
                    "name": "anythingllm",
                    "type": "npu",
                }
            )

    ui.status("Prüfe lokale QNN-Backends...", "info")
    interface_qnn, label_qnn = _load_qnn(models_root, ui)
    if interface_qnn:
        execution_backends.append(
            {
                "interface": interface_qnn,
                "label": label_qnn or "QNN",
                "name": "qnn",
                "type": "qnn",
            }
        )

    ui.status("Prüfe CPU-Backends...", "info")
    interface_cpu, label_cpu = _load_cpu(models_root, ui)
    if interface_cpu:
        execution_backends.append(
            {
                "interface": interface_cpu,
                "label": label_cpu or "CPU",
                "name": "cpu",
                "type": "cpu",
            }
        )

    if not execution_backends:
        ui.status(
            "Keines der verfügbaren LLM-Backends (AnythingLLM, QNN, CPU) konnte geladen werden.",
            "error",
        )
        ui.status("Bitte Konfiguration und Modelle prüfen.", "info")
        return

    llm_interface = execution_backends[0]["interface"]
    backend_label = execution_backends[0].get("label") or "Plan"

    default_key = None
    if config and getattr(config, "agent_config", None):
        default_key = getattr(config.agent_config, "default_agent", None)

    if default_key:
        try:
            agent_manager.switch_agent(default_key)
        except ValueError:
            ui.status(
                f"Standard-Agent '{default_key}' nicht gefunden. Fallback auf Liste.",
                "warning",
            )

    if agent_manager.active_agent is None:
        try:
            first_agent = available_agents[0]
            agent_manager.switch_agent(first_agent.key)
        except (IndexError, ValueError) as exc:
            ui.status(f"Fehler beim Setzen des Standard-Agenten: {exc}", "error")
            return

    ui.status(
        f"Aktiver Agent: {agent_manager.active_agent.display_name}", "success"
    )
    ui.list_agents(
        agent_manager.agents,
        active_key=agent_manager.active_agent.key,
    )
    available_agents = agent_manager.list_agents()

    command_hint = "Bereit. Nachricht eingeben, "
    if planner_providers:
        command_hint += "'/plan <Ziel>' für DPPM-Plan, '/planner list' für Provider, "
    command_hint += "'/switch <Name|Nummer>' zum Wechseln, 'quit' zum Beenden."
    ui.status(command_hint, "info")

    active_chat_backend_index = 0

    def _generate_with_backend(
        interface,
        label: str,
        system_prompt: str,
        user_prompt: str,
        history_messages,
    ) -> tuple[str, bool]:
        use_stream = streaming_enabled and hasattr(interface, "stream_generate_response")
        if use_stream:
            chunks: list[str] = []
            first_chunk = True
            try:
                for chunk in interface.stream_generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    history=history_messages,
                ):
                    if not chunk:
                        continue
                    if first_chunk:
                        ui.stop_spinner()
                        ui.stream_prefix(label)
                        first_chunk = False
                    chunks.append(chunk)
                    ui.streaming_chunk(chunk)
                if first_chunk:
                    ui.stop_spinner()
                else:
                    print()
                return "".join(chunks), True
            except Exception as exc:  # pylint: disable=broad-except
                ui.stop_spinner()
                ui.status(
                    f"Streaming-Fehler am Backend '{label}': {exc}",
                    "warning",
                )
                use_stream = False

        try:
            ui.stop_spinner()
            ui.stream_prefix(label)
            response = interface.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                history=history_messages,
            )
            return response, False
        except Exception as exc:  # pylint: disable=broad-except
            raise RuntimeError(exc) from exc

    while True:
        user_input = input("\nDu: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break

        if user_input.lower() == "/memory":
            categories = memory_system.list_categories()
            if categories:
                ui.status("Aktive Memory-Kategorien:", "info")
                for cat in categories:
                    ui.status(f"- {cat}", "info")
            else:
                ui.status("Keine Memory-Kategorien vorhanden.", "info")
            continue

        if user_input.lower().startswith("/memory clear"):
            parts = user_input.split()
            category = None
            keep = None
            if len(parts) >= 3:
                category = parts[2]
            else:
                categories = memory_system.list_categories()
                if not categories:
                    ui.status("Kein Memory vorhanden.", "info")
                    continue
                choice = ui.choose_option(
                    "Welche Memory-Kategorie löschen?",
                    categories,
                    default_index=0,
                )
                category = categories[choice]
            if len(parts) >= 4:
                try:
                    keep = max(0, int(parts[3]))
                except ValueError:
                    keep = None
            removed = memory_system.clear_category(category, keep)
            if removed == 0:
                ui.status(f"Keine Einträge aus '{category}' entfernt.", "info")
            elif keep is None:
                ui.status(f"Memory '{category}' komplett geleert ({removed} Einträge).", "success")
            else:
                ui.status(
                    f"Memory '{category}' reduziert. {removed} alte Einträge entfernt, {keep} behalten.",
                    "success",
                )
            continue

        if user_input.lower().startswith("/planner"):
            if not planner_providers:
                ui.status("Kein Planner-Provider konfiguriert.", "warning")
                continue

            parts = user_input.split()
            subcommand = parts[1].lower() if len(parts) > 1 else "list"

            if subcommand == "list":
                ui.status("Verfügbare Planner-Provider:", "info")
                for idx, name in enumerate(planner_provider_order, start=1):
                    info = planner_providers.get(name)
                    if not info:
                        continue
                    marker = "(aktiv)" if name == active_planner_provider else ""
                    ui.status(
                        f"{idx}. {name} [{info['type']}] {info['model']} {marker}",
                        "info",
                    )
                continue

            if subcommand == "use" and len(parts) >= 3:
                desired = parts[2]
                info = planner_providers.get(desired)
                if not info:
                    ui.status(
                        f"Planner-Provider '{desired}' ist nicht verfügbar.",
                        "error",
                    )
                    continue
                active_planner_provider = desired
                _save_active_planner(memory_system, desired)
                ui.status(
                    f"Aktiver Planner-Provider gesetzt auf '{desired}'.",
                    "success",
                )
                continue

            ui.status("Verwendung: /planner list | /planner use <Name>", "info")
            continue

        if user_input.lower().startswith("/plan"):
            if not planner_providers:
                ui.status(
                    "Kein Planner-Provider aktiv. Bitte Konfiguration prüfen.",
                    "warning",
                )
                continue

            parts = user_input.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                ui.status("Bitte Zielbeschreibung angeben: /plan <Ziel>", "warning")
                continue

            goal_text = parts[1].strip()
            ui.status(f"Erzeuge Plan für: {goal_text}", "info")

            planner_context = _build_planner_context(agent_manager, memory_system)

            plan_data = None
            selected_provider_name = None

            ordered_names: list[str] = []
            if active_planner_provider and active_planner_provider in planner_providers:
                ordered_names.append(active_planner_provider)
            for name in planner_provider_order:
                if name not in ordered_names and name in planner_providers:
                    ordered_names.append(name)

            for provider_name in ordered_names:
                info = planner_providers.get(provider_name)
                if not info:
                    continue
                provider_type = info["type"]
                provider_interface = info["interface"]
                ui.status(
                    f"Nutze Planner-Provider '{provider_name}' ({provider_type})...",
                    "info",
                )
                stream_state = {"active": False}

                def _planner_stream(chunk: str) -> None:
                    if not stream_state["active"]:
                        ui.stream_prefix(f"Planner-{provider_name}")
                        stream_state["active"] = True
                    ui.streaming_chunk(chunk)

                try:
                    plan_data = provider_interface.plan(
                        goal_text,
                        planner_context,
                        progress_callback=_planner_stream,
                    )
                    if stream_state["active"]:
                        print()
                    selected_provider_name = provider_name
                    ui.status(
                        f"Planner '{provider_name}' hat einen Plan geliefert.",
                        "success",
                    )
                    ui.status(
                        "Planungsphase abgeschlossen: Subtasks stehen für die Ausführung bereit.",
                        "info",
                    )
                    break
                except PlannerError as exc:
                    if stream_state["active"]:
                        print()
                    hint = ""
                    cause = getattr(exc, "__cause__", None)
                    if isinstance(cause, PlanValidationError):
                        hint = " (Planaufbau entspricht nicht dem Schema)"
                        faulty_plan = getattr(cause, "plan_data", None)
                        ui.status(
                            "Der Planner hat einen unvollständigen oder fehlerhaften Plan geliefert.",
                            "warning",
                        )
                        ui.status(
                            "Hinweis: Agent Keys müssen zu deinen SelfAI-Agenten passen und 'parallel_group' muss >= 1 sein.",
                            "info",
                        )
                        if faulty_plan:
                            ui.status(
                                f"Fehlerquelle (Provider '{provider_name}'):",
                                "warning",
                            )
                            ui.show_plan(faulty_plan)
                    ui.status(
                        f"Planner '{provider_name}' fehlgeschlagen: {exc}{hint}",
                        "warning",
                    )
                    continue

            if plan_data is None:
                ui.status(
                    "Keiner der Planner-Provider konnte einen Plan erstellen. Erzeuge Fallback-Plan.",
                    "warning",
                )
                fallback_agent_key = _default_agent_key(agent_manager)
                if not fallback_agent_key:
                    ui.status(
                        "Fallback fehlgeschlagen: Kein Agent verfügbar. Bitte Konfiguration prüfen.",
                        "error",
                    )
                    continue
                plan_data = _build_fallback_plan(goal_text, fallback_agent_key)
                selected_provider_name = "fallback"
                ui.status(
                    f"Fallback-Plan erstellt (Agent '{fallback_agent_key}').",
                    "info",
                )

            _sanitize_plan_agents(plan_data, agent_manager, ui)
            _announce_plan_agents(plan_data, agent_manager, ui)
            ui.show_plan(plan_data)

            logic_messages = validate_plan_logic(plan_data)
            proceed_with_plan = True
            if logic_messages:
                has_error = any(msg.startswith("FEHLER") for msg in logic_messages)
                for msg in logic_messages:
                    level = "error" if msg.startswith("FEHLER") else "warning"
                    ui.status(msg, level)
                prompt_text = (
                    "Plan enthält kritische Fehler. Trotzdem übernehmen?"
                    if has_error
                    else "Plan enthält Warnungen. Trotzdem übernehmen?"
                )
                proceed_with_plan = ui.confirm(prompt_text, default_yes=False)

            if not proceed_with_plan:
                ui.status("Plan verworfen.", "warning")
                continue

            if not ui.confirm_plan():
                ui.status("Plan verworfen.", "warning")
                continue

            try:
                plan_data.setdefault("metadata", {})
                provider_metadata = planner_providers.get(
                    selected_provider_name, {}
                )
                plan_data["metadata"].update(
                    {
                        "planner_provider": selected_provider_name,
                        "planner_provider_type": provider_metadata.get("type"),
                        "planner_model": provider_metadata.get("model"),
                        "goal": goal_text,
                    }
                )
                if (
                    selected_provider_name
                    and selected_provider_name in planner_providers
                    and selected_provider_name != active_planner_provider
                ):
                    active_planner_provider = selected_provider_name
                    _save_active_planner(memory_system, selected_provider_name)
                    ui.status(
                        f"Aktiver Planner-Provider aktualisiert auf '{selected_provider_name}'.",
                        "info",
                    )
                plan_path = memory_system.save_plan(goal_text, plan_data)
                try:
                    display_path = plan_path.relative_to(project_root)
                except ValueError:
                    display_path = plan_path
                ui.status(f"Plan gespeichert: {display_path}", "success")
                ui.status(
                    "Plan gespeichert. Als nächstes folgt die Ausführungsphase.",
                    "info",
                )
            except OSError:
                ui.status("Plan konnte nicht gespeichert werden (siehe Log).", "error")
                continue

            if llm_interface is None:
                ui.status(
                    "LLM-Backend nicht verfügbar. Ausführung übersprungen.",
                    "warning",
                )
                continue

            if not ui.confirm_execution():
                ui.status("Ausführung übersprungen. Plan bleibt gespeichert.", "info")
                continue

            try:
                dispatcher = ExecutionDispatcher(
                    plan_path=plan_path,
                    agent_manager=agent_manager,
                    memory_system=memory_system,
                    llm_backends=execution_backends,
                    ui=ui,
                    backend_label=backend_label,
                    llm_timeout=getattr(planner_cfg, "execution_timeout", None),
                    retry_attempts=2,
                    retry_delay=5.0,
                    max_output_tokens=1024,
                )
                dispatcher.run()
                ui.status("Plan erfolgreich ausgeführt.", "success")
                ui.status(
                    "Ausführungsphase erfolgreich abgeschlossen. Prüfe Merge-Optionen.",
                    "info",
                )

                primary_backend = execution_backends[0]
                default_merge_backend = {
                    "label": primary_backend.get("label") or backend_label or "AnythingLLM",
                    "type": primary_backend.get("type", "anythingllm"),
                    "interface": primary_backend.get("interface"),
                    "max_tokens": 2048,
                    "name": primary_backend.get("name", "anythingllm"),
                    "model": primary_backend.get("label")
                    or primary_backend.get("name")
                    or backend_label
                    or "anythingllm",
                    "timeout": getattr(planner_cfg, "execution_timeout", None)
                    if planner_cfg
                    else None,
                }

                merge_backend = default_merge_backend
                if plan_data.get("merge"):
                    if merge_providers:
                        merge_backend = _select_merge_backend(
                            ui,
                            llm_interface,
                            backend_label,
                            merge_providers,
                            active_merge_provider,
                            merge_provider_order,
                        )
                    selected_name = merge_backend.get("name")
                    if selected_name and selected_name != active_merge_provider:
                        active_merge_provider = selected_name
                        _save_active_merge(memory_system, selected_name)
                        ui.status(
                            f"Aktiver Merge-Provider gesetzt auf '{selected_name}'.",
                            "info",
                        )

                merge_timeout = getattr(planner_cfg, "execution_timeout", None)
                merge_success = _execute_merge_phase(
                    plan_path,
                    merge_backend=merge_backend,
                    agent_manager=agent_manager,
                    memory_system=memory_system,
                    ui=ui,
                    execution_timeout=merge_timeout,
                )

                if not merge_success:
                    current_name = merge_backend.get("name")
                    default_name = default_merge_backend.get("name")

                    fallback_candidates: list[dict[str, object]] = []
                    if merge_providers:
                        provider_names = merge_provider_order or list(merge_providers.keys())
                        for name in provider_names:
                            if name == current_name:
                                continue
                            info = merge_providers.get(name)
                            if not info or "interface" not in info:
                                continue
                            candidate_backend = dict(info)
                            candidate_backend.setdefault("label", name)
                            candidate_backend["name"] = name
                            fallback_candidates.append(candidate_backend)

                    if current_name != default_name:
                        fallback_candidates.append(default_merge_backend)

                    fallback_done = False
                    for candidate in fallback_candidates:
                        label = candidate.get("label") or candidate.get("name") or "Fallback"
                        ui.status(
                            f"Merge fehlgeschlagen. Versuche Fallback-Backend '{label}'.",
                            "warning",
                        )
                        fallback_success = _execute_merge_phase(
                            plan_path,
                            merge_backend=candidate,
                            agent_manager=agent_manager,
                            memory_system=memory_system,
                            ui=ui,
                            execution_timeout=merge_timeout,
                        )
                        if fallback_success:
                            fallback_done = True
                            break

                    if not fallback_done:
                        fallback_agent = _select_merge_agent_from_plan(
                            plan_data.get("merge") or {},
                            agent_manager,
                        )
                        if fallback_agent is None:
                            fallback_agent = agent_manager.active_agent
                        entries = _collect_subtask_entries(plan_data)
                        fallback_text = _render_fallback_merge(entries)
                        ui.status(
                            "Alle Merge-Backends schlugen fehl. Führe SelfAI-Fallback-Zusammenfassung aus.",
                            "warning",
                        )
                        ui.stream_prefix("SelfAI-Fallback")
                        ui.typing_animation(fallback_text)
                        result_path = memory_system.save_conversation(
                            fallback_agent,
                            "Fallback Merge Summary",
                            fallback_text,
                        )
                        plan_data.setdefault("metadata", {})
                        plan_data["metadata"].update(
                            {
                                "merge_agent": fallback_agent.key if fallback_agent else None,
                                "merge_provider": "fallback-summary",
                                "merge_provider_type": "internal",
                                "merge_model": "selfai-fallback",
                                "merge_backend_label": "SelfAI-Fallback",
                                "merge_base_url": None,
                                "merge_max_tokens": None,
                                "merge_timeout": None,
                                "merge_result_path": str(result_path) if result_path else None,
                            }
                        )
                        _save_plan_file(plan_path, plan_data)
                        ui.status("Fallback-Zusammenfassung abgeschlossen.", "success")
                        ui.status(
                            "Merge konnte mit keinem verfügbaren Backend abgeschlossen werden.",
                            "error",
                        )
            except ExecutionError as exc:
                ui.status(f"Plan-Ausführung abgebrochen: {exc}", "error")
            except Exception as exc:  # pylint: disable=broad-except
                ui.status(f"Unerwarteter Ausführungsfehler: {exc}", "error")

            continue

        if user_input.lower().startswith("/switch "):
            agent_name_raw = user_input.split(" ", 1)[1]
            try:
                candidate = agent_name_raw.strip()
                normalized = candidate.rstrip(".").strip()

                if normalized.isdigit():
                    index = int(normalized) - 1
                    if index < 0 or index >= len(available_agents):
                        raise ValueError(
                            f"Agent mit Nummer {normalized} existiert nicht."
                        )
                    selected = available_agents[index]
                    agent_manager.switch_agent(selected.key)
                else:
                    agent_manager.switch_agent(candidate)
                ui.status(
                    f"Aktiver Agent: {agent_manager.active_agent.display_name}",
                    "info",
                )
                ui.list_agents(
                    agent_manager.agents,
                    active_key=agent_manager.active_agent.key,
                )
                available_agents = agent_manager.list_agents()
            except ValueError as exc:
                ui.status(str(exc), "error")
            continue

        system_prompt = agent_manager.active_agent.system_prompt
        history = memory_system.load_relevant_context(
            agent_manager.active_agent,
            user_input,
            limit=2,
        )
        response_text = None
        streamed = False
        last_error = None
        order = [active_chat_backend_index] + [
            idx for idx in range(len(execution_backends)) if idx != active_chat_backend_index
        ]

        for backend_index in order:
            backend = execution_backends[backend_index]
            interface = backend.get("interface")
            label = backend.get("label") or backend.get("name") or backend_label or "SelfAI"
            try:
                ui.start_spinner("SelfAI denkt nach...")
                response_text, streamed = _generate_with_backend(
                    interface,
                    label,
                    system_prompt,
                    user_input,
                    history,
                )
                active_chat_backend_index = backend_index
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_error = exc
                ui.status(
                    f"LLM-Backend '{label}' fehlgeschlagen: {exc}",
                    "warning",
                )
                continue

        if response_text is None:
            ui.status(
                f"Keine Antwort von den LLM-Backends ({last_error}).",
                "error",
            )
            continue

        if not streamed:
            ui.typing_animation(response_text)

        memory_system.save_conversation(
            agent=agent_manager.active_agent,
            user_prompt=user_input,
            llm_response=response_text,
        )


if __name__ == "__main__":
    main()
