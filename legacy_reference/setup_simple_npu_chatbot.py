#!/usr/bin/env python3
"""
Automatisches Setup für das simple-npu-chatbot-Referenzprojekt.

Erstellt (falls nötig) eine virtuelle Umgebung in simples-npu-chatbot/llm-venv
und installiert alle benötigten Abhängigkeiten aus requirements.txt.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 10)


def check_python_version() -> None:
    """Stellt sicher, dass die laufende Python-Version unterstützt wird."""
    if sys.version_info < MIN_PYTHON:
        version = ".".join(map(str, sys.version_info[:3]))
        expected = ".".join(map(str, MIN_PYTHON))
        raise SystemExit(
            f"Python {expected} oder höher wird benötigt, gefunden: {version}."
        )


def run_cmd(command: list[str], *, cwd: Path | None = None) -> None:
    """Führt einen Shell-Befehl aus und gibt die Ausgabe direkt aus."""
    pretty_cmd = " ".join(command)
    location = f" (cwd: {cwd})" if cwd else ""
    print(f"\n>>> {pretty_cmd}{location}")
    subprocess.run(command, check=True, cwd=cwd)


def resolve_project_paths(requirements_filename: str) -> tuple[Path, Path, Path]:
    """Ermittelt Hauptpfade für das Setup."""
    root = Path(__file__).resolve().parent
    chatbot_dir = root / "simple-npu-chatbot"
    if not chatbot_dir.is_dir():
        raise SystemExit(
            f"Verzeichnis '{chatbot_dir}' nicht gefunden. "
            "Bitte stelle sicher, dass simple-npu-chatbot/ vorhanden ist."
        )

    venv_path = chatbot_dir / "llm-venv"
    requirements = chatbot_dir / requirements_filename
    if not requirements.is_file():
        raise SystemExit(f"Requirements-Datei nicht gefunden: {requirements}")

    return chatbot_dir, venv_path, requirements


def get_venv_python(venv_path: Path) -> Path:
    """Gibt den Pfad zum Python-Interpreter in der virtuellen Umgebung zurück."""
    if os.name == "nt":
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        python_path = venv_path / "bin" / "python"
    return python_path


def create_virtualenv(venv_path: Path, *, recreate: bool) -> None:
    """Erstellt die virtuelle Umgebung (optional neu)."""
    if venv_path.exists():
        if recreate:
            print(f"Entferne bestehende virtuelle Umgebung unter {venv_path} ...")
            shutil.rmtree(venv_path)
        else:
            print(f"Virtuelle Umgebung existiert bereits unter {venv_path}")
            return

    print(f"Erstelle virtuelle Umgebung unter {venv_path} ...")
    run_cmd([sys.executable, "-m", "venv", str(venv_path)])


def install_requirements(venv_python: Path, requirements: Path) -> None:
    """Installiert Pakete in der virtuellen Umgebung."""
    if not venv_python.is_file():
        raise SystemExit(f"Python in virtueller Umgebung nicht gefunden: {venv_python}")

    run_cmd([str(venv_python), "-m", "pip", "--version"])
    run_cmd([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run_cmd(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "wheel",
            "setuptools",
        ]
    )
    run_cmd([str(venv_python), "-m", "pip", "install", "-r", str(requirements)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Setzt das simple-npu-chatbot-Projekt auf "
            "(virtuelle Umgebung + requirements)."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--requirements-file",
        default="requirements-minimal.txt",
        help=(
            "Alternative Requirements-Datei (relativ zu simple-npu-chatbot/). "
            "Standard: requirements-minimal.txt"
        ),
    )
    group.add_argument(
        "--full",
        action="store_true",
        help="Komplette requirements.txt installieren (inklusive Gradio & Datenpakete).",
    )
    parser.add_argument(
        "--recreate-venv",
        action="store_true",
        help="Bestehende virtuelle Umgebung löschen und neu anlegen.",
    )
    return parser.parse_args()


def main() -> None:
    check_python_version()
    args = parse_args()
    requirements_filename = "requirements.txt" if args.full else args.requirements_file
    chatbot_dir, venv_path, requirements = resolve_project_paths(requirements_filename)

    create_virtualenv(venv_path, recreate=args.recreate_venv)
    venv_python = get_venv_python(venv_path)
    install_requirements(venv_python, requirements)

    activation_hint = (
        f"source {venv_path}/bin/activate"
        if os.name != "nt"
        else f"{venv_path}\\Scripts\\Activate.ps1"
    )
    print("\nSetup abgeschlossen.")
    print(f"Verwendete Requirements: {requirements.name}")
    print(f"Aktivieren der Umgebung:\n  {activation_hint}")
    print(
        "\nBeispielbefehle:\n"
        f"  python {chatbot_dir/'src'/'auth.py'}\n"
        f"  python {chatbot_dir/'src'/'terminal_chatbot.py'}"
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"\n❌ Befehl fehlgeschlagen: {exc}") from exc
