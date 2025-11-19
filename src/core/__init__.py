"""Core utilities and infrastructure for SelfAI NPU Agent.

This package contains essential infrastructure components:
- Telemetry: Performance tracking and metrics collection
- (Future) Configuration management
- (Future) Logging utilities
- (Future) Error handling
"""

from src.core.telemetry import (
    TelemetryManager,
    track_latency,
    track_token_usage,
)

__all__ = [
    "TelemetryManager",
    "track_latency",
    "track_token_usage",
]
