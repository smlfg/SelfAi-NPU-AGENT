"""Extended tool collection for SelfAI agents."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

# Import project root from tool_registry
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from selfai.tools.tool_registry import PROJECT_ROOT, _resolve_project_path, register_tool, RegisteredTool


# =============================================================================
# SYSTEM INFORMATION TOOLS
# =============================================================================

def get_system_info() -> str:
    """
    Liefert System-Informationen (CPU, RAM, Python-Version, Disk).

    Returns:
        JSON string mit System-Informationen.
    """
    import platform
    import sys as system_module
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage(str(PROJECT_ROOT))

        return json.dumps({
            "platform": platform.system(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": system_module.version.split()[0],
            "cpu_cores": cpu_count,
            "cpu_usage_percent": cpu_percent,
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "memory_available_gb": round(mem.available / (1024**3), 2),
            "memory_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_percent": disk.percent,
        })
    except ImportError:
        return json.dumps({
            "platform": platform.system(),
            "python_version": system_module.version.split()[0],
            "error": "psutil nicht installiert für erweiterte Infos"
        })
    except Exception as exc:
        return json.dumps({"error": f"Fehler beim Abrufen der System-Infos: {exc}"})


def get_disk_usage(path: str = ".") -> str:
    """
    Liefert Disk-Usage für einen Pfad.

    Args:
        path: Pfad zum Prüfen (Standard: Projektroot)

    Returns:
        JSON string mit Disk-Informationen.
    """
    try:
        target = _resolve_project_path(path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        import psutil
        usage = psutil.disk_usage(str(target))
        return json.dumps({
            "path": str(target.relative_to(PROJECT_ROOT)),
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": usage.percent,
        })
    except ImportError:
        return json.dumps({"error": "psutil nicht installiert"})
    except Exception as exc:
        return json.dumps({"error": f"Disk-Usage Fehler: {exc}"})


def get_python_packages() -> str:
    """
    Listet installierte Python-Pakete.

    Returns:
        JSON string mit Paket-Liste.
    """
    try:
        result = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        packages = json.loads(result.stdout)
        return json.dumps({
            "packages": packages[:50],  # Limit to 50 for performance
            "total_count": len(packages),
            "truncated": len(packages) > 50,
        })
    except Exception as exc:
        return json.dumps({"error": f"Fehler beim Abrufen der Pakete: {exc}"})


# =============================================================================
# GIT TOOLS
# =============================================================================

def git_status(repo_path: str = ".") -> str:
    """
    Führt 'git status' aus und liefert den Output.

    Args:
        repo_path: Pfad zum Git-Repository (Standard: Projektroot)

    Returns:
        JSON string mit Git-Status.
    """
    try:
        target = _resolve_project_path(repo_path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return json.dumps({
            "status": "success",
            "output": result.stdout,
            "has_changes": bool(result.stdout.strip()),
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Git-Befehl timeout"})
    except FileNotFoundError:
        return json.dumps({"error": "Git nicht gefunden (nicht installiert?)"})
    except Exception as exc:
        return json.dumps({"error": f"Git-Status Fehler: {exc}"})


def git_log(repo_path: str = ".", limit: int = 10) -> str:
    """
    Zeigt Git-Commit-Historie.

    Args:
        repo_path: Pfad zum Repository
        limit: Anzahl der Commits (Standard: 10)

    Returns:
        JSON string mit Commit-Historie.
    """
    try:
        target = _resolve_project_path(repo_path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    limit_int = max(1, min(int(limit), 100))  # 1-100 Commits

    try:
        result = subprocess.run(
            ["git", "log", f"-{limit_int}", "--pretty=format:%h|%an|%ar|%s"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    })

        return json.dumps({"commits": commits, "count": len(commits)})
    except Exception as exc:
        return json.dumps({"error": f"Git-Log Fehler: {exc}"})


def git_branch_list(repo_path: str = ".") -> str:
    """
    Listet alle Git-Branches.

    Args:
        repo_path: Pfad zum Repository

    Returns:
        JSON string mit Branch-Liste.
    """
    try:
        target = _resolve_project_path(repo_path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )

        branches = []
        current_branch = None

        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("* "):
                current_branch = line[2:]
                branches.append({"name": current_branch, "current": True})
            elif line:
                branches.append({"name": line, "current": False})

        return json.dumps({
            "branches": branches,
            "current_branch": current_branch,
            "count": len(branches),
        })
    except Exception as exc:
        return json.dumps({"error": f"Git-Branch Fehler: {exc}"})


def git_diff(repo_path: str = ".", file_path: str | None = None) -> str:
    """
    Zeigt Git-Diff (Änderungen).

    Args:
        repo_path: Pfad zum Repository
        file_path: Optionaler spezifischer Dateipfad

    Returns:
        JSON string mit Diff-Output.
    """
    try:
        target = _resolve_project_path(repo_path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    cmd = ["git", "diff"]
    if file_path:
        cmd.append(file_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=target,
            capture_output=True,
            text=True,
            timeout=15,
        )

        return json.dumps({
            "diff": result.stdout[:5000],  # Limit to 5000 chars
            "has_changes": bool(result.stdout.strip()),
            "truncated": len(result.stdout) > 5000,
        })
    except Exception as exc:
        return json.dumps({"error": f"Git-Diff Fehler: {exc}"})


# =============================================================================
# DATA PROCESSING TOOLS
# =============================================================================

def parse_json_file(path: str) -> str:
    """
    Parsed eine JSON-Datei und validiert sie.

    Args:
        path: Pfad zur JSON-Datei

    Returns:
        JSON string mit geparsten Daten oder Fehler.
    """
    try:
        file_path = _resolve_project_path(path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    if not file_path.is_file():
        return json.dumps({"error": "Datei nicht gefunden"})

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
        return json.dumps({
            "status": "success",
            "data": data,
            "type": type(data).__name__,
            "size_bytes": len(content),
        })
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Ungültiges JSON: {exc}"})
    except Exception as exc:
        return json.dumps({"error": f"Fehler beim Parsen: {exc}"})


def count_lines_of_code(path: str = ".", pattern: str = "*.py") -> str:
    """
    Zählt Codezeilen in Dateien.

    Args:
        path: Pfad zum Scannen
        pattern: Dateimuster (Standard: *.py)

    Returns:
        JSON string mit Statistiken.
    """
    try:
        base_dir = _resolve_project_path(path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    total_files = 0
    total_lines = 0
    total_blank = 0
    total_comments = 0

    for file_path in base_dir.rglob(pattern):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            total_files += 1
            total_lines += len(lines)

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    total_blank += 1
                elif stripped.startswith("#"):
                    total_comments += 1
        except (OSError, UnicodeDecodeError):
            continue

    total_code = total_lines - total_blank - total_comments

    return json.dumps({
        "total_files": total_files,
        "total_lines": total_lines,
        "code_lines": total_code,
        "blank_lines": total_blank,
        "comment_lines": total_comments,
        "pattern": pattern,
    })


def analyze_directory_structure(path: str = ".", max_depth: int = 3) -> str:
    """
    Analysiert Verzeichnis-Struktur.

    Args:
        path: Pfad zum Analysieren
        max_depth: Maximale Tiefe (Standard: 3)

    Returns:
        JSON string mit Verzeichnis-Struktur.
    """
    try:
        base_dir = _resolve_project_path(path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    def scan_dir(dir_path: Path, current_depth: int) -> dict[str, Any]:
        if current_depth > max_depth:
            return {"truncated": True}

        result: dict[str, Any] = {"dirs": [], "files": [], "file_count": 0, "dir_count": 0}

        try:
            for item in sorted(dir_path.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    result["dirs"].append({
                        "name": item.name,
                        "children": scan_dir(item, current_depth + 1),
                    })
                    result["dir_count"] += 1
                elif item.is_file():
                    result["files"].append(item.name)
                    result["file_count"] += 1
        except PermissionError:
            result["error"] = "Permission denied"

        return result

    structure = scan_dir(base_dir, 0)
    return json.dumps(structure)


# =============================================================================
# UTILITY TOOLS
# =============================================================================

def create_report(title: str, content: str, output_path: str = "reports/report.md") -> str:
    """
    Erstellt einen formatierten Bericht.

    Args:
        title: Titel des Berichts
        content: Inhalt des Berichts
        output_path: Ausgabepfad (Standard: reports/report.md)

    Returns:
        JSON string mit Status.
    """
    try:
        file_path = _resolve_project_path(output_path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# {title}

**Erstellt:** {timestamp}

---

{content}

---

*Generiert von SelfAI*
"""

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(report, encoding="utf-8")

        return json.dumps({
            "status": "success",
            "path": str(file_path.relative_to(PROJECT_ROOT)),
            "size_bytes": len(report),
        })
    except Exception as exc:
        return json.dumps({"error": f"Fehler beim Erstellen des Berichts: {exc}"})


