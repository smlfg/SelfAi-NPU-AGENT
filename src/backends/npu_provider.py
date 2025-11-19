"""NPU provider implementation using AnythingLLM for Snapdragon X Elite NPU acceleration.

This module implements the NPU-accelerated LLM provider using AnythingLLM as the backend.
It provides hardware-accelerated inference on devices with Snapdragon X Elite NPUs.
"""

import json
import uuid
from typing import Dict, Iterator, List, Optional

import httpx

from src.backends.base import LLMProvider


class NPUProvider(LLMProvider):
    """NPU-accelerated LLM provider using AnythingLLM HTTP API.

    This provider communicates with an AnythingLLM server to leverage Snapdragon X Elite
    NPU hardware acceleration for fast, efficient inference. It supports both blocking
    and streaming response generation.

    Attributes:
        api_key: API key for authenticating with AnythingLLM.
        base_url: Base URL of the AnythingLLM server (without trailing slash).
        workspace_slug: Workspace identifier in AnythingLLM.
        stream_enabled: Whether streaming responses are enabled.
        timeout: Request timeout in seconds.
        session_id: Unique session identifier for conversation tracking.
        chat_url: Full URL for non-streaming chat endpoint.
        stream_url: Full URL for streaming chat endpoint.
        headers: HTTP headers for API requests.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        workspace_slug: str,
        *,
        stream: bool = True,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the NPU provider.

        Args:
            api_key: AnythingLLM API authentication token.
            base_url: Base URL of the AnythingLLM server.
            workspace_slug: Workspace identifier for this session.
            stream: Whether to enable streaming responses (default: True).
            timeout: Request timeout in seconds (default: 60.0).

        Raises:
            ValueError: If required parameters (api_key, base_url, workspace_slug) are missing.
            RuntimeError: If the AnythingLLM server is not accessible or authentication fails.
        """
        super().__init__(provider_name="AnythingLLM", provider_type="npu")

        if not api_key:
            raise ValueError("API key for AnythingLLM is required.")
        if not base_url:
            raise ValueError("Base URL for AnythingLLM is required.")
        if not workspace_slug:
            raise ValueError("Workspace slug for AnythingLLM is required.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.workspace_slug = workspace_slug
        self.stream_enabled = stream
        self.timeout = timeout
        self.session_id = f"selfai-{uuid.uuid4()}"

        # Construct endpoint URLs
        self.chat_url = f"{self.base_url}/workspace/{self.workspace_slug}/chat"
        self.stream_url = f"{self.base_url}/workspace/{self.workspace_slug}/stream-chat"

        # Prepare HTTP headers
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # Validate connection and authentication
        self._check_auth()

    def _check_auth(self) -> None:
        """Validate API key against the AnythingLLM authentication endpoint.

        Raises:
            RuntimeError: If authentication fails or server is unreachable.
        """
        auth_url = f"{self.base_url}/auth"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(auth_url, headers=self.headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"AnythingLLM authentication failed (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Cannot connect to AnythingLLM server: {exc}"
            ) from exc

    @staticmethod
    def _build_prompt(
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Format system prompt, conversation history, and user prompt into a single message.

        Args:
            system_prompt: System-level instructions.
            user_prompt: Current user query.
            history: Optional conversation history.

        Returns:
            Formatted prompt string with all components combined.
        """
        sections: List[str] = []

        # Add system prompt
        if system_prompt:
            sections.append(f"[System]\n{system_prompt.strip()}")

        # Add conversation history
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

        # Add current user prompt
        sections.append(f"[User]\n{user_prompt.strip()}")

        return "\n\n".join(sections)

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a complete response from AnythingLLM (blocking call).

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Optional request timeout (overrides default).
            max_output_tokens: Optional maximum tokens to generate.

        Returns:
            Complete generated response text.

        Raises:
            RuntimeError: If the API request fails or returns invalid data.
        """
        payload = {
            "message": self._build_prompt(system_prompt, user_prompt, history),
            "mode": "chat",
            "sessionId": self.session_id,
            "attachments": [],
        }
        if max_output_tokens:
            payload["maxOutputTokens"] = int(max_output_tokens)

        client_timeout = timeout if timeout is not None else self.timeout

        try:
            with httpx.Client(timeout=client_timeout) as client:
                response = client.post(
                    self.chat_url, headers=self.headers, json=payload
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_payload = exc.response.text
            raise RuntimeError(
                f"AnythingLLM responded with HTTP {exc.response.status_code}: {error_payload}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Error contacting AnythingLLM: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"AnythingLLM response is not valid JSON: {response.text}"
            ) from exc

        text = data.get("textResponse")
        if not text:
            raise RuntimeError(
                f"AnythingLLM did not return a textResponse: {data}"
            )
        return text

    def stream_generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        timeout: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a streaming response from AnythingLLM (yields chunks).

        Args:
            system_prompt: System-level instructions.
            user_prompt: User query.
            history: Optional conversation history.
            timeout: Optional request timeout (overrides default).
            max_output_tokens: Optional maximum tokens to generate.

        Yields:
            Individual text chunks as they are generated.

        Raises:
            RuntimeError: If streaming is disabled or the API request fails.
        """
        if not self.stream_enabled:
            raise RuntimeError("Streaming is disabled for this NPU provider instance.")

        payload = {
            "message": self._build_prompt(system_prompt, user_prompt, history),
            "mode": "chat",
            "sessionId": self.session_id,
            "attachments": [],
        }
        if max_output_tokens:
            payload["maxOutputTokens"] = int(max_output_tokens)

        buffer = ""
        client_timeout = timeout if timeout is not None else self.timeout

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
                            # Remove SSE "data:" prefix
                            if line.startswith("data:"):
                                line = line[len("data:"):].strip()
                            if not line or line in ("[DONE]", "DONE"):
                                return
                            try:
                                parsed_chunk = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            # Check for errors
                            if parsed_chunk.get("error"):
                                raise RuntimeError(
                                    f"AnythingLLM error: {parsed_chunk['error']}"
                                )

                            # Extract text delta or full text
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
                f"AnythingLLM streaming request failed "
                f"(HTTP {exc.response.status_code}): {error_payload}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Error streaming from AnythingLLM: {exc}"
            ) from exc

        # Handle any remaining buffer content
        if buffer:
            try:
                parsed_response = json.loads(buffer)
                if parsed_response.get("error"):
                    raise RuntimeError(
                        f"AnythingLLM error: {parsed_response['error']}"
                    )
                full_text = parsed_response.get("textResponse")
                if full_text:
                    yield full_text
            except json.JSONDecodeError:
                # Ignore incomplete buffer remnants
                pass

    def supports_streaming(self) -> bool:
        """Check if streaming is enabled for this provider instance.

        Returns:
            True if streaming is enabled, False otherwise.
        """
        return self.stream_enabled

    def healthcheck(self) -> bool:
        """Perform a health check on the AnythingLLM service.

        Returns:
            True if the service is accessible and authentication succeeds, False otherwise.
        """
        try:
            self._check_auth()
            return True
        except RuntimeError:
            return False

    def get_metadata(self) -> Dict[str, any]:
        """Get metadata about this NPU provider.

        Returns:
            Dictionary containing provider metadata including workspace information.
        """
        metadata = super().get_metadata()
        metadata.update({
            "base_url": self.base_url,
            "workspace_slug": self.workspace_slug,
            "session_id": self.session_id,
            "timeout": self.timeout,
        })
        return metadata
