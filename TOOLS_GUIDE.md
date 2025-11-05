# SelfAI Tool System - Vollständiger Leitfaden

## Übersicht

Das SelfAI Tool-System ermöglicht es Agenten, **konkrete Aktionen** auszuführen, wie z.B.:
- 📁 Dateien lesen, schreiben und durchsuchen
- 📅 Kalendereinträge verwalten
- 🚂 Zugverbindungen suchen
- 🌤️ Wetterdaten abrufen
- ...und vieles mehr!

### Neu in dieser Version

✅ **Tool-Support für normale Chat-Interaktionen** - Nicht nur für geplante Subtasks!
✅ **Hybrides Tool-Calling-Format** - Unterstützt JSON und textbasiertes Format
✅ **Automatische Fallback-Logik** - Funktioniert auch wenn Tools fehlschlagen
✅ **Einfache Tool-Verwaltung** - `/tools` Kommandos zum Steuern

---

## Schnellstart

### 1. Tools auflisten

```bash
python selfai/selfai.py
Du: /tools list
```

**Ausgabe:**
```
ℹ Verfügbare Tools (9):
  🔧 get_current_weather: Get the current weather in a given location.
  🔧 find_train_connections: Liefert Beispiel-Bahnverbindungen...
  🔧 add_calendar_event: Speichert einen neuen Kalendereintrag...
  🔧 list_calendar_events: Listet lokale Kalendereinträge...
  🔧 list_project_files: Listet Dateien innerhalb des Projekts...
  🔧 read_project_file: Liest den Beginn einer Textdatei...
  🔧 search_project_files: Durchsucht Projektdateien...
  🔧 write_project_file: Schreibt oder ergänzt eine Textdatei...
ℹ Tool-Support: ✅ Aktiviert
```

### 2. Tool verwenden (automatisch)

Der Agent entscheidet **automatisch**, wann Tools nützlich sind:

```bash
Du: Suche nach allen Python-Dateien im selfai Verzeichnis
```

**Was passiert:**
1. 🤖 Agent analysiert die Anfrage
2. 🔧 Wählt `list_project_files` Tool aus
3. ▶️ Führt Tool mit passenden Parametern aus
4. 💬 Präsentiert das Ergebnis in natürlicher Sprache

### 3. Tool-Support steuern

```bash
/tools off     # Deaktiviert Tool-Support
/tools on      # Aktiviert Tool-Support
/tools list    # Zeigt verfügbare Tools
```

---

## Verfügbare Tools

### 📁 Datei-Operationen

#### `list_project_files`
Listet Dateien innerhalb des Projekts.

**Parameter:**
- `subdir` (optional): Unterordner (z.B. `"selfai/core"`)
- `pattern` (optional): Glob-Muster (z.B. `"*.py"`)
- `max_results` (optional): Maximale Anzahl (Standard: 20)

**Beispiel:**
```
Du: Zeige mir alle Python-Dateien im selfai/core Verzeichnis
```

#### `read_project_file`
Liest den Inhalt einer Datei.

**Parameter:**
- `path` (required): Pfad zur Datei (z.B. `"selfai/core/agent.py"`)
- `max_chars` (optional): Maximale Zeichen (Standard: 4000)
- `strip` (optional): Whitespace entfernen (Standard: false)

**Beispiel:**
```
Du: Lies die Datei config.yaml.template
```

#### `write_project_file`
Schreibt Inhalt in eine Datei.

**Parameter:**
- `path` (required): Pfad zur Datei
- `content` (required): Zu schreibender Inhalt
- `mode` (optional): `"w"` (überschreiben) oder `"a"` (anhängen)

**Beispiel:**
```
Du: Erstelle eine Datei data/notes.txt mit dem Inhalt "Hallo Welt"
```

#### `search_project_files`
Durchsucht Dateien nach einem Begriff.

**Parameter:**
- `query` (required): Suchbegriff
- `pattern` (optional): Dateimuster (Standard: `"*.md"`)
- `max_results` (optional): Max. Ergebnisse (Standard: 20)

