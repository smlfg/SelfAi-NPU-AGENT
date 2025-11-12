"""
Resource Allocation Module
Manages compute resource allocation across GPUs, memory, and CPU cores.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import threading


@dataclass
class ResourceRequest:
    """Resource allocation request"""
    request_id: str
    user: str
    gpu_count: int
    memory_gb: int
    cpu_cores: int
    priority: int  # 1-10, higher is more important
    requested_at: str


@dataclass
class ResourceAllocation:
    """Allocated resources"""
    allocation_id: str
    request_id: str
    user: str
    gpu_ids: List[int]
    memory_gb: int
    cpu_cores: int
    allocated_at: str
    status: str  # "active", "released"


@dataclass
class ResourceCapacity:
    """System resource capacity"""
    total_gpus: int
    total_memory_gb: int
    total_cpu_cores: int
    available_gpus: List[int]
    available_memory_gb: int
    available_cpu_cores: int


class ResourceAllocator:
    """
    Resource allocation system for managing compute resources.

    Features:
    - GPU allocation with tracking
    - Memory management
    - CPU core allocation
    - Priority-based allocation
    - Resource reservation and release
    - Utilization tracking
    """

    def __init__(
        self,
        total_gpus: int = 2,
        total_memory_gb: int = 64,
        total_cpu_cores: int = 16
    ):
        self.total_gpus = total_gpus
        self.total_memory_gb = total_memory_gb
        self.total_cpu_cores = total_cpu_cores

        # Available resources
        self.available_gpus = set(range(total_gpus))
        self.available_memory_gb = total_memory_gb
        self.available_cpu_cores = total_cpu_cores

        # Allocations
        self.allocations: Dict[str, ResourceAllocation] = {}
        self.pending_requests: List[ResourceRequest] = []

        # Thread safety
        self.lock = threading.Lock()

    def get_capacity(self) -> ResourceCapacity:
        """Get current resource capacity"""
        with self.lock:
            return ResourceCapacity(
                total_gpus=self.total_gpus,
                total_memory_gb=self.total_memory_gb,
                total_cpu_cores=self.total_cpu_cores,
                available_gpus=sorted(self.available_gpus),
                available_memory_gb=self.available_memory_gb,
                available_cpu_cores=self.available_cpu_cores
            )

    def request_resources(
        self,
        user: str,
        gpu_count: int = 0,
        memory_gb: int = 0,
        cpu_cores: int = 1,
        priority: int = 5
    ) -> Optional[ResourceAllocation]:
        """
        Request resource allocation.

        Args:
            user: Username requesting resources
            gpu_count: Number of GPUs requested
            memory_gb: Amount of memory in GB
            cpu_cores: Number of CPU cores
            priority: Priority level (1-10)

        Returns:
            ResourceAllocation if successful, None if resources unavailable
        """
        with self.lock:
            # Check if resources are available
            if not self._can_allocate(gpu_count, memory_gb, cpu_cores):
                # Add to pending requests
                request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                request = ResourceRequest(
                    request_id=request_id,
                    user=user,
                    gpu_count=gpu_count,
                    memory_gb=memory_gb,
                    cpu_cores=cpu_cores,
                    priority=priority,
                    requested_at=datetime.now().isoformat()
                )
                self.pending_requests.append(request)
                self.pending_requests.sort(key=lambda r: r.priority, reverse=True)
                return None

            # Allocate resources
            return self._allocate(user, gpu_count, memory_gb, cpu_cores)

    def _can_allocate(self, gpu_count: int, memory_gb: int, cpu_cores: int) -> bool:
        """Check if resources can be allocated"""
        return (
            len(self.available_gpus) >= gpu_count and
            self.available_memory_gb >= memory_gb and
            self.available_cpu_cores >= cpu_cores
        )

    def _allocate(
        self,
        user: str,
        gpu_count: int,
        memory_gb: int,
        cpu_cores: int
    ) -> ResourceAllocation:
        """Perform resource allocation"""
        # Allocate GPUs
        allocated_gpus = []
        if gpu_count > 0:
            allocated_gpus = sorted(self.available_gpus)[:gpu_count]
            for gpu_id in allocated_gpus:
                self.available_gpus.remove(gpu_id)

        # Allocate memory and CPU
        self.available_memory_gb -= memory_gb
        self.available_cpu_cores -= cpu_cores

        # Create allocation
        allocation_id = f"alloc_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        allocation = ResourceAllocation(
            allocation_id=allocation_id,
            request_id="",
            user=user,
            gpu_ids=allocated_gpus,
            memory_gb=memory_gb,
            cpu_cores=cpu_cores,
            allocated_at=datetime.now().isoformat(),
            status="active"
        )

        self.allocations[allocation_id] = allocation
        return allocation

    def release_resources(self, allocation_id: str) -> bool:
        """
        Release allocated resources.

        Args:
            allocation_id: ID of allocation to release

        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if allocation_id not in self.allocations:
                return False

            allocation = self.allocations[allocation_id]

            if allocation.status != "active":
                return False

            # Return GPUs
            for gpu_id in allocation.gpu_ids:
                self.available_gpus.add(gpu_id)

            # Return memory and CPU
            self.available_memory_gb += allocation.memory_gb
            self.available_cpu_cores += allocation.cpu_cores

            # Update allocation status
            allocation.status = "released"

            # Process pending requests
            self._process_pending_requests()

            return True

    def _process_pending_requests(self):
        """Process pending resource requests"""
        fulfilled_requests = []

        for request in self.pending_requests:
            if self._can_allocate(
                request.gpu_count,
                request.memory_gb,
                request.cpu_cores
            ):
                allocation = self._allocate(
                    request.user,
                    request.gpu_count,
                    request.memory_gb,
                    request.cpu_cores
                )
                allocation.request_id = request.request_id
                fulfilled_requests.append(request)

        # Remove fulfilled requests
        for request in fulfilled_requests:
            self.pending_requests.remove(request)

    def get_allocation(self, allocation_id: str) -> Optional[ResourceAllocation]:
        """Get allocation by ID"""
        return self.allocations.get(allocation_id)

    def list_allocations(self, user: Optional[str] = None) -> List[ResourceAllocation]:
        """
        List allocations, optionally filtered by user.

        Args:
            user: Filter by username (None for all)

        Returns:
            List of ResourceAllocation objects
        """
        with self.lock:
            allocations = [a for a in self.allocations.values() if a.status == "active"]
            if user:
                allocations = [a for a in allocations if a.user == user]
            return allocations

    def get_utilization(self) -> Dict:
        """Get resource utilization statistics"""
        with self.lock:
            gpu_util = ((self.total_gpus - len(self.available_gpus)) / self.total_gpus * 100
                       if self.total_gpus > 0 else 0)
            memory_util = ((self.total_memory_gb - self.available_memory_gb) / self.total_memory_gb * 100
                          if self.total_memory_gb > 0 else 0)
            cpu_util = ((self.total_cpu_cores - self.available_cpu_cores) / self.total_cpu_cores * 100
                       if self.total_cpu_cores > 0 else 0)

            return {
                "gpu_utilization_percent": gpu_util,
                "memory_utilization_percent": memory_util,
                "cpu_utilization_percent": cpu_util,
                "active_allocations": len([a for a in self.allocations.values() if a.status == "active"]),
                "pending_requests": len(self.pending_requests),
                "timestamp": datetime.now().isoformat()
            }

    def get_allocations_dict(self) -> List[Dict]:
        """Get all allocations as dictionary format for JSON serialization"""
        with self.lock:
            return [asdict(a) for a in self.allocations.values() if a.status == "active"]


