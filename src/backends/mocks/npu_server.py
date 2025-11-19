#!/usr/bin/env python3
"""FastAPI-based NPU simulator for testing without real hardware.

This standalone server mimics the AnythingLLM API endpoints, allowing developers
without NPU hardware to test the full stack in "Simulation Mode".

Features:
- Configurable response delay (simulates NPU inference time)
- Streaming and non-streaming endpoints
- Workspace management
- Health check endpoints
- Request logging and metrics

Usage:
    # Start the simulator
    python -m src.backends.mocks.npu_server

    # Or with uvicorn directly
    uvicorn src.backends.mocks.npu_server:app --reload --port 3001

    # Configure delay (milliseconds)
    export NPU_SIM_DELAY=500

    # Test with curl
    curl http://localhost:3001/api/v1/workspace/main/chat \\
      -H "Authorization: Bearer test-key" \\
      -H "Content-Type: application/json" \\
      -d '{"message": "Hello", "mode": "chat"}'

Integration:
    >>> # In your application, point to simulator
    >>> settings.npu_provider.base_url = "http://localhost:3001/api/v1"
    >>> settings.npu_provider.api_key = "test-key"
    >>>
    >>> # Use normally
    >>> provider = NPUProvider(settings.npu_provider)
    >>> response = await provider.generate_response(messages)
"""

import asyncio
import json
import os
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


# =============================================================================
# CONFIGURATION
# =============================================================================


# Simulated inference delay in seconds
INFERENCE_DELAY = float(os.getenv("NPU_SIM_DELAY", "1.0"))

# Valid API key for testing
VALID_API_KEY = os.getenv("NPU_SIM_API_KEY", "test-key")

# Simulated model name
MODEL_NAME = os.getenv("NPU_SIM_MODEL", "Phi-3.5-Mini-Simulated")


# =============================================================================
# DATA MODELS
# =============================================================================


class ChatRequest(BaseModel):
    """Chat request payload."""

    message: str
    mode: str = "chat"
    temperature: Optional[float] = 0.7
    maxTokens: Optional[int] = 512
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    """Chat response payload."""

    textResponse: str
    workspace: str
    model: str
    timestamp: float


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================


app = FastAPI(
    title="NPU Simulator",
    description="Mock AnythingLLM API for testing without NPU hardware",
    version="1.0.0",
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def verify_api_key(authorization: Optional[str] = None) -> bool:
    """Verify API key from Authorization header.

    Args:
        authorization: Authorization header value.

    Returns:
        True if API key is valid.
    """
    if not authorization:
        return False

    # Remove "Bearer " prefix
    token = authorization.replace("Bearer ", "").strip()
    return token == VALID_API_KEY


def generate_simulated_response(message: str) -> str:
    """Generate a simulated response based on the input message.

    Args:
        message: User's input message.

    Returns:
        Simulated AI response.
    """
    # Simple rule-based responses for testing
    message_lower = message.lower()

    if "hello" in message_lower or "hi" in message_lower:
        return "Hello! I'm the NPU simulator. How can I help you today?"

    elif "python" in message_lower:
        return (
            "Python is a high-level, interpreted programming language known for its "
            "simplicity and readability. It's widely used in web development, data science, "
            "AI/ML, and automation. [Simulated NPU Response]"
        )

    elif "test" in message_lower:
        return (
            f"This is a simulated response from the NPU simulator. "
            f"Your message was: '{message}'. "
            f"Response delay: {INFERENCE_DELAY}s. Model: {MODEL_NAME}"
        )

    else:
        return (
            f"I received your message: '{message}'. "
            f"This is a simulated response from the NPU simulator ({MODEL_NAME}). "
            f"In production, this would be processed by the real NPU hardware."
        )


# =============================================================================
# API ENDPOINTS
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "NPU Simulator",
        "version": "1.0.0",
        "status": "running",
        "model": MODEL_NAME,
        "inference_delay": INFERENCE_DELAY,
    }


