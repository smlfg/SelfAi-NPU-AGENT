# core/agent_manager.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class Agent:
    key: str
    display_name: str
    workspace_slug: str
    system_prompt: str
    memory_categories: list[str]
    color: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    path: Optional[Path] = None


class AgentManager:
    def __init__(self, agents_dir: Path):
        self.agents_dir = agents_dir
        self.agents: Dict[str, Agent] = self._load_agents()
        self.active_agent: Agent | None = None

    def _load_agents(self) -> Dict[str, Agent]:
        agents: Dict[str, Agent] = {}
        if not self.agents_dir.is_dir():
            print(f"Warnung: Agenten-Verzeichnis nicht gefunden: {self.agents_dir}")
            return agents

        # 1. Neue Verzeichnis-basierte Struktur
        for folder in sorted(self.agents_dir.iterdir()):
            if not folder.is_dir():
                continue
            if folder.name.startswith("_"):
                continue

            config_path = folder / "config.yaml"
            if not config_path.is_file():
                print(f"⚠️  Überspringe {folder.name}: config.yaml fehlt.")
                continue

            try:
                with config_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                agent_cfg = data.get("agent", {})
            except (yaml.YAMLError, OSError) as exc:
                print(f"⚠️  Fehler beim Laden von {config_path}: {exc}")
                continue

            required = [
                "name",
                "display_name",
                "workspace_slug",
                "memory_categories",
                "color",
                "system_prompt_file",
            ]
            if not all(field in agent_cfg for field in required):
                print(f"⚠️  In {config_path} fehlen Pflichtfelder.")
                continue

            prompt_path = folder / agent_cfg["system_prompt_file"]
            if not prompt_path.is_file():
                print(f"⚠️  System-Prompt-Datei fehlt: {prompt_path}")
                continue

            try:
                system_prompt = prompt_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                print(f"⚠️  System-Prompt konnte nicht gelesen werden ({prompt_path}): {exc}")
                continue

            key = agent_cfg["name"].lower()
            agent = Agent(
                key=key,
                display_name=agent_cfg["display_name"],
                workspace_slug=agent_cfg["workspace_slug"],
                system_prompt=system_prompt,
                memory_categories=agent_cfg.get("memory_categories", []),
                color=agent_cfg.get("color", "white"),
                description=agent_cfg.get("description", ""),
                tags=agent_cfg.get("tags", []),
                path=folder,
            )
            agents[key] = agent

        # 2. Fallback: Legacy *.yaml Dateien (Kompatibilität)
        legacy_files = [
            path for path in sorted(self.agents_dir.glob("*.yaml"))
            if not path.name.startswith("_")
        ]
        for file_path in legacy_files:
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                agent_cfg = data.get("agent", {})
            except (yaml.YAMLError, OSError) as exc:
                print(f"⚠️  Fehler beim Laden von {file_path}: {exc}")
                continue

            required_legacy = [
                "name",
                "workspace_slug",
                "system_prompt",
                "memory_categories",
                "display_name",
                "color",
            ]
            if not all(field in agent_cfg for field in required_legacy):
                continue

            key = agent_cfg["name"].lower()
            if key in agents:
                continue  # Directory version hat Vorrang

            agent = Agent(
                key=key,
                display_name=agent_cfg["display_name"],
                workspace_slug=agent_cfg["workspace_slug"],
                system_prompt=agent_cfg["system_prompt"],
                memory_categories=agent_cfg.get("memory_categories", []),
                color=agent_cfg.get("color", "white"),
                description=agent_cfg.get("description", ""),
                tags=agent_cfg.get("tags", []),
                path=file_path.parent,
            )
            agents[key] = agent

        return dict(sorted(agents.items(), key=lambda item: item[1].display_name.lower()))

    def list_agents(self) -> list[Agent]:
        return list(self.agents.values())

    def switch_agent(self, agent_name: str) -> Agent:
        key = agent_name.lower()
        agent = self.agents.get(key)
        if agent is None:
            agent = next(
                (a for a in self.agents.values() if a.display_name.lower() == key),
                None,
            )

        if agent is None:
            raise ValueError(f"Agent '{agent_name}' nicht gefunden.")

        self.active_agent = agent
        return agent

    def get(self, key: str) -> Optional[Agent]:
        return self.agents.get(key.lower())
