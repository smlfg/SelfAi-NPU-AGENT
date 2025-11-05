# Anti-Halluzinations-Mechanismus - Implementierungsanleitung

## Problem

Der DPPM-Planner **erfindet Tools**, die nicht existieren, und Agenten **halluzinieren Tool-Outputs**.

**Beispiel-Problem:**
```json
{
  "subtasks": [
    {
      "id": "S1",
      "engine": "smolagent",
      "tools": ["search_web", "analyze_sentiment", "magic_tool"]
      // ❌ Diese Tools existieren nicht!
    }
  ]
}
```

Dann halluziniert der Agent:
```
Tool 'search_web' returned: "Ich habe das Web durchsucht..."
// ❌ Tool wurde nie ausgeführt, Agent erfindet Output!
```

---

## Lösung: 4-Stufen-Validierung

### ✅ Stufe 1: Planner-Prompt Verbesserung (ERLEDIGT)

**Datei:** `selfai/core/planner_ollama_interface.py` Zeile 134

**Bereits implementiert:**
```
- Für Subtasks mit "engine": "smolagent" nutze ausschließlich folgende Tool-Namen (keine anderen erfinden):
{tool_name_list}
```

**Verbesserung nötig:**
```python
# In _build_prompt() Methode, Zeile 134 ersetzen:

template = textwrap.dedent(
    """
    ...
    ⚠️  KRITISCHE REGEL - TOOL-HALLUZINATION VERHINDERN:
    - Verwende NUR Tools aus der folgenden WHITELIST
    - ERFINDE KEINE Tools, die nicht aufgelistet sind
    - Bei unbekannten Tools wird der Plan ABGELEHNT
    - Wenn ein Tool fehlt, nutze "notes" um das Problem zu beschreiben

    WHITELIST - Erlaubte Tools:
{tool_whitelist}

    ❌ VERBOTEN: Erfundene Tools wie "search_web", "magic_tool", etc.
    ✅ ERLAUBT: Nur Tools aus der Whitelist oben

    ...
    """
)

# Und dann:
tool_whitelist = generate_tool_whitelist_prompt()  # Aus tool_validator.py
```

---

### ✅ Stufe 2: Plan-Validierung nach Generierung (NEU)

**Datei:** `selfai/core/planner_ollama_interface.py`

**In der `plan()` Methode, NACH dem JSON-Parsing:**

```python
# Zeile ~240, nach validate_plan_structure(plan_data)

# NEUE TOOL-VALIDIERUNG:
from selfai.core.tool_validator import validate_plan_tools, sanitize_plan_tools

# 1. Prüfe Tools
is_valid, tool_errors = validate_plan_tools(plan_data)

if not is_valid:
    # Tools sind ungültig!
    error_msg = "Plan enthält ungültige Tools:\n" + "\n".join(tool_errors)

    # Option A: Strikt - Plan ablehnen
    raise PlanValidationError(error_msg, plan_data=plan_data)

    # Option B: Tolerant - Ungültige Tools entfernen
    # sanitized_plan, removed = sanitize_plan_tools(plan_data)
    # if progress_callback:
    #     progress_callback(f"\n⚠️  Entfernte ungültige Tools: {', '.join(removed)}\n")
    # plan_data = sanitized_plan
```

---

### ✅ Stufe 3: Runtime-Validierung im Execution Dispatcher (NEU)

**Datei:** `selfai/core/execution_dispatcher.py`

**In der `_run_smolagent()` Methode, Zeile ~173:**

```python
def _run_smolagent(self, task, agent, prompt_text, history, task_id):
    from selfai.core.smolagents_runner import SmolAgentError, SmolAgentRunner
    from selfai.core.tool_validator import validate_tool_name  # NEU!

    # Hole Tools
    tool_names = []
    raw_tools = task.get("tools")
    if isinstance(raw_tools, list):
        for name in raw_tools:
            if not isinstance(name, str) or not name.strip():
                continue

            # NEU: Validiere jedes Tool
            is_valid, error = validate_tool_name(name)
            if not is_valid:
                self.ui.status(f"⚠️  {error}", "warning")
                # Tool überspringen oder Fehler werfen
                continue  # Tolerant: überspringen
                # raise ExecutionError(error)  # Strikt: abbrechen

            tool_names.append(name)

    # Rest wie gehabt...
```

---

### ✅ Stufe 4: Tool-Call-Validierung im ToolCallingInterface (NEU)

**Datei:** `selfai/core/tool_calling_interface.py`

**In der `_execute_tool()` Methode, Zeile ~169:**

```python
def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool with given arguments."""
    from selfai.core.tool_validator import validate_tool_call_runtime  # NEU!

    # NEU: Runtime-Validierung
    is_valid, error = validate_tool_call_runtime(tool_name, arguments)
    if not is_valid:
        error_msg = f"❌ Tool-Call ungültig: {error}"
        if self.ui:
            self.ui.status(error_msg, "error")
        return error_msg

    # Original Code
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
```

---

## Implementierungs-Checkliste

