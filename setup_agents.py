#!/usr/bin/env python3
"""
Automatisches Setup-Script für SelfAI Agent-Konfigurationen.
Erstellt alle fehlenden Agent-Config-Dateien.
"""

import os
from pathlib import Path

# Projekt-Root
PROJECT_ROOT = Path(__file__).parent

# Agent-Konfigurationen
AGENT_CONFIGS = {
    "code_helfer": {
        "config.yaml": """agent:
  name: "code_helfer"
  display_name: "Code Helper"
  workspace_slug: "main"
  color: "cyan"
  description: "Ein spezialisierter Agent für Code-Analyse und Datei-Operationen"

  memory_categories:
    - code_analysis
    - file_operations

  system_prompt_file: "system_prompt.md"

  tools:
    - list_project_files
    - read_project_file
    - write_project_file
    - search_project_files
    - git_status
    - git_log
    - git_diff
    - count_lines_of_code
    - parse_json_file
""",
        "system_prompt.md": """Du bist ein spezialisierter Code-Helper-Agent.

Deine Aufgaben:
- Code-Analyse und Review
- Datei-Operationen (Lesen, Schreiben, Suchen)
- Git-Status und Änderungen prüfen
- Code-Qualität verbessern

Du hast Zugriff auf Tools für:
- Dateisystem-Operationen
- Git-Integration
- Code-Statistiken

Sei präzise, hilfreich und erkläre deine Schritte."""
    },

    "projektmanager": {
        "config.yaml": """agent:
  name: "projektmanager"
  display_name: "Projekt Manager"
  workspace_slug: "main"
  color: "green"
  description: "Ein Agent für Projektplanung und Organisation"

  memory_categories:
    - projektplanung
    - organisation

  system_prompt_file: "system_prompt.md"

  tools:
    - list_project_files
    - read_project_file
    - write_project_file
    - search_project_files
    - add_calendar_event
    - list_calendar_events
    - git_status
    - git_log
    - create_report
    - analyze_directory_structure
""",
        "system_prompt.md": """Du bist ein Projekt-Manager-Agent.

Deine Aufgaben:
- Projektplanung und Organisation
- Kalender-Management
- Berichte erstellen
- Projekt-Struktur analysieren

Du hast Zugriff auf:
- Datei- und Verzeichnis-Tools
- Kalender-Integration
- Report-Generierung
- Git-Integration

Sei organisiert, strukturiert und denke in Projekten."""
    }
}


def create_agent_configs():
    """Erstellt alle Agent-Konfigurationen."""
    agents_dir = PROJECT_ROOT / "agents"

    if not agents_dir.exists():
        print(f"❌ Agents-Verzeichnis nicht gefunden: {agents_dir}")
        return False

    success_count = 0
    skip_count = 0

    for agent_name, files in AGENT_CONFIGS.items():
        agent_dir = agents_dir / agent_name

        # Erstelle Agent-Verzeichnis falls nicht vorhanden
        if not agent_dir.exists():
            print(f"📁 Erstelle Verzeichnis: {agent_name}/")
            agent_dir.mkdir(parents=True, exist_ok=True)

        # Erstelle jede Datei
        for filename, content in files.items():
            file_path = agent_dir / filename

            if file_path.exists():
                print(f"⏭️  Überspringe (existiert): {agent_name}/{filename}")
                skip_count += 1
            else:
                print(f"✅ Erstelle: {agent_name}/{filename}")
                file_path.write_text(content, encoding="utf-8")
                success_count += 1

    print(f"\n{'='*60}")
    print(f"✅ Erfolgreich erstellt: {success_count} Dateien")
    print(f"⏭️  Übersprungen: {skip_count} Dateien")
    print(f"{'='*60}\n")

    return True


def verify_setup():
    """Verifiziert, dass alle benötigten Dateien vorhanden sind."""
    agents_dir = PROJECT_ROOT / "agents"

    print("🔍 Verifiziere Setup...\n")

    all_ok = True
    for agent_name in AGENT_CONFIGS.keys():
        agent_dir = agents_dir / agent_name

        # Prüfe config.yaml
        config_path = agent_dir / "config.yaml"
        if config_path.exists():
            print(f"✅ {agent_name}/config.yaml")
        else:
            print(f"❌ {agent_name}/config.yaml FEHLT!")
            all_ok = False

        # Prüfe system_prompt.md
        prompt_path = agent_dir / "system_prompt.md"
        if prompt_path.exists():
            print(f"✅ {agent_name}/system_prompt.md")
        else:
            print(f"❌ {agent_name}/system_prompt.md FEHLT!")
            all_ok = False

    print()

    # Prüfe Haupt-Config
    main_config = PROJECT_ROOT / "config.yaml"
    if main_config.exists():
        print(f"✅ config.yaml (Haupt-Konfiguration)")
    else:
        print(f"⚠️  config.yaml fehlt - bitte aus Template erstellen!")
        print(f"   Befehl: copy config.yaml.template config.yaml")
        all_ok = False

    # Prüfe .env
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        print(f"✅ .env (Umgebungsvariablen)")
    else:
        print(f"⚠️  .env fehlt - bitte aus Example erstellen!")
        print(f"   Befehl: copy .env.example .env")

    print(f"\n{'='*60}")
    if all_ok:
        print("🎉 SETUP KOMPLETT - SelfAI kann gestartet werden!")
        print("   Befehl: python selfai/selfai.py")
    else:
        print("⚠️  Es fehlen noch einige Dateien (siehe oben)")
    print(f"{'='*60}\n")

    return all_ok


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  SelfAI Agent Setup Script")
    print("="*60 + "\n")

    # Erstelle Konfigurationen
    if create_agent_configs():
        # Verifiziere
        verify_setup()
    else:
        print("❌ Setup fehlgeschlagen!")
