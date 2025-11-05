# Git Update Anleitung - Tool-System holen

## Option 1: Branch wechseln und pullen (Empfohlen)

```bash
cd /pfad/zu/SelfAi-NPU-AGENT

# 1. Aktuellen Status prüfen
git status

# 2. Änderungen vom Remote holen
git fetch origin

# 3. Auf den Tool-Branch wechseln
git checkout claude/review-pr-011CUppJy9F4ANpfjsCACmys

# 4. Neueste Änderungen pullen
git pull origin claude/review-pr-011CUppJy9F4ANpfjsCACmys

# 5. Prüfen ob alles da ist
ls -la selfai/core/tool_calling_interface.py
# Sollte die Datei anzeigen!
```

## Option 2: Nur die neuesten Änderungen pullen

Wenn du bereits auf dem Branch bist:

```bash
git pull origin claude/review-pr-011CUppJy9F4ANpfjsCACmys
```

## Prüfen ob es funktioniert hat

```bash
# 1. Neue Dateien sollten existieren
ls selfai/core/tool_calling_interface.py
ls TOOLS_GUIDE.md
ls agents/code_helfer/config.yaml

# 2. Python-Import testen
python -c "from selfai.core.tool_calling_interface import ToolCallingInterface; print('✅ Tool-System verfügbar!')"
```

## Was wird heruntergeladen?

### Neue Dateien:
- `selfai/core/tool_calling_interface.py` - Haupt-Tool-System
- `TOOLS_GUIDE.md` - Vollständige Dokumentation
- `CHANGELOG_TOOLS.md` - Änderungsprotokoll
- `agents/code_helfer/config.yaml` - Beispiel-Agent
- `agents/code_helfer/system_prompt.md`
- `agents/projektmanager/config.yaml` - Beispiel-Agent
- `agents/projektmanager/system_prompt.md`

### Geänderte Dateien:
- `selfai/selfai.py` - Tool-Integration in Chat
- `selfai/tools/tool_registry.py` - Neues write_project_file Tool
- `selfai/core/agent_manager.py` - Agent-spezifische Tools

## Fehlersuche

**Problem:** "Branch nicht gefunden"
```bash
git fetch origin
git branch -a  # Zeigt alle Branches
```

**Problem:** "Merge-Konflikt"
```bash
# Lokale Änderungen stashen
git stash
git pull
git stash pop
```

**Problem:** "Datei nicht gefunden nach Pull"
```bash
# Cache refreshen
git status
ls -R agents/
```
