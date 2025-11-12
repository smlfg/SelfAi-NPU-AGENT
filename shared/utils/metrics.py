"""
Shared metrics collection for all agents.
"""

from typing import Dict, Any
from datetime import datetime
import json


class MetricsCollector:
    """
    Collects and exports metrics for monitoring.

    Usage:
        metrics = MetricsCollector("agent2_dashboard")
        metrics.increment("requests_total")
        metrics.set_gauge("gpu_utilization", 75.5)
        metrics.export()
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = {}

    def increment(self, name: str, value: int = 1):
        """Increment a counter"""
        self.counters[name] = self.counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float):
        """Set a gauge value"""
        self.gauges[name] = value

    def record_histogram(self, name: str, value: float):
        """Record a histogram value"""
        if name not in self.histograms:
            self.histograms[name] = []
        self.histograms[name].append(value)

    def export(self) -> Dict[str, Any]:
        """Export metrics as dictionary"""
        return {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "counters": self.counters,
            "gauges": self.gauges,
            "histograms": {
                name: {
                    "count": len(values),
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "avg": sum(values) / len(values) if values else 0
                }
                for name, values in self.histograms.items()
            }
        }

    def export_json(self) -> str:
        """Export metrics as JSON string"""
        return json.dumps(self.export(), indent=2)

    def reset(self):
        """Reset all metrics"""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