**Beispiel:**
```
Du: Suche nach "ToolCallingInterface" in allen Python-Dateien
```

### 📅 Kalender-Tools

#### `add_calendar_event`
Erstellt einen Kalendereintrag.

**Parameter:**
- `title` (required): Titel des Events
- `date` (required): Datum (YYYY-MM-DD oder DD.MM.YYYY)
- `start_time` (optional): Startzeit (HH:MM)
- `end_time` (optional): Endzeit (HH:MM)
- `location` (optional): Ort
- `notes` (optional): Zusätzliche Notizen

**Beispiel:**
```
Du: Erstelle einen Kalendereintrag für "Meeting mit Team" am 15.01.2025 um 14:00
```

#### `list_calendar_events`
Listet Kalendereinträge.

**Parameter:**
- `date` (optional): Bestimmtes Datum filtern
- `limit` (optional): Max. Anzahl
- `include_past` (optional): Vergangene Einträge einschließen (Standard: true)

**Beispiel:**
```
Du: Zeige mir meine Termine für nächste Woche
```

### 🚂 Reise-Tools

#### `find_train_connections`
Sucht Zugverbindungen (Demo-Daten).

**Parameter:**
- `origin` (required): Startbahnhof (z.B. `"Mainz Hbf"`)
- `destination` (required): Zielbahnhof (z.B. `"Worms Hbf"`)
- `date` (optional): Datum (YYYY-MM-DD)
- `max_results` (optional): Max. Verbindungen (Standard: 3)

**Beispiel:**
```
Du: Finde Zugverbindungen von Mainz nach Worms
```

### 🌤️ Wetter-Tools

#### `get_current_weather`
Gibt Wetter-Informationen zurück (Demo).

**Parameter:**
- `location` (required): Stadt (z.B. `"San Francisco, CA"`)
- `unit` (optional): `"celsius"` oder `"fahrenheit"`

**Beispiel:**
```
Du: Wie ist das Wetter in Tokyo?
```

---

## Technische Details

### Architektur

```
┌─────────────────────────────────────────────────────────┐
│                    Chat-Schleife                        │
│                   (selfai/selfai.py)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Tools aktiviert?      │
         └───────┬───────────────┘
                 │
       ┌─────────┴─────────┐
       │ JA                │ NEIN
       ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│ToolCallingIface  │  │ Direkte LLM-Gen. │
│                  │  │ (ohne Tools)     │
└─────┬────────────┘  └──────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│ 1. System Prompt mit Tool-Beschreibungen│
│ 2. LLM generiert Antwort                │
│ 3. Parse Tool-Call (JSON/Text/Action)   │
│ 4. Führe Tool aus                       │
│ 5. Schicke Ergebnis zurück an LLM      │
│ 6. LLM generiert finale Antwort        │
└─────────────────────────────────────────┘
```

### Tool-Calling-Formate

Das System unterstützt **3 verschiedene Formate**:

#### Format 1: JSON (OpenAI-Style)
```json
{
    "tool_name": "read_project_file",
    "arguments": {
        "path": "README.md",
        "max_chars": 1000
    }
}
```

#### Format 2: Function Call (Textbasiert)
```
read_project_file(path="README.md", max_chars=1000)
```

#### Format 3: Smolagents Action
```
Action: {"name": "read_project_file", "arguments": {"path": "README.md"}}
```

### Fallback-Strategie

```
ToolCallingInterface
        │
        ├─ Versuch 1: Mit Tools
        │      └─ Fehler? → Fallback
        │
        └─ Fallback: Direkte Generation (ohne Tools)
```

---

## Eigene Tools erstellen

### Schritt 1: Tool-Funktion schreiben

```python
# In selfai/tools/tool_registry.py

def my_custom_tool(param1: str, param2: int = 10) -> str:
    """
    Beschreibung deines Tools.

    Args:
        param1: Erster Parameter
        param2: Zweiter Parameter (optional)

    Returns:
        JSON string mit Ergebnis
    """
    import json

    # Deine Logik hier
    result = f"Verarbeitet: {param1} mit {param2}"

    return json.dumps({"status": "success", "result": result})
```

