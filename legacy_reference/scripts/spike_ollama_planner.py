"""Spike-Skript: Validiert, dass der Ollama-Planner ein parsebares JSON liefert."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

import httpx

# Ensure project root available for imports when executed from subdirectory
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config_loader import load_configuration


def _build_prompt(goal: str) -> str:
    """Erzeuge das minimale Planner-Prompt-Template für den Spike."""

    template = textwrap.dedent(
        """
        Du agierst als DPPM-Planer (Decompose–Parallel Plan–Merge) für SelfAI und erzeugst ausschließlich JSON in folgendem Schema:
        {{
          "subtasks": [
            {{
              "id": "S1",
              "title": "kurzer Titel",
              "objective": "prägnante Zielbeschreibung (max. 160 Zeichen)",
              "agent_key": "code_helfer",
              "engine": "anythingllm",
              "parallel_group": 1,
              "depends_on": [],
              "notes": "optionale Hinweise (max. 160 Zeichen)"
            }}
          ],
          "merge": {{
            "strategy": "Kurze Beschreibung der Zusammenführung (max. 160 Zeichen)",
            "steps": [
              {{
                "title": "Schritt",
                "description": "konkrete Merge-Aktion (max. 160 Zeichen)",
                "depends_on": ["S1", "S2"]
              }}
            ]
          }}
        }}

        DPPM-Vorgaben:
        1. Decompose – zerlege die Aufgabe in maximal fünf unabhängige Subtasks.
        2. Parallel Plan – weise parallele Arbeiten über "parallel_group" zu und nutze "depends_on" nur für echte Abhängigkeiten.
        3. Merge – definiere eine konsistente Zusammenführung des globalen Plans.

        Regeln:
        - Gib ausschließlich reines JSON zurück, ohne Markdown, Backticks oder Text vor/nach dem JSON.
        - Jeder String muss eine Zeile bleiben und <= 160 Zeichen haben.
        - Verwende als "agent_key" nur: "code_helfer", "research_assistant", "doc_scout".
        - Verwende als "engine" nur: "anythingllm", "qnn", "cpu", "smolagent".
        - Trage mindestens zwei Subtasks ein, wenn möglich; maximal fünf.
        - Liefere die finale JSON ausschließlich in der Antwort-Ausgabe (nicht im Thinking-Bereich).
        - Analysiere die Anforderung präzise. Wenn explizite Detailanweisungen (z. B. "letter for letter", "Schritt für Schritt", "einzeln") vorkommen, bilde Subtasks, die diese Vorgaben exakt widerspiegeln.
        - Jeder Subtask muss einen eigenen Mehrwert liefern; vermeide redundante oder identische Ziele.
        - Die Merge-Strategie muss beschreiben, wie die Ergebnisse zusammengeführt werden (nicht nur "kombiniere alle Outputs").
        - Beende die Ausgabe direkt nach dem JSON mit der Zeichenkette END_OF_PLAN.
        - Wenn die Anforderung mehrdeutig ist, erstelle zuerst einen Klärungs-Subtask (z. B. "Anforderung klären") und dokumentiere offene Fragen oder Annahmen.
        - Stelle sicher, dass Subtasks, die auf vorangehenden Ergebnissen basieren, die entsprechenden IDs in "depends_on" aufführen.

        Ziel:
        {goal}

        Kontext:
        - SelfAI-Agenten: code_helfer (Coding), research_assistant (Recherche), doc_scout (Dokumentation).
        - Execution-Backends: anythingllm (Snapdragon NPU), qnn (lokale QNN), cpu (lokale GGUF), smolagent (Tool-Aufrufe).
        - Fokus: Ollama als vorgelagerter DPPM-Planer für SelfAI einrichten, inkl. Konfiguration, Prompting, Confirmation Flow, Plan-Speicherung.
        """
    ).strip()

    return template

def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        cleaned = cleaned.strip()
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned


def run(goal: str, provider_name: str | None = None) -> int:
    config = load_configuration()
    planner_cfg = getattr(config, "planner", None)
    if not planner_cfg or not planner_cfg.enabled:
        print("❌ Planner ist in der Konfiguration deaktiviert. Abbruch.")
        return 1

    if not planner_cfg.providers:
        print("❌ Keine Planner-Provider konfiguriert.")
        return 1

    provider = None
    if provider_name:
        provider = next(
            (p for p in planner_cfg.providers if p.name == provider_name), None
        )
        if provider is None:
            print(f"❌ Provider '{provider_name}' nicht gefunden.")
            return 1
    else:
        provider = planner_cfg.providers[0]

    payload = {
        "model": provider.model,
        "prompt": _build_prompt(goal),
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": provider.max_tokens,
        },
    }

    print(
        f"→ Provider '{provider.name}' @ {provider.base_url} (Timeout {provider.timeout}s, Modell {provider.model})"
    )

    try:
        with httpx.Client(timeout=provider.timeout) as client:
            response = client.post(
                f"{provider.base_url.rstrip('/')}/api/generate",
                json=payload,
                headers=provider.headers or None,
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        print(f"❌ Timeout nach {provider.timeout}s beim Kontaktieren des Providers.")
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            f"❌ Ollama HTTP-Fehler: {exc.response.status_code} - {exc.response.text}"
        )
        return 1
    except httpx.RequestError as exc:
        print(f"❌ Allgemeiner Request-Fehler: {exc}")
        return 1

    try:
        body = response.json()
    except json.JSONDecodeError:
        print("❌ Ollama-Response war kein gültiges JSON.")
        print(f"Raw Response: {response.text[:500]}")
        return 1

    planner_text = body.get("response")
    if not planner_text:
        print("❌ Feld 'response' fehlt in der Ollama-Antwort.")
        print(json.dumps(body, indent=2))
        return 1

    planner_text = _strip_code_fences(planner_text)
    if "END_OF_PLAN" in planner_text:
        planner_text = planner_text.split("END_OF_PLAN", 1)[0].strip()

    try:
        planner_json = json.loads(planner_text)
    except json.JSONDecodeError as exc:
        print("❌ Planner-Ausgabe ist kein gültiges JSON.")
        done_reason = body.get("done_reason")
        if done_reason:
            print(f"Hinweis: done_reason = {done_reason}")
        print(f"Fehler: {exc}")
        print(f"Output: {planner_text}")
        return 1

    if "subtasks" not in planner_json:
        print("❌ Planner-JSON enthält keinen 'subtasks'-Eintrag.")
        print(json.dumps(planner_json, indent=2, ensure_ascii=False))
        return 1

    print("✅ Ollama-Plan erfolgreich empfangen.")
    print(json.dumps(planner_json, indent=2, ensure_ascii=False))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike: Testet den Ollama-Planer-Endpunkt",
    )
    parser.add_argument(
        "--goal",
        required=True,
        help="Zielbeschreibung, für die ein Plan erzeugt werden soll.",
    )
    parser.add_argument(
        "--provider",
        help="Optionaler Planner-Provider-Name aus der Konfiguration.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = run(args.goal, provider_name=args.provider)
    sys.exit(exit_code)
