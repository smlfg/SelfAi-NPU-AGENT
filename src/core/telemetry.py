"""Telemetry and metrics tracking system for LLM backend performance monitoring.

This module provides a singleton TelemetryManager that tracks:
- Latency metrics (response time per provider)
- Token usage statistics
- Success/failure rates
- Provider performance comparisons (NPU vs CPU)

The metrics are stored in a local JSON file for analysis and reporting.
"""

import functools
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

# Type variable for generic decorator support
F = TypeVar('F', bound=Callable[..., Any])


class TelemetryManager:
    """Singleton manager for tracking LLM backend performance metrics.

    This class provides centralized telemetry collection with thread-safe operations.
    It tracks latency, token usage, and provider performance to help optimize
    backend selection and prove NPU performance benefits.

    Attributes:
        _instance: Singleton instance.
        _lock: Thread lock for singleton instantiation.
        enabled: Whether telemetry collection is enabled.
        stats_file: Path to the JSON stats file.
        metrics: In-memory metrics storage.
        _file_lock: Thread lock for file operations.

    Example:
        >>> telemetry = TelemetryManager.get_instance()
        >>> telemetry.record_latency("NPUProvider", 0.5, True)
        >>> telemetry.record_token_usage("NPUProvider", 150, 50)
        >>> stats = telemetry.get_statistics()
    """

    _instance: Optional['TelemetryManager'] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, stats_file: Optional[Path] = None, enabled: bool = True) -> None:
        """Initialize the telemetry manager.

        Args:
            stats_file: Path to the JSON stats file (default: ./telemetry/stats.json).
            enabled: Whether to enable telemetry collection.

        Note:
            Do not call this directly. Use get_instance() instead.
        """
        if TelemetryManager._instance is not None:
            raise RuntimeError(
                "TelemetryManager is a singleton. Use get_instance() instead."
            )

        self.enabled = enabled
        self.stats_file = stats_file or Path("telemetry/stats.json")
        self._file_lock = threading.Lock()

        # Initialize metrics structure
        self.metrics: Dict[str, Any] = {
            "session_start": datetime.now().isoformat(),
            "providers": {},
            "totals": {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "total_latency": 0.0,
                "total_tokens": 0,
            },
        }

        # Load existing metrics if file exists
        self._load_metrics()

    @classmethod
    def get_instance(
        cls,
        stats_file: Optional[Path] = None,
        enabled: bool = True,
    ) -> 'TelemetryManager':
        """Get or create the singleton instance.

        Args:
            stats_file: Path to stats file (only used on first call).
            enabled: Whether telemetry is enabled (only used on first call).

        Returns:
            The singleton TelemetryManager instance.

        Thread-safe:
            Uses double-checked locking for performance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(stats_file=stats_file, enabled=enabled)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing).

        Warning:
            This should only be used in test environments.
        """
        with cls._lock:
            cls._instance = None

    def _load_metrics(self) -> None:
        """Load existing metrics from the stats file."""
        if not self.enabled:
            return

        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    stored_metrics = json.load(f)
                    # Merge stored metrics with current session
                    self.metrics["providers"] = stored_metrics.get("providers", {})
                    # Keep current session start time
            except (json.JSONDecodeError, OSError) as exc:
                # If file is corrupted, start fresh
                print(f"Warning: Could not load telemetry data: {exc}")

    def _save_metrics(self) -> None:
        """Save current metrics to the stats file."""
        if not self.enabled:
            return

        with self._file_lock:
            # Ensure directory exists
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self.metrics, f, indent=2, ensure_ascii=False)
            except OSError as exc:
                print(f"Warning: Could not save telemetry data: {exc}")

    def _ensure_provider_metrics(self, provider_name: str) -> None:
        """Ensure metrics structure exists for a provider.

        Args:
            provider_name: Name of the provider.
        """
        if provider_name not in self.metrics["providers"]:
            self.metrics["providers"][provider_name] = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "total_latency": 0.0,
                "min_latency": float('inf'),
                "max_latency": 0.0,
                "total_tokens": 0,
                "latency_samples": [],
            }

    def record_latency(
        self,
        provider_name: str,
        latency: float,
        success: bool = True,
    ) -> None:
        """Record a latency measurement for a provider.

        Args:
            provider_name: Name of the LLM provider.
            latency: Response time in seconds.
            success: Whether the request succeeded.
        """
        if not self.enabled:
            return

        self._ensure_provider_metrics(provider_name)
        provider = self.metrics["providers"][provider_name]

        # Update provider metrics
        provider["requests"] += 1
        if success:
            provider["successes"] += 1
            provider["total_latency"] += latency
            provider["min_latency"] = min(provider["min_latency"], latency)
            provider["max_latency"] = max(provider["max_latency"], latency)

            # Keep last 100 samples for detailed analysis
            provider["latency_samples"].append({
                "timestamp": datetime.now().isoformat(),
                "latency": latency,
            })
            if len(provider["latency_samples"]) > 100:
                provider["latency_samples"].pop(0)
        else:
            provider["failures"] += 1

        # Update totals
        self.metrics["totals"]["requests"] += 1
        if success:
            self.metrics["totals"]["successes"] += 1
            self.metrics["totals"]["total_latency"] += latency
        else:
            self.metrics["totals"]["failures"] += 1

        self._save_metrics()

    def record_token_usage(
        self,
        provider_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage for a provider.

        Args:
            provider_name: Name of the LLM provider.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
        """
        if not self.enabled:
            return

        self._ensure_provider_metrics(provider_name)
        provider = self.metrics["providers"][provider_name]

        total_tokens = input_tokens + output_tokens
        provider["total_tokens"] += total_tokens
        self.metrics["totals"]["total_tokens"] += total_tokens

        self._save_metrics()

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregated statistics for all providers.

        Returns:
            Dictionary containing comprehensive statistics including:
            - Per-provider metrics
            - Average latencies
            - Success rates
            - Performance comparisons

        Example:
            >>> stats = telemetry.get_statistics()
            >>> print(stats['providers']['NPUProvider']['avg_latency'])
            0.342
        """
        if not self.enabled:
            return {"enabled": False}

        stats: Dict[str, Any] = {
            "enabled": True,
            "session_start": self.metrics["session_start"],
            "totals": dict(self.metrics["totals"]),
            "providers": {},
        }

        # Calculate per-provider statistics
        for provider_name, provider_data in self.metrics["providers"].items():
            successes = provider_data["successes"]
            requests = provider_data["requests"]

            provider_stats = {
                "requests": requests,
                "successes": successes,
                "failures": provider_data["failures"],
                "success_rate": (successes / requests * 100) if requests > 0 else 0.0,
                "total_latency": provider_data["total_latency"],
                "avg_latency": (
                    provider_data["total_latency"] / successes
                    if successes > 0 else 0.0
                ),
                "min_latency": (
                    provider_data["min_latency"]
                    if provider_data["min_latency"] != float('inf') else 0.0
                ),
                "max_latency": provider_data["max_latency"],
                "total_tokens": provider_data["total_tokens"],
            }

            stats["providers"][provider_name] = provider_stats

        # Add global averages
        total_requests = stats["totals"]["requests"]
        total_successes = stats["totals"]["successes"]
        stats["totals"]["success_rate"] = (
            total_successes / total_requests * 100
            if total_requests > 0 else 0.0
        )
        stats["totals"]["avg_latency"] = (
            stats["totals"]["total_latency"] / total_successes
            if total_successes > 0 else 0.0
        )

        return stats

    def compare_providers(self) -> Dict[str, Any]:
        """Compare performance between different providers.

        Returns:
            Dictionary with comparative analysis including:
            - Fastest provider
            - NPU vs CPU speedup ratio
            - Success rate comparison

        Example:
            >>> comparison = telemetry.compare_providers()
            >>> print(f"NPU is {comparison['speedup']:.2f}x faster than CPU")
        """
        stats = self.get_statistics()

        if not stats.get("enabled"):
            return {"enabled": False}

        providers = stats.get("providers", {})
        if not providers:
            return {"error": "No provider data available"}

        comparison: Dict[str, Any] = {
            "providers": list(providers.keys()),
        }

        # Find fastest provider
        fastest_provider = None
        fastest_latency = float('inf')
        for name, data in providers.items():
            avg_latency = data.get("avg_latency", float('inf'))
            if avg_latency > 0 and avg_latency < fastest_latency:
                fastest_latency = avg_latency
                fastest_provider = name

        comparison["fastest_provider"] = fastest_provider
        comparison["fastest_latency"] = fastest_latency

        # NPU vs CPU comparison
        npu_latency = None
        cpu_latency = None

        for name, data in providers.items():
            avg = data.get("avg_latency", 0)
            if "NPU" in name or "npu" in name or "AnythingLLM" in name:
                npu_latency = avg
            elif "CPU" in name or "cpu" in name:
                cpu_latency = avg

        if npu_latency and cpu_latency and npu_latency > 0:
            comparison["npu_latency"] = npu_latency
            comparison["cpu_latency"] = cpu_latency
            comparison["speedup"] = cpu_latency / npu_latency
            comparison["performance_gain_percent"] = (
                (cpu_latency - npu_latency) / cpu_latency * 100
            )

        return comparison

    def clear_metrics(self) -> None:
        """Clear all collected metrics and reset to initial state."""
        self.metrics = {
            "session_start": datetime.now().isoformat(),
            "providers": {},
            "totals": {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "total_latency": 0.0,
                "total_tokens": 0,
            },
        }
        self._save_metrics()

    def export_report(self, output_file: Optional[Path] = None) -> str:
        """Export a human-readable performance report.

        Args:
            output_file: Optional file path to save the report.

        Returns:
            The formatted report as a string.
        """
        stats = self.get_statistics()
        comparison = self.compare_providers()

        lines = [
            "=" * 70,
            "LLM BACKEND PERFORMANCE REPORT",
            "=" * 70,
            f"Session Start: {stats.get('session_start', 'N/A')}",
            f"Telemetry: {'Enabled' if stats.get('enabled') else 'Disabled'}",
            "",
            "OVERALL STATISTICS",
            "-" * 70,
            f"Total Requests: {stats['totals']['requests']}",
            f"Successes: {stats['totals']['successes']}",
            f"Failures: {stats['totals']['failures']}",
            f"Success Rate: {stats['totals']['success_rate']:.2f}%",
            f"Average Latency: {stats['totals']['avg_latency']:.3f}s",
            f"Total Tokens: {stats['totals']['total_tokens']}",
            "",
            "PER-PROVIDER METRICS",
            "-" * 70,
        ]

        for provider_name, provider_stats in stats.get("providers", {}).items():
            lines.extend([
                f"\n{provider_name}:",
                f"  Requests: {provider_stats['requests']}",
                f"  Success Rate: {provider_stats['success_rate']:.2f}%",
                f"  Avg Latency: {provider_stats['avg_latency']:.3f}s",
                f"  Min Latency: {provider_stats['min_latency']:.3f}s",
                f"  Max Latency: {provider_stats['max_latency']:.3f}s",
                f"  Total Tokens: {provider_stats['total_tokens']}",
            ])

        if comparison.get("speedup"):
            lines.extend([
                "",
                "NPU vs CPU PERFORMANCE",
                "-" * 70,
                f"NPU Latency: {comparison['npu_latency']:.3f}s",
                f"CPU Latency: {comparison['cpu_latency']:.3f}s",
                f"Speedup: {comparison['speedup']:.2f}x",
                f"Performance Gain: {comparison['performance_gain_percent']:.1f}%",
            ])

        lines.append("=" * 70)
        report = "\n".join(lines)

        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(report, encoding='utf-8')

        return report


# Decorator for tracking latency
def track_latency(provider_name: Optional[str] = None) -> Callable[[F], F]:
    """Decorator to automatically track function latency.

    Args:
        provider_name: Name of the provider (if None, uses function name).

    Returns:
        Decorated function that records latency to telemetry.

    Example:
        >>> @track_latency("NPUProvider")
        >>> def generate_response(prompt: str) -> str:
        ...     # Implementation
        ...     return "response"
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            telemetry = TelemetryManager.get_instance()

            # Determine provider name
            name = provider_name
            if name is None:
                # Try to get from self (for methods)
                if args and hasattr(args[0], 'provider_name'):
                    name = args[0].provider_name
                else:
                    name = func.__name__

            start_time = time.time()
            success = False
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                latency = time.time() - start_time
                telemetry.record_latency(name, latency, success)

        return cast(F, wrapper)
    return decorator


# Decorator for tracking token usage
def track_token_usage(provider_name: Optional[str] = None) -> Callable[[F], F]:
    """Decorator to automatically track token usage.

    The decorated function should return a tuple or dict containing token counts.

    Args:
        provider_name: Name of the provider (if None, uses function name).

    Returns:
        Decorated function that records token usage to telemetry.

    Example:
        >>> @track_token_usage("NPUProvider")
        >>> def generate(prompt: str) -> dict:
        ...     return {
        ...         "response": "text",
        ...         "input_tokens": 10,
        ...         "output_tokens": 20,
        ...     }
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            telemetry = TelemetryManager.get_instance()

            # Determine provider name
            name = provider_name
            if name is None:
                if args and hasattr(args[0], 'provider_name'):
                    name = args[0].provider_name
                else:
                    name = func.__name__

            result = func(*args, **kwargs)

            # Extract token counts from result
            input_tokens = 0
            output_tokens = 0

            if isinstance(result, dict):
                input_tokens = result.get("input_tokens", 0)
                output_tokens = result.get("output_tokens", 0)
            elif isinstance(result, tuple) and len(result) >= 2:
                input_tokens = result[0] if isinstance(result[0], int) else 0
                output_tokens = result[1] if isinstance(result[1], int) else 0

            if input_tokens > 0 or output_tokens > 0:
                telemetry.record_token_usage(name, input_tokens, output_tokens)

            return result

        return cast(F, wrapper)
    return decorator