def validate_yaml_file(path: str) -> str:
    """
    Validiert eine YAML-Datei.

    Args:
        path: Pfad zur YAML-Datei

    Returns:
        JSON string mit Validierungsergebnis.
    """
    try:
        file_path = _resolve_project_path(path)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    if not file_path.is_file():
        return json.dumps({"error": "Datei nicht gefunden"})

    try:
        import yaml
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        return json.dumps({
            "status": "valid",
            "type": type(data).__name__,
            "size_bytes": len(content),
            "keys": list(data.keys()) if isinstance(data, dict) else None,
        })
    except yaml.YAMLError as exc:
        return json.dumps({"status": "invalid", "error": f"YAML-Fehler: {exc}"})
    except Exception as exc:
        return json.dumps({"error": f"Fehler beim Validieren: {exc}"})


# =============================================================================
# TOOL REGISTRATION
# =============================================================================

# System Tools
register_tool(RegisteredTool(
    name="get_system_info",
    func=get_system_info,
    schema={
        "name": "get_system_info",
        "description": "Liefert umfassende System-Informationen (CPU, RAM, Disk, Python-Version).",
        "parameters": {"type": "object", "properties": {}},
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="get_disk_usage",
    func=get_disk_usage,
    schema={
        "name": "get_disk_usage",
        "description": "Prüft Disk-Usage für einen Pfad (Total, Used, Free, Percent).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pfad relativ zum Projektroot (Standard: '.')."}
            },
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="get_python_packages",
    func=get_python_packages,
    schema={
        "name": "get_python_packages",
        "description": "Listet installierte Python-Pakete mit Namen und Versionen.",
        "parameters": {"type": "object", "properties": {}},
    },
    output_type="string",
))

