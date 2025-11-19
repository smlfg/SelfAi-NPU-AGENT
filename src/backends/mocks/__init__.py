"""Mock servers and simulators for testing.

This package provides test doubles for external dependencies:
    - NPU Simulator: FastAPI server mimicking AnythingLLM API

Usage:
    # Start NPU simulator
    python -m src.backends.mocks.npu_server --port 3001

    # Or with uvicorn
    uvicorn src.backends.mocks.npu_server:app --reload --port 3001
"""

__all__ = ["npu_server"]