### Schritt 2: Tool registrieren

```python
# Am Ende von tool_registry.py

register_tool(
    RegisteredTool(
        name="my_custom_tool",
        func=my_custom_tool,
        schema={
            "name": "my_custom_tool",
            "description": "Macht etwas Nützliches mit den Parametern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Erster Parameter",
                    },
                    "param2": {
                        "type": "integer",
                        "description": "Zweiter Parameter (optional)",
                    },
                },
                "required": ["param1"],
            },
        },
        output_type="string",
    )
)
```

### Schritt 3: Testen

```bash
python selfai/selfai.py
Du: /tools list
# Dein Tool sollte jetzt in der Liste erscheinen!
```

---

## Best Practices

### 1. Tool-Design

✅ **DO:**
- Klare, beschreibende Namen (`read_project_file` statt `read`)
- Ausführliche Beschreibungen in der Schema-Definition
- JSON-Rückgabewerte für strukturierte Daten
- Fehlerbehandlung mit try/except
- Sicherheitschecks (z.B. Pfad-Validierung)

❌ **DON'T:**
- Vage Namen (`do_stuff`)
- Fehlende Fehlerbehandlung
- Unsichere Operationen ohne Validierung
- Zu komplexe Parameter-Strukturen

### 2. Parameter-Design

✅ **Gute Parameter:**
```python
{
    "path": "selfai/core/agent.py",  # Klar und spezifisch
    "max_results": 20                # Selbsterklärend
}
```

❌ **Schlechte Parameter:**
```python
{
    "p": "selfai/core/agent.py",    # Unklar
    "n": 20                          # Bedeutung unklar
}
```

### 3. Sicherheit

🔒 **Wichtige Sicherheitsmaßnahmen:**

1. **Pfad-Validierung:**
   ```python
   def _resolve_project_path(relative_path: str) -> Path:
       candidate = (PROJECT_ROOT / relative_path).resolve()
       if PROJECT_ROOT not in candidate.parents:
           raise ValueError("Pfad liegt außerhalb des Projekts!")
       return candidate
   ```

2. **Input-Sanitization:**
   ```python
   safe_input = user_input.strip()[:1000]  # Limit length
   ```

3. **Fehlerbehandlung:**
   ```python
   try:
       result = risky_operation()
   except Exception as exc:
       return json.dumps({"error": str(exc)})
   ```

---

## Fehlerbehebung

### Problem: "Tool not found"

**Lösung:** Prüfe, ob das Tool registriert ist:
```bash
/tools list
```

### Problem: "Tool execution failed"

**Mögliche Ursachen:**
1. Falsche Parameter
2. Fehlende Dateien/Daten
3. Berechtigungsprobleme

**Debug-Schritte:**
```python
# In tool_registry.py, füge Logging hinzu:
import logging
logger = logging.getLogger(__name__)

def my_tool(...):
    logger.debug(f"Tool called with: {locals()}")
    # ...
```

### Problem: "LLM verwendet Tools nicht"

**Lösungen:**
1. Prüfe, ob Tools aktiviert sind: `/tools list`
2. Verwende explizitere Anfragen: "Bitte verwende das list_project_files Tool"
3. Stelle sicher, dass der LLM-Backend Tool-Calling unterstützt

### Problem: "Tool-Calling Loop endlos"

**Ursache:** LLM generiert immer wieder Tool-Calls statt finaler Antwort

**Lösung:** `max_iterations` Parameter in `ToolCallingInterface` anpassen:
```python
tool_interface = ToolCallingInterface(
    llm_interface=interface,
    max_iterations=3,  # Reduziere Limit
    ui=ui,
)
```

---

## Performance-Tipps

### 1. Tool-Auswahl optimieren

Statt alle Tools zu laden:
```python
tool_interface = ToolCallingInterface(
    llm_interface=interface,
    tool_names=["read_project_file", "search_project_files"],  # Nur benötigte
    max_iterations=5,
)
```

### 2. Caching implementieren

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_tool_operation(param: str) -> str:
    # Teure Operation...
    return result