# Git Tools
register_tool(RegisteredTool(
    name="git_status",
    func=git_status,
    schema={
        "name": "git_status",
        "description": "Führt 'git status' aus und zeigt den aktuellen Repository-Status.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Pfad zum Repository (Standard: Projektroot)."}
            },
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="git_log",
    func=git_log,
    schema={
        "name": "git_log",
        "description": "Zeigt Git-Commit-Historie mit Hash, Author, Date, Message.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Pfad zum Repository (Standard: Projektroot)."},
                "limit": {"type": "integer", "description": "Anzahl der Commits (1-100, Standard: 10)."},
            },
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="git_branch_list",
    func=git_branch_list,
    schema={
        "name": "git_branch_list",
        "description": "Listet alle Git-Branches und markiert den aktuellen Branch.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Pfad zum Repository (Standard: Projektroot)."}
            },
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="git_diff",
    func=git_diff,
    schema={
        "name": "git_diff",
        "description": "Zeigt Git-Diff (Änderungen) für das Repository oder eine spezifische Datei.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Pfad zum Repository (Standard: Projektroot)."},
                "file_path": {"type": "string", "description": "Optionaler spezifischer Dateipfad."},
            },
        },
    },
    output_type="string",
))

# Data Processing Tools
register_tool(RegisteredTool(
    name="parse_json_file",
    func=parse_json_file,
    schema={
        "name": "parse_json_file",
        "description": "Parsed und validiert eine JSON-Datei, liefert die Daten strukturiert zurück.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pfad zur JSON-Datei relativ zum Projektroot."}
            },
            "required": ["path"],
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="count_lines_of_code",
    func=count_lines_of_code,
    schema={
        "name": "count_lines_of_code",
        "description": "Zählt Codezeilen in Dateien (Total, Code, Blank, Comments).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pfad zum Scannen (Standard: Projektroot)."},
                "pattern": {"type": "string", "description": "Dateimuster (Standard: '*.py')."},
            },
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="analyze_directory_structure",
    func=analyze_directory_structure,
    schema={
        "name": "analyze_directory_structure",
        "description": "Analysiert Verzeichnis-Struktur mit Dateien und Unterverzeichnissen.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pfad zum Analysieren (Standard: Projektroot)."},
                "max_depth": {"type": "integer", "description": "Maximale Tiefe (Standard: 3)."},
            },
        },
    },
    output_type="string",
))

# Utility Tools
register_tool(RegisteredTool(
    name="create_report",
    func=create_report,
    schema={
        "name": "create_report",
        "description": "Erstellt einen formatierten Bericht als Markdown-Datei.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titel des Berichts."},
                "content": {"type": "string", "description": "Inhalt des Berichts."},
                "output_path": {"type": "string", "description": "Ausgabepfad (Standard: reports/report.md)."},
            },
            "required": ["title", "content"],
        },
    },
    output_type="string",
))

register_tool(RegisteredTool(
    name="validate_yaml_file",
    func=validate_yaml_file,
    schema={
        "name": "validate_yaml_file",
        "description": "Validiert eine YAML-Datei auf Syntax-Fehler.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pfad zur YAML-Datei relativ zum Projektroot."}
            },
            "required": ["path"],
        },
    },
    output_type="string",
))
