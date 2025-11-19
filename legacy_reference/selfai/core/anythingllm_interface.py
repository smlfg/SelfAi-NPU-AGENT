import json
import uuid
from typing import Iterable, Iterator

import httpx


class AnythingLLMInterface:
    """HTTP-Client für die AnythingLLM-Workspace-API (Snapdragon NPU Backend)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        workspace_slug: str,
        *,
        stream: bool = True,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("API-Token für AnythingLLM fehlt.")
        if not base_url:
            raise ValueError("Basis-URL für AnythingLLM fehlt.")
        if not workspace_slug:
            raise ValueError("Workspace-Slug für AnythingLLM fehlt.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.workspace_slug = workspace_slug
        self.stream_enabled = stream
        self.timeout = timeout
        self.session_id = f"selfai-{uuid.uuid4()}"

        self.chat_url = (
            f"{self.base_url}/workspace/{self.workspace_slug}/chat"
        )
        self.stream_url = (
            f"{self.base_url}/workspace/{self.workspace_slug}/stream-chat"
        )

        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # Mini-Healthcheck beim Initialisieren, damit Fehlkonfigurationen früh auffallen.
        self._check_auth()

    def _check_auth(self) -> None:
        """Validiert den API-Key gegen den Auth-Endpunkt."""
        auth_url = f"{self.base_url}/auth"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(auth_url, headers=self.headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"AnythingLLM Auth fehlgeschlagen (Status {exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Keine Verbindung zu AnythingLLM möglich: {exc}"
            ) from exc

    @staticmethod
    def _build_prompt(
        system_prompt: str,
        user_prompt: str,
        history: Iterable[dict] | None,
    ) -> str:
        """Formatiert System-Prompt, History und Nutzerprompt zu einer Nachricht."""
        sections: list[str] = []

        if system_prompt:
            sections.append(f"[System]\n{system_prompt.strip()}")

        if history:
            for message in history:
                role = message.get("role", "").lower()
                content = message.get("content", "")
                if not content:
                    continue
                if role == "assistant":
                    sections.append(f"[Assistant]\n{content.strip()}")
                elif role == "user":
                    sections.append(f"[User]\n{content.strip()}")
                else:
                    sections.append(f"[{role or 'Message'}]\n{content.strip()}")

        sections.append(f"[User]\n{user_prompt.strip()}")
        return "\n\n".join(sections)

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list | None = None,
        *,
        timeout: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """
        Sendet eine Chat-Anfrage an AnythingLLM und gibt die Textantwort zurück.
        Streaming wird intern deaktiviert, da SelfAI synchron arbeitet.
        """
        payload = {
            "message": self._build_prompt(system_prompt, user_prompt, history),
            "mode": "chat",
            "sessionId": self.session_id,
            "attachments": [],
        }
        if max_output_tokens:
            payload["maxOutputTokens"] = int(max_output_tokens)

        client_timeout = timeout or self.timeout
        try:
            with httpx.Client(timeout=client_timeout) as client:
                response = client.post(
                    self.chat_url, headers=self.headers, json=payload
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_payload = exc.response.text
            raise RuntimeError(
                f"AnythingLLM antwortete mit HTTP {exc.response.status_code}: {error_payload}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Fehler beim Kontaktieren von AnythingLLM: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Antwort von AnythingLLM ist kein gültiges JSON: {response.text}"
            ) from exc

        text = data.get("textResponse")
        if not text:
            raise RuntimeError(
                f"AnythingLLM lieferte keine textResponse zurück: {data}"
            )
        return text

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list | None = None,
        *,
        timeout: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]:
        """
        Streamt eine Chat-Antwort. Gibt Text-Segmente (Chunks) zurück.
        """
        if not self.stream_enabled:
            raise RuntimeError("Streaming ist für AnythingLLM deaktiviert.")

        payload = {
            "message": self._build_prompt(system_prompt, user_prompt, history),
            "mode": "chat",
            "sessionId": self.session_id,
            "attachments": [],
        }
        if max_output_tokens:
            payload["maxOutputTokens"] = int(max_output_tokens)

        buffer = ""
        client_timeout = timeout or self.timeout
        try:
            with httpx.Client(timeout=client_timeout) as client:
                with client.stream(
                    "POST",
                    self.stream_url,
                    headers=self.headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()

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
                                return
                            try:
                                parsed_chunk = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            if parsed_chunk.get("error"):
                                raise RuntimeError(
                                    f"AnythingLLM Fehler: "
                                    f"{parsed_chunk['error']}"
                                )

                            text_delta = (
                                parsed_chunk.get("textResponseDelta")
                                or parsed_chunk.get("delta")
                            )
                            full_text = parsed_chunk.get("textResponse")
                            if text_delta:
                                yield text_delta
                            elif full_text:
                                yield full_text
                            if parsed_chunk.get("close"):
                                return

        except httpx.HTTPStatusError as exc:
            error_payload = exc.response.text
            raise RuntimeError(
                f"AnythingLLM Streaming-Request schlug fehl "
                f"(HTTP {exc.response.status_code}): {error_payload}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Fehler beim Streaming von AnythingLLM: {exc}"
            ) from exc

        # Falls nach dem Stream noch Daten übrig sind, versuche sie zu parsen.
        if buffer:
            try:
                parsed_response = json.loads(buffer)
                if parsed_response.get("error"):
                    raise RuntimeError(
                        f"AnythingLLM Fehler: {parsed_response['error']}"
                    )
                full_text = parsed_response.get("textResponse")
                if full_text:
                    yield full_text
            except json.JSONDecodeError:
                # Unvollständige Reste ignorieren.
                pass