@app.get("/api/v1/workspace/{workspace_slug}")
async def get_workspace(
    workspace_slug: str,
    authorization: Optional[str] = Header(None),
):
    """Get workspace info (health check endpoint).

    Args:
        workspace_slug: Workspace identifier.
        authorization: Authorization header.

    Returns:
        Workspace information.
    """
    if not verify_api_key(authorization):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "workspace": workspace_slug,
        "model": MODEL_NAME,
        "status": "active",
        "provider": "npu_simulator",
    }


@app.post("/api/v1/workspace/{workspace_slug}/chat")
async def chat(
    workspace_slug: str,
    request: ChatRequest,
    authorization: Optional[str] = Header(None),
):
    """Non-streaming chat endpoint.

    Args:
        workspace_slug: Workspace identifier.
        request: Chat request payload.
        authorization: Authorization header.

    Returns:
        Chat response.
    """
    if not verify_api_key(authorization):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Simulate NPU inference delay
    await asyncio.sleep(INFERENCE_DELAY)

    # Generate simulated response
    response_text = generate_simulated_response(request.message)

    return ChatResponse(
        textResponse=response_text,
        workspace=workspace_slug,
        model=MODEL_NAME,
        timestamp=time.time(),
    )


@app.post("/api/v1/workspace/{workspace_slug}/stream-chat")
async def stream_chat(
    workspace_slug: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Streaming chat endpoint using Server-Sent Events.

    Args:
        workspace_slug: Workspace identifier.
        request: HTTP request.
        authorization: Authorization header.

    Returns:
        StreamingResponse with SSE format.
    """
    if not verify_api_key(authorization):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Parse request body
    body = await request.json()
    chat_request = ChatRequest(**body)

    # Generate full response
    response_text = generate_simulated_response(chat_request.message)

    async def event_generator():
        """Generate Server-Sent Events."""
        # Split response into words for streaming
        words = response_text.split()

        for i, word in enumerate(words):
            # Simulate token generation delay
            await asyncio.sleep(INFERENCE_DELAY / len(words))

            # Add space before word (except first)
            chunk = word if i == 0 else f" {word}"

            # Send SSE event
            event_data = {"textResponse": chunk, "delta": chunk}
            yield f"data: {json.dumps(event_data)}\n\n"

        # Send completion marker
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status.
    """
    return {
        "status": "healthy",
        "service": "npu_simulator",
        "model": MODEL_NAME,
        "timestamp": time.time(),
    }


# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================


@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    print("=" * 70)
    print("NPU SIMULATOR STARTED")
    print("=" * 70)
    print(f"Model: {MODEL_NAME}")
    print(f"Inference Delay: {INFERENCE_DELAY}s")
    print(f"API Key: {VALID_API_KEY}")
    print(f"Base URL: http://localhost:3001/api/v1")
    print("=" * 70)
    print("\nEndpoints:")
    print("  GET  /                                     - Server info")
    print("  GET  /health                               - Health check")
    print("  GET  /api/v1/workspace/{slug}              - Workspace info")
    print("  POST /api/v1/workspace/{slug}/chat         - Non-streaming chat")
    print("  POST /api/v1/workspace/{slug}/stream-chat  - Streaming chat")
    print("\nExample usage:")
    print('  curl http://localhost:3001/api/v1/workspace/main/chat \\')
    print('    -H "Authorization: Bearer test-key" \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"message": "Hello", "mode": "chat"}\'')
    print("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information."""
    print("\nNPU Simulator shutting down...")


# =============================================================================
# MAIN (for direct execution)
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    # Parse command-line arguments
    import argparse

    parser = argparse.ArgumentParser(description="NPU Simulator Server")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3001,
        help="Port to bind to (default: 3001)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Simulated inference delay in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="test-key",
        help="API key for authentication (default: test-key)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes",
    )

    args = parser.parse_args()

    # Update global configuration
    INFERENCE_DELAY = args.delay
    VALID_API_KEY = args.api_key

    # Start server
    uvicorn.run(
        "src.backends.mocks.npu_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
