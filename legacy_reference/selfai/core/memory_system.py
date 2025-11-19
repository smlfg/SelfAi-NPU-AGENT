import json
import re
from datetime import datetime
from pathlib import Path

# Importiere die Agent-Klasse, um Type Hinting zu ermöglichen und auf Agent-Eigenschaften zuzugreifen.
from selfai.core.agent_manager import Agent
from selfai.core.context_filter import (
    TaskClassification,
    calculate_relevance,
    classify_task,
    extract_tags,
)

class MemorySystem:
    """Verwaltet das Speichern und Laden von Konversationen."""
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        # Kritisch: Stelle sicher, dass das Basis-Speicherverzeichnis existiert,
        # um spätere Schreibfehler zu vermeiden.
        self.memory_dir.mkdir(exist_ok=True)
        self.plan_dir = self.memory_dir / "plans"
        self.plan_dir.mkdir(exist_ok=True)

    def save_conversation(self, agent: Agent, user_prompt: str, llm_response: str):
        """
        Speichert eine vollständige Interaktion in einer formatierten Textdatei.
        """
        try:
            # 1. Kategorie ermitteln
            # Entscheidung: Wie gefordert, wird die erste Kategorie aus der Liste des Agenten verwendet.
            # Ein Fallback auf 'general' sorgt für Robustheit, falls keine Kategorien definiert sind.
            category = agent.memory_categories[0] if agent.memory_categories else "general"

            # 2. Kategorie-Verzeichnis erstellen
            category_dir = self.memory_dir / category
            category_dir.mkdir(exist_ok=True)

            # 3. Eindeutigen Dateinamen generieren
            now = datetime.now()
            timestamp_str = now.strftime("%Y%m%d-%H%M%S")
            # Entscheidung: Der `workspace_slug` des Agenten wird für einen sauberen, URL-sicheren Dateinamen verwendet.
            filename = f"{agent.workspace_slug}_{timestamp_str}.txt"
            filepath = category_dir / filename

            # 4. Tags ermitteln
            combined_text = f"{user_prompt}\n{llm_response}"
            fallback_tags = [category, agent.key]
            tags = extract_tags(combined_text, fallback_tags=fallback_tags)
            tags_line = ", ".join(tags)

            # 5. Inhalt gemäß Spezifikation formatieren
            content = (
                f"---"
                f"\nAgent: {agent.display_name}"
                f"\nAgentKey: {agent.key}"
                f"\nWorkspace: {agent.workspace_slug}"
                f"\nTimestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                f"\nTags: {tags_line}"
                f"\n---"
                f"\nSystem Prompt:"
                f"\n{agent.system_prompt}"
                f"\n---"
                f"\nUser:"
                f"\n{user_prompt}"
                f"\n---"
                f"\nSelfAI:"
                f"\n{llm_response}"
            )

            # 6. Datei schreiben
            filepath.write_text(content, encoding="utf-8")
            return filepath

        except Exception as e:
            # Kritisch: Fange alle Fehler während des Speichervorgangs ab, um die Hauptanwendung nicht zu blockieren.
            print(f"[Memory Error] Fehler beim Speichern der Konversation: {e}")
            return None

    def save_plan(self, goal: str, plan_data: dict) -> Path:
        """Speichert einen Planner-Plan als JSON-Datei und gibt den Pfad zurück."""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        goal_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", goal.strip()).strip("-") or "plan"
        filename = f"{timestamp}_{goal_slug}.json"
        filepath = self.plan_dir / filename

        try:
            filepath.write_text(
                json.dumps(plan_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"[Memory Error] Plan konnte nicht gespeichert werden: {exc}")
            raise

        return filepath

    def load_relevant_context(
        self,
        agent: Agent,
        current_text: str | None = None,
        *,
        limit: int = 3,
        threshold: float = 0.35,
    ) -> list:
        """
        Lädt Kontext aus dem Memory und filtert ihn anhand einfacher Tags.
        """

        categories = agent.memory_categories if agent.memory_categories else ["general"]
        candidate_files = self._get_candidate_files(categories)

        if not candidate_files or limit <= 0:
            return []

        # Maximal 50 Kandidaten prüfen, um IO zu begrenzen.
        max_candidates = min(len(candidate_files), 50)
        candidate_files = candidate_files[:max_candidates]

        classification: TaskClassification | None = None
        if current_text:
            classification = classify_task(current_text, agent.key)
        else:
            classification = TaskClassification(
                intent="general",
                tags=extract_tags("", fallback_tags=[agent.key, *categories]),
            )

        expected_tags = classification.tags if classification else []

        scored_files: list[dict[str, object]] = []
        for path in candidate_files:
            parsed = self._parse_memory_file(path)
            if not parsed:
                continue
            file_tags = parsed.get("tags") or []
            if not file_tags:
                file_tags = extract_tags("", fallback_tags=categories)

            score = calculate_relevance(expected_tags, file_tags)
            scored_files.append(
                {
                    "path": path,
                    "parsed": parsed,
                    "score": score,
                    "mtime": path.stat().st_mtime,
                }
            )

        if not scored_files:
            return []

        relevant = [item for item in scored_files if item["score"] >= threshold]
        if not relevant:
            relevant = scored_files[:limit]

        relevant.sort(key=lambda item: (item["score"], item["mtime"]), reverse=True)
        selected = relevant[:limit]
        # chronologisch sortieren (älteste zuerst), damit Verlauf Sinn ergibt
        selected.sort(key=lambda item: item["mtime"])

        context_messages: list[dict[str, str]] = []
        for entry in selected:
            parsed = entry["parsed"]
            user_part = parsed.get("user", "")
            assistant_part = parsed.get("assistant", "")
            if user_part:
                context_messages.append({"role": "user", "content": user_part})
            if assistant_part:
                context_messages.append({"role": "assistant", "content": assistant_part})

        return context_messages

    def clear_category(self, category: str, max_entries: int | None = None) -> int:
        target_dir = self.memory_dir / category
        if not target_dir.is_dir():
            return 0

        files = sorted(target_dir.glob("*.txt"))
        if max_entries is None:
            removed = len(files)
            for path in files:
                try:
                    path.unlink()
                except OSError:
                    pass
            return removed

        keep = max(0, int(max_entries))
        if keep >= len(files):
            return 0

        to_delete = files[:-keep]
        removed = 0
        for path in to_delete:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    def list_categories(self) -> list[str]:
        categories: list[str] = []
        for entry in sorted(self.memory_dir.iterdir()):
            if entry.is_dir():
                categories.append(entry.name)
        return categories

    def _parse_memory_file(self, path: Path) -> dict[str, object] | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None

        sections = raw.split("---")
        header = sections[1] if len(sections) > 1 else ""
        tags: list[str] = []
        for line in header.splitlines():
            if line.strip().lower().startswith("tags:"):
                _, _, value = line.partition(":")
                tags = [tag.strip() for tag in value.split(",") if tag.strip()]
                break

        user_text = ""
        assistant_text = ""
        for section in sections:
            stripped = section.strip()
            if stripped.lower().startswith("user:"):
                user_text = stripped[5:].strip()
            elif stripped.lower().startswith("selfai:"):
                assistant_text = stripped[7:].strip()

        return {
            "tags": tags,
            "user": user_text,
            "assistant": assistant_text,
            "raw": raw,
        }

    def _get_candidate_files(self, categories: list[str]) -> list[Path]:
        files: list[Path] = []
        for category in categories:
            directory = self.memory_dir / category
            if directory.is_dir():
                files.extend(directory.glob("*.txt"))
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return files
