"""Ollama-Chat-Interface für Merge-Ausgaben."""

from __future__ import annotations

import json
from typing import Dict, Iterator, Optional

import httpx


class MergeOllamaInterface:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.headers = headers or {}
        self.generate_url = f"{self.base_url}/api/generate"

    def _stream_request(self, payload: Dict[str, object]) -> Iterator[str]:
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                self.generate_url,
                json=payload,
                headers=self.headers or None,
            ) as response:
                response.raise_for_status()
                buffer = ""
                for chunk in response.iter_text():
                    if not chunk:
                        continue
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            line = line[len("data:") :].strip()
                        if not line or line in ("[DONE]", "DONE"):
                            continue
                        try:
                            parsed = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if parsed.get("error"):
                            raise RuntimeError(parsed["error"])
                        if parsed.get("response"):
                            yield parsed["response"]

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "prompt": f"[System]\n{system_prompt.strip()}\n\n[User]\n{user_prompt.strip()}",
            "stream": True,
            "options": {
                "temperature": 0.2,
                "num_predict": int(max_tokens or self.max_tokens),
            },
        }
        return self._stream_request(payload)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": f"[System]\n{system_prompt.strip()}\n\n[User]\n{user_prompt.strip()}",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": int(max_tokens or self.max_tokens),
            },
        }
        with httpx.Client(timeout=timeout or self.timeout) as client:
            response = client.post(
                self.generate_url,
                json=payload,
                headers=self.headers or None,
            )
            response.raise_for_status()
            data = response.json()
            output = data.get("response")
            if not output:
                raise RuntimeError("Ollama lieferte keine Antwort.")
            return output