```

### 3. Async-Tools (Zukunft)

Für I/O-intensive Tools:
```python
import asyncio

async def async_tool(...):
    result = await fetch_from_api(...)
    return result
```

---

## Beispiel-Workflows

### Workflow 1: Codebase-Analyse

```bash
Du: Analysiere die Struktur des selfai/core Verzeichnisses
```

**Agent-Ablauf:**
1. `list_project_files(subdir="selfai/core", pattern="*.py")`
2. Für jede Datei: `read_project_file(path=...)`
3. Zusammenfassung generieren

### Workflow 2: Dokumentation erstellen

```bash
Du: Erstelle eine Zusammenfassung aller verfügbaren Tools und speichere sie in docs/tools_summary.md
```

**Agent-Ablauf:**
1. `/tools list` intern aufrufen
2. Tool-Schemas analysieren
3. `write_project_file(path="docs/tools_summary.md", content=...)`

### Workflow 3: Meeting vorbereiten

```bash
Du: Plane ein Meeting "Sprint Review" für morgen 10:00-11:00 und finde Zugverbindungen von Mainz nach Frankfurt
```

**Agent-Ablauf:**
1. `add_calendar_event(title="Sprint Review", date="2025-01-06", start_time="10:00", end_time="11:00")`
2. `find_train_connections(origin="Mainz Hbf", destination="Frankfurt Hbf")`
3. Zusammenfassung mit beiden Ergebnissen

---

## Integration mit Planner

Tools funktionieren auch in **geplanten Subtasks**:

```yaml
# Beispiel-Plan
subtasks:
  - id: S1
    title: "Code analysieren"
    objective: "Finde alle Python-Dateien und analysiere sie"
    agent_key: "code_helfer"
    engine: "smolagent"  # Wichtig: smolagent für Tool-Support!
    tools:
      - list_project_files
      - read_project_file
      - search_project_files
```

**Aktivierung:**
```bash
Du: /plan Analysiere die Projektstruktur und erstelle einen Bericht
```

---

## Erweiterte Konfiguration

### In `config.yaml` (Optional):

```yaml
# Zukünftige Erweiterung
tools:
  enabled: true
  default_tools:
    - read_project_file
    - write_project_file
    - list_project_files

  max_iterations: 5

  # Tool-spezifische Timeouts
  timeouts:
    default: 30.0
    list_project_files: 10.0
    search_project_files: 60.0
```

---

## Referenz: Alle Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `/tools list` | Zeige alle verfügbaren Tools |
| `/tools on` | Aktiviere Tool-Support |
| `/tools off` | Deaktiviere Tool-Support |
| `/memory` | Zeige Memory-Kategorien |
| `/memory clear <cat>` | Lösche Memory-Kategorie |
| `/switch <agent>` | Wechsle den Agenten |
| `/plan <goal>` | Erstelle und führe Plan aus |
| `/planner list` | Zeige Planner-Provider |
| `quit` | Beende SelfAI |

---

## Roadmap

### Geplante Features:

- [ ] **Tool-Kategorien** - Gruppierung verwandter Tools
- [ ] **Tool-Berechtigungen** - Sicherheits-Policies
- [ ] **Async Tool-Execution** - Parallele Tool-Aufrufe
- [ ] **Tool-Feedback** - Streaming-Updates während Ausführung
- [ ] **Custom Tool-Plugins** - Externe Tool-Pakete laden
- [ ] **Tool-Analytics** - Nutzungsstatistiken
- [ ] **Tool-Marketplace** - Community-Tools teilen

---

## Support & Feedback

**Probleme melden:**
- GitHub Issues: [github.com/your-repo/issues](https://github.com/your-repo/issues)

**Beispiele:**
- Siehe `examples/tool_examples.md` (coming soon)

**Weitere Dokumentation:**
- [CLAUDE.md](CLAUDE.md) - Vollständige Architektur
- [README.md](README.md) - Schnellstart
- [UI_GUIDE.md](UI_GUIDE.md) - Terminal-UI

---

**Version:** 1.0.0
**Last Updated:** Januar 2025
**Status:** ✅ Production-Ready