if __name__ == "__main__":
    # Test resource allocator
    allocator = ResourceAllocator(total_gpus=4, total_memory_gb=64, total_cpu_cores=16)

    print("Initial capacity:")
    capacity = allocator.get_capacity()
    print(f"  GPUs: {len(capacity.available_gpus)}/{capacity.total_gpus}")
    print(f"  Memory: {capacity.available_memory_gb}/{capacity.total_memory_gb} GB")
    print(f"  CPU: {capacity.available_cpu_cores}/{capacity.total_cpu_cores} cores")

    # Request resources
    print("\nRequesting resources for user1...")
    alloc1 = allocator.request_resources(
        user="user1",
        gpu_count=2,
        memory_gb=16,
        cpu_cores=4
    )
    if alloc1:
        print(f"  Allocated: {alloc1.allocation_id}")
        print(f"    GPUs: {alloc1.gpu_ids}")
        print(f"    Memory: {alloc1.memory_gb} GB")
        print(f"    CPU: {alloc1.cpu_cores} cores")

    print("\nCurrent utilization:")
    util = allocator.get_utilization()
    for key, value in util.items():
        print(f"  {key}: {value}")

    # Release resources
    if alloc1:
        print(f"\nReleasing allocation {alloc1.allocation_id}...")
        allocator.release_resources(alloc1.allocation_id)

    print("\nFinal capacity:")
    capacity = allocator.get_capacity()
    print(f"  GPUs: {len(capacity.available_gpus)}/{capacity.total_gpus}")
    print(f"  Memory: {capacity.available_memory_gb}/{capacity.total_memory_gb} GB")
    print(f"  CPU: {capacity.available_cpu_cores}/{capacity.total_cpu_cores} cores")
