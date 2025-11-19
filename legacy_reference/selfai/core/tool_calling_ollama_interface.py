
"""Ollama-basierter Tool-Caller für SelfAI."""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from typing import Any, Dict

import httpx

from selfai.tools.tool_registry import get_all_tool_schemas

class ToolCallingError(RuntimeError):
    """Basisklasse für Tool-Calling-bezogene Fehler."""

@dataclass
class ToolCallingContext:
    # Vorerst leer, könnte aber zukünftig für Kontext-Informationen genutzt werden
    pass

class ToolCallingOllamaInterface:
    """Kommuniziert mit einem Ollama-Endpunkt, um Tool-Aufrufe zu generieren."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
        headers: Dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.generate_url = f"{self.base_url}/api/generate"
        self.headers = headers or {}

    def _build_prompt(self, user_prompt: str) -> str:
        """Erstellt den Prompt, um das LLM zur Tool-Nutzung anzuleiten."""
        
        tool_schemas = get_all_tool_schemas()
        tools_json_str = json.dumps(tool_schemas, indent=2)

        template = textwrap.dedent(
            f"""Du bist ein hilfreicher Assistent, der Zugriff auf eine Reihe von Tools hat.

Deine Aufgabe ist es, basierend auf der Anfrage des Benutzers zu entscheiden, ob eines dieser Tools nützlich sein könnte. 
Wenn ja, musst du ein JSON-Objekt generieren, das den Namen des Tools und die erforderlichen Argumente enthält. 
Wenn kein Tool passt, antworte einfach direkt auf die Anfrage des Benutzers.

**Hier sind die verfügbaren Tools:**
```json
{tools_json_str}
```

**Regeln für die Tool-Nutzung:**
1.  Wenn du dich für die Nutzung eines Tools entscheidest, darf deine Antwort **ausschließlich** das JSON-Objekt für den Tool-Aufruf enthalten. Kein zusätzlicher Text, keine Erklärungen, keine Markdown-Formatierung.
2.  Das JSON-Objekt muss folgendes Format haben:
    ```json
    {{
        "tool_name": "<name_des_tools>",
        "arguments": {{
            "<arg_name_1>": "<wert_1>",
            "<arg_name_2>": "<wert_2>"
        }}
    }}
    ```
3.  Wenn kein Tool zur Beantwortung der Anfrage geeignet ist, antworte einfach als normaler Chatbot. Formuliere eine hilfreiche, textbasierte Antwort.

**Benutzeranfrage:**
{user_prompt}

**Deine Antwort:**
"""
        ).strip()

        return template

    def generate_tool_call(self, user_prompt: str) -> dict | str:
        """Erzeugt entweder einen Tool-Aufruf (dict) oder eine Textantwort (str)."""

        payload = {
            "model": self.model,
            "prompt": self._build_prompt(user_prompt),
            "stream": False,
            "format": "json", # Wir bitten um JSON, aber das Modell kann immer noch Text ausgeben
            "options": {
                "temperature": 0.0,
                "num_predict": self.max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.generate_url,
                    json=payload,
                    headers=self.headers or None,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ToolCallingError(
                f"Ollama antwortete nicht innerhalb von {self.timeout} Sekunden."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ToolCallingError(
                f"Ollama HTTP-Fehler {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ToolCallingError(f"Fehler beim Kontaktieren von Ollama: {exc}") from exc

        try:
            body = response.json()
            raw_response = body.get("response", "").strip()
        except json.JSONDecodeError:
            # Wenn die Antwort kein JSON ist, behandeln wir sie als reine Textantwort
            raw_response = response.text.strip()

        # Versuch, die Antwort als JSON (Tool-Aufruf) zu parsen
        try:
            # Wir nehmen an, dass eine Antwort, die mit { beginnt, ein JSON-Objekt ist
            if raw_response.startswith("{"):
                parsed_json = json.loads(raw_response)
                if "tool_name" in parsed_json and "arguments" in parsed_json:
                    return parsed_json # Es ist ein valider Tool-Aufruf
        except json.JSONDecodeError:
            # Es sah aus wie JSON, war aber keins. Wir behandeln es als Text.
            pass

        # Wenn alles andere fehlschlägt, geben wir die Antwort als reinen Text zurück
        return raw_response

