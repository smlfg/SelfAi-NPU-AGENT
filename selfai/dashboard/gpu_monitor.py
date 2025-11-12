"""
GPU Monitoring Module
Collects and provides GPU metrics including utilization, memory, temperature, and power.
"""

import psutil
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class GPUMetrics:
    """GPU metrics data structure"""
    gpu_id: int
    name: str
    utilization: float  # Percentage
    memory_used: int  # MB
    memory_total: int  # MB
    memory_percent: float
    temperature: Optional[float]  # Celsius
    power_draw: Optional[float]  # Watts
    timestamp: str


class GPUMonitor:
    """
    GPU monitoring system that collects real-time metrics.

    Note: This implementation provides a framework. For actual GPU monitoring,
    you would need to install and configure:
    - NVIDIA GPUs: nvidia-smi, pynvml
    - AMD GPUs: rocm-smi, pyrsmi
    - Qualcomm NPUs: QNN SDK tools
    """

    def __init__(self):
        self.gpu_available = False
        self.gpu_type = None
        self._detect_gpu()

    def _detect_gpu(self):
        """Detect available GPU/NPU hardware"""
        # Try NVIDIA
        try:
            import pynvml
            pynvml.nvmlInit()
            self.gpu_available = True
            self.gpu_type = "nvidia"
            return
        except (ImportError, Exception):
            pass

        # Try AMD
        try:
            import pyrsmi
            pyrsmi.rocm_smi_lib.rsmi_init(0)
            self.gpu_available = True
            self.gpu_type = "amd"
            return
        except (ImportError, Exception):
            pass

        # Check for Qualcomm NPU (Snapdragon X Elite)
        try:
            # This is a placeholder - actual NPU detection would use QNN SDK
            import platform
            if 'arm' in platform.machine().lower():
                self.gpu_available = True
                self.gpu_type = "qualcomm_npu"
                return
        except Exception:
            pass

    def get_gpu_metrics(self) -> List[GPUMetrics]:
        """
        Collect current GPU metrics from all available GPUs.

        Returns:
            List of GPUMetrics objects
        """
        if not self.gpu_available:
            return self._get_mock_metrics()

        if self.gpu_type == "nvidia":
            return self._get_nvidia_metrics()
        elif self.gpu_type == "amd":
            return self._get_amd_metrics()
        elif self.gpu_type == "qualcomm_npu":
            return self._get_qualcomm_npu_metrics()

        return []

    def _get_nvidia_metrics(self) -> List[GPUMetrics]:
        """Get metrics from NVIDIA GPUs using pynvml"""
        try:
            import pynvml
            pynvml.nvmlInit()

            device_count = pynvml.nvmlDeviceGetCount()
            metrics = []

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)

                # Get utilization
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                # Get memory
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                # Get temperature
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    temp = None

                # Get power draw
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert mW to W
                except:
                    power = None

                metrics.append(GPUMetrics(
                    gpu_id=i,
                    name=name.decode('utf-8') if isinstance(name, bytes) else name,
                    utilization=util.gpu,
                    memory_used=mem_info.used // (1024 * 1024),
                    memory_total=mem_info.total // (1024 * 1024),
                    memory_percent=(mem_info.used / mem_info.total) * 100,
                    temperature=temp,
                    power_draw=power,
                    timestamp=datetime.now().isoformat()
                ))

            return metrics

        except Exception as e:
            print(f"Error getting NVIDIA GPU metrics: {e}")
            return []

    def _get_amd_metrics(self) -> List[GPUMetrics]:
        """Get metrics from AMD GPUs using pyrsmi"""
        try:
            import pyrsmi
            # Placeholder for AMD ROCm GPU metrics
            # Implementation would use pyrsmi library
            return []
        except Exception as e:
            print(f"Error getting AMD GPU metrics: {e}")
            return []

    def _get_qualcomm_npu_metrics(self) -> List[GPUMetrics]:
        """Get metrics from Qualcomm NPU"""
        # Placeholder for Qualcomm NPU metrics
        # Actual implementation would interface with QNN SDK
        return [GPUMetrics(
            gpu_id=0,
            name="Qualcomm Hexagon NPU",
            utilization=0.0,
            memory_used=0,
            memory_total=8192,
            memory_percent=0.0,
            temperature=None,
            power_draw=None,
            timestamp=datetime.now().isoformat()
        )]

    def _get_mock_metrics(self) -> List[GPUMetrics]:
        """Return mock metrics for development/testing"""
        import random

        return [
            GPUMetrics(
                gpu_id=0,
                name="Mock GPU 0",
                utilization=random.uniform(20, 80),
                memory_used=random.randint(2000, 8000),
                memory_total=11264,
                memory_percent=random.uniform(20, 70),
                temperature=random.uniform(55, 75),
                power_draw=random.uniform(100, 250),
                timestamp=datetime.now().isoformat()
            ),
            GPUMetrics(
                gpu_id=1,
                name="Mock GPU 1",
                utilization=random.uniform(20, 80),
                memory_used=random.randint(2000, 8000),
                memory_total=11264,
                memory_percent=random.uniform(20, 70),
                temperature=random.uniform(55, 75),
                power_draw=random.uniform(100, 250),
                timestamp=datetime.now().isoformat()
            )
        ]

    def get_metrics_dict(self) -> List[Dict]:
        """Get GPU metrics as dictionary format for JSON serialization"""
        metrics = self.get_gpu_metrics()
        return [asdict(m) for m in metrics]

    def get_system_info(self) -> Dict:
        """Get general system information"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        return {
            "cpu_percent": cpu_percent,
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": memory.total / (1024**3),
            "memory_used_gb": memory.used / (1024**3),
            "memory_percent": memory.percent,
            "gpu_available": self.gpu_available,
            "gpu_type": self.gpu_type,
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Test GPU monitor
    monitor = GPUMonitor()
    print("GPU Available:", monitor.gpu_available)
    print("GPU Type:", monitor.gpu_type)
    print("\nGPU Metrics:")
    for gpu in monitor.get_gpu_metrics():
        print(f"  GPU {gpu.gpu_id}: {gpu.name}")
        print(f"    Utilization: {gpu.utilization:.1f}%")
        print(f"    Memory: {gpu.memory_used}/{gpu.memory_total} MB ({gpu.memory_percent:.1f}%)")
        if gpu.temperature:
            print(f"    Temperature: {gpu.temperature:.1f}°C")
        if gpu.power_draw:
            print(f"    Power: {gpu.power_draw:.1f}W")

    print("\nSystem Info:")
    sys_info = monitor.get_system_info()
    for key, value in sys_info.items():
        print(f"  {key}: {value}")