### ✅ Bereits erledigt:
- [x] `tool_validator.py` Modul erstellt
- [x] Validierungsfunktionen implementiert:
  - `validate_tool_name()` - Einzelne Tool-Namen prüfen
  - `validate_plan_tools()` - Alle Tools in einem Plan prüfen
  - `sanitize_plan_tools()` - Ungültige Tools entfernen
  - `generate_tool_whitelist_prompt()` - Whitelist-Prompt generieren
  - `validate_tool_call_runtime()` - Runtime-Validierung

### 🔄 Noch zu tun:
- [ ] `planner_ollama_interface.py` updaten:
  - [ ] Import von `tool_validator` hinzufügen
  - [ ] Prompt mit Whitelist erweitern
  - [ ] Plan-Validierung nach Generierung

- [ ] `execution_dispatcher.py` updaten:
  - [ ] Tool-Validierung in `_run_smolagent()` einbauen

- [ ] `tool_calling_interface.py` updaten:
  - [ ] Runtime-Validierung in `_execute_tool()` einbauen

---

## Manuelle Code-Updates

Da die Dateien zu groß für automatische Edits sind, hier die **manuellen Änderungen**:

### 1. planner_ollama_interface.py

**Import hinzufügen (Zeile ~12):**
```python
from selfai.core.tool_validator import validate_plan_tools, generate_tool_whitelist_prompt
```

**Prompt erweitern (Zeile ~147, VOR "Ziel:"):**
```python
{tool_whitelist_warning}

Ziel:
{goal}
```

**Format-Parameter erweitern (Zeile ~152):**
```python
return template.format(
    agent_overview=agents_text,
    memory_summary=context.memory_summary or "(kein Memory verfügbar)",
    tools_overview=tools_overview,
    goal=goal.strip(),
    tool_name_list=allowed_tool_names,
    tool_whitelist_warning=generate_tool_whitelist_prompt(),  # NEU!
)
```

**Plan-Validierung einbauen (Zeile ~240, nach validate_plan_structure):**
```python
# Nach: validate_plan_structure(plan_data, ...

# NEU: Tool-Validierung
is_valid, tool_errors = validate_plan_tools(plan_data)
if not is_valid:
    error_msg = "Plan enthält ungültige Tools:\n" + "\n".join(tool_errors)
    raise PlanValidationError(error_msg, plan_data=plan_data)
```

---

### 2. execution_dispatcher.py

**Import hinzufügen (Zeile ~9):**
```python
from selfai.core.tool_validator import validate_tool_name
```

**Tool-Validierung in _run_smolagent (Zeile ~176):**
```python
for name in raw_tools:
    if not isinstance(name, str) or not name.strip():
        continue

    # NEU: Validiere Tool
    is_valid, error = validate_tool_name(name)
    if not is_valid:
        self.ui.status(f"⚠️  Subtask {task_id}: {error}", "warning")
        continue  # Überspringe ungültiges Tool

    tool_names.append(name)
```

---

### 3. tool_calling_interface.py

**Import hinzufügen (Zeile ~10):**
```python
from selfai.core.tool_validator import validate_tool_call_runtime
```

**Runtime-Validierung in _execute_tool (Zeile ~169):**
```python
def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool with given arguments."""
    # NEU: Runtime-Validierung
    from selfai.core.tool_validator import validate_tool_call_runtime

    is_valid, error = validate_tool_call_runtime(tool_name, arguments)
    if not is_valid:
        error_msg = f"❌ Tool-Call ungültig: {error}"
        if self.ui:
            self.ui.status(error_msg, "error")
        return error_msg

    # Rest bleibt gleich...
```

---

## Testen

**Nach der Implementierung:**

```python
# Test 1: Planner mit ungültigem Tool
python -c "
from selfai.core.planner_ollama_interface import PlannerOllamaInterface
from selfai.core.tool_validator import validate_plan_tools

plan = {
    'subtasks': [{
        'id': 'S1',
        'engine': 'smolagent',
        'tools': ['fake_tool', 'read_project_file']  # fake_tool existiert nicht!
    }]
}

is_valid, errors = validate_plan_tools(plan)
print(f'Valid: {is_valid}')
print(f'Errors: {errors}')
"

# Erwartete Ausgabe:
# Valid: False
# Errors: ["Subtask S1: Tool 'fake_tool' existiert nicht..."]
```

---

## Zusammenfassung

### Vor der Implementierung:
```
❌ Planner erfindet Tools
❌ Keine Validierung
❌ Agent halluziniert Outputs
❌ Ausführung schlägt fehl
```

### Nach der Implementierung:
```
✅ Planner erhält Whitelist
✅ Plan wird validiert (Stufe 2)
✅ Tools werden vor Ausführung geprüft (Stufe 3)
✅ Runtime-Validierung verhindert falsche Calls (Stufe 4)
✅ Klare Fehlermeldungen
✅ Keine Halluzination möglich!
```

---

## Nächste Schritte

1. Die manuellen Code-Updates durchführen (siehe oben)
2. Testen mit einem Plan der ungültige Tools enthält
3. Dokumentation in TOOLS_GUIDE.md ergänzen

**Status:** 🟡 Validierungsmodul erstellt, Integration in Code noch nötig
