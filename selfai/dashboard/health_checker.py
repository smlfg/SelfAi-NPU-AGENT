"""
System Health Checker Module
Performs comprehensive system health checks and diagnostics.
"""

import psutil
import os
import socket
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import time


@dataclass
class HealthCheck:
    """Health check result"""
    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: Dict
    checked_at: str


@dataclass
class SystemHealth:
    """Overall system health status"""
    status: str  # "healthy", "degraded", "unhealthy"
    checks: List[HealthCheck]
    summary: Dict
    timestamp: str


class HealthChecker:
    """
    System health monitoring and diagnostics.

    Features:
    - CPU health monitoring
    - Memory usage checks
    - Disk space monitoring
    - GPU availability checks
    - Network connectivity tests
    - Service availability checks
    - Performance metrics
    """

    def __init__(self):
        self.thresholds = {
            "cpu_warning": 80.0,  # CPU usage %
            "cpu_critical": 95.0,
            "memory_warning": 80.0,  # Memory usage %
            "memory_critical": 95.0,
            "disk_warning": 85.0,  # Disk usage %
            "disk_critical": 95.0,
            "temperature_warning": 75.0,  # GPU temp °C
            "temperature_critical": 85.0
        }

    def check_health(self) -> SystemHealth:
        """
        Perform comprehensive health check.

        Returns:
            SystemHealth object with all check results
        """
        checks = []

        # Run all health checks
        checks.append(self._check_cpu())
        checks.append(self._check_memory())
        checks.append(self._check_disk())
        checks.append(self._check_gpu())
        checks.append(self._check_network())
        checks.append(self._check_processes())

        # Determine overall status
        statuses = [check.status for check in checks]
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Generate summary
        summary = {
            "total_checks": len(checks),
            "healthy": sum(1 for c in checks if c.status == "healthy"),
            "degraded": sum(1 for c in checks if c.status == "degraded"),
            "unhealthy": sum(1 for c in checks if c.status == "unhealthy")
        }

        return SystemHealth(
            status=overall_status,
            checks=checks,
            summary=summary,
            timestamp=datetime.now().isoformat()
        )

    def _check_cpu(self) -> HealthCheck:
        """Check CPU health"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

            # Determine status
            if cpu_percent >= self.thresholds["cpu_critical"]:
                status = "unhealthy"
                message = f"CPU usage critically high: {cpu_percent:.1f}%"
            elif cpu_percent >= self.thresholds["cpu_warning"]:
                status = "degraded"
                message = f"CPU usage elevated: {cpu_percent:.1f}%"
            else:
                status = "healthy"
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            details = {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "load_average": load_avg,
                "frequency_mhz": cpu_freq.current if cpu_freq else None
            }

            return HealthCheck(
                component="CPU",
                status=status,
                message=message,
                details=details,
                checked_at=datetime.now().isoformat()
            )

        except Exception as e:
            return HealthCheck(
                component="CPU",
                status="unhealthy",
                message=f"CPU check failed: {e}",
                details={},
                checked_at=datetime.now().isoformat()
            )

    def _check_memory(self) -> HealthCheck:
        """Check memory health"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Determine status
            if memory.percent >= self.thresholds["memory_critical"]:
                status = "unhealthy"
                message = f"Memory usage critically high: {memory.percent:.1f}%"
            elif memory.percent >= self.thresholds["memory_warning"]:
                status = "degraded"
                message = f"Memory usage elevated: {memory.percent:.1f}%"
            else:
                status = "healthy"
                message = f"Memory usage normal: {memory.percent:.1f}%"

            details = {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent": memory.percent,
                "swap_total_gb": swap.total / (1024**3),
                "swap_used_gb": swap.used / (1024**3),
                "swap_percent": swap.percent
            }

            return HealthCheck(
                component="Memory",
                status=status,
                message=message,
                details=details,
                checked_at=datetime.now().isoformat()
            )

        except Exception as e:
            return HealthCheck(
                component="Memory",
                status="unhealthy",
                message=f"Memory check failed: {e}",
                details={},
                checked_at=datetime.now().isoformat()
            )

    def _check_disk(self) -> HealthCheck:
        """Check disk health"""
        try:
            disk = psutil.disk_usage('/')
            io_counters = psutil.disk_io_counters()

            # Determine status
            if disk.percent >= self.thresholds["disk_critical"]:
                status = "unhealthy"
                message = f"Disk usage critically high: {disk.percent:.1f}%"
            elif disk.percent >= self.thresholds["disk_warning"]:
                status = "degraded"
                message = f"Disk usage elevated: {disk.percent:.1f}%"
            else:
                status = "healthy"
                message = f"Disk usage normal: {disk.percent:.1f}%"

            details = {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": disk.percent,
                "read_count": io_counters.read_count if io_counters else None,
                "write_count": io_counters.write_count if io_counters else None
            }

            return HealthCheck(
                component="Disk",
                status=status,
                message=message,
                details=details,
                checked_at=datetime.now().isoformat()
            )

        except Exception as e:
            return HealthCheck(
                component="Disk",
                status="unhealthy",
                message=f"Disk check failed: {e}",
                details={},
                checked_at=datetime.now().isoformat()
            )

    def _check_gpu(self) -> HealthCheck:
        """Check GPU health"""
        try:
            # Try to get GPU info using pynvml
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()

                gpu_info = []
                max_temp = 0

                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                    try:
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        max_temp = max(max_temp, temp)
                    except:
                        temp = None

                    gpu_info.append({
                        "id": i,
                        "name": name.decode('utf-8') if isinstance(name, bytes) else name,
                        "utilization": util.gpu,
                        "temperature": temp
                    })

                # Determine status based on temperature
                if max_temp >= self.thresholds["temperature_critical"]:
                    status = "unhealthy"
                    message = f"GPU temperature critically high: {max_temp:.1f}°C"
                elif max_temp >= self.thresholds["temperature_warning"]:
                    status = "degraded"
                    message = f"GPU temperature elevated: {max_temp:.1f}°C"
                else:
                    status = "healthy"
                    message = f"GPUs healthy, {device_count} device(s) detected"

                details = {
                    "gpu_count": device_count,
                    "gpus": gpu_info
                }

            except (ImportError, Exception):
                # No GPU or unable to get info
                status = "healthy"
                message = "No GPU detected or GPU monitoring unavailable"
                details = {
                    "gpu_count": 0,
                    "gpus": []
                }

            return HealthCheck(
                component="GPU",
                status=status,
                message=message,
                details=details,
                checked_at=datetime.now().isoformat()
            )

        except Exception as e:
            return HealthCheck(
                component="GPU",
                status="degraded",
                message=f"GPU check failed: {e}",
                details={},
                checked_at=datetime.now().isoformat()
            )

    def _check_network(self) -> HealthCheck:
        """Check network connectivity"""
        try:
            # Check if we can resolve DNS
            socket.gethostbyname('google.com')

            # Get network stats
            net_io = psutil.net_io_counters()

            status = "healthy"
            message = "Network connectivity normal"

            details = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errors_in": net_io.errin,
                "errors_out": net_io.errout,
                "drops_in": net_io.dropin,
                "drops_out": net_io.dropout
            }

            # Check for errors
            if net_io.errin > 100 or net_io.errout > 100:
                status = "degraded"
                message = f"Network errors detected (in: {net_io.errin}, out: {net_io.errout})"

            return HealthCheck(
                component="Network",
                status=status,
                message=message,
                details=details,
                checked_at=datetime.now().isoformat()
            )

        except Exception as e:
            return HealthCheck(
                component="Network",
                status="unhealthy",
                message=f"Network connectivity issues: {e}",
                details={},
                checked_at=datetime.now().isoformat()
            )

    def _check_processes(self) -> HealthCheck:
        """Check system processes"""
        try:
            process_count = len(psutil.pids())
            zombie_count = 0

            # Count zombie processes
            for proc in psutil.process_iter(['status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombie_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Determine status
            if zombie_count > 10:
                status = "degraded"
                message = f"High number of zombie processes: {zombie_count}"
            else:
                status = "healthy"
                message = f"Process count normal: {process_count} processes"

            details = {
                "total_processes": process_count,
                "zombie_processes": zombie_count
            }

            return HealthCheck(
                component="Processes",
                status=status,
                message=message,
                details=details,
                checked_at=datetime.now().isoformat()
            )

        except Exception as e:
            return HealthCheck(
                component="Processes",
                status="degraded",
                message=f"Process check failed: {e}",
                details={},
                checked_at=datetime.now().isoformat()
            )

    def get_health_dict(self) -> Dict:
        """Get health check results as dictionary for JSON serialization"""
        health = self.check_health()
        return {
            "status": health.status,
            "checks": [asdict(c) for c in health.checks],
            "summary": health.summary,
            "timestamp": health.timestamp
        }


if __name__ == "__main__":
    # Test health checker
    checker = HealthChecker()

    print("System Health Check")
    print("=" * 50)

    health = checker.check_health()
    print(f"\nOverall Status: {health.status.upper()}")
    print(f"Time: {health.timestamp}")

    print(f"\nSummary:")
    print(f"  Total Checks: {health.summary['total_checks']}")
    print(f"  Healthy: {health.summary['healthy']}")
    print(f"  Degraded: {health.summary['degraded']}")
    print(f"  Unhealthy: {health.summary['unhealthy']}")

    print(f"\nDetailed Results:")
    for check in health.checks:
        status_symbol = {
            "healthy": "✓",
            "degraded": "⚠",
            "unhealthy": "✗"
        }.get(check.status, "?")

        print(f"\n  [{status_symbol}] {check.component}: {check.status.upper()}")
        print(f"      {check.message}")
