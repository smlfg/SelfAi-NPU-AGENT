"""
Agent 2: System Dashboard & Monitoring - Interface Output
Provides API endpoint definitions for the dashboard and monitoring system.
"""

# Dashboard API Endpoints
DASHBOARD_API = {
    # Health & Status
    "health": "http://localhost:11000/api/health",
    "status": "http://localhost:11000/api/status",

    # GPU Monitoring
    "gpu_stats": "http://localhost:11000/api/gpu",
    "gpu_by_id": "http://localhost:11000/api/gpu/{gpu_id}",

    # JupyterLab Orchestration
    "jupyter_list": "http://localhost:11000/api/jupyter",
    "jupyter_spawn": "http://localhost:11000/api/jupyter/spawn",
    "jupyter_session": "http://localhost:11000/api/jupyter/{session_id}",

    # Resource Allocation
    "resources": "http://localhost:11000/api/resources",
    "resources_allocate": "http://localhost:11000/api/resources/allocate",
    "resources_release": "http://localhost:11000/api/resources/{allocation_id}",
}


# Component Import Paths
COMPONENTS = {
    "gpu_monitor": "selfai.dashboard.gpu_monitor.GPUMonitor",
    "jupyter_orchestrator": "selfai.dashboard.jupyter_orchestrator.JupyterOrchestrator",
    "resource_allocator": "selfai.dashboard.resource_allocator.ResourceAllocator",
    "health_checker": "selfai.dashboard.health_checker.HealthChecker",
    "dashboard_server": "selfai.dashboard.dashboard_server.DashboardServer",
}


# Usage Examples
USAGE_EXAMPLES = {
    "start_server": """
# Start the dashboard server
python -m selfai.dashboard.dashboard_server --host 0.0.0.0 --port 11000
""",

    "check_health": """
# Check system health
curl http://localhost:11000/api/health
""",

    "get_gpu_stats": """
# Get GPU statistics
curl http://localhost:11000/api/gpu
""",

    "spawn_jupyter": """
# Spawn a JupyterLab session
curl -X POST http://localhost:11000/api/jupyter/spawn \\
  -H "Content-Type: application/json" \\
  -d '{
    "user": "researcher1",
    "gpu_ids": [0, 1],
    "memory_limit_gb": 32,
    "cpu_limit": 8
  }'
""",

    "allocate_resources": """
# Request resource allocation
curl -X POST http://localhost:11000/api/resources/allocate \\
  -H "Content-Type: application/json" \\
  -d '{
    "user": "researcher1",
    "gpu_count": 2,
    "memory_gb": 32,
    "cpu_cores": 8,
    "priority": 7
  }'
""",

    "python_client": """
# Python client example
import requests

# Get GPU stats
response = requests.get('http://localhost:11000/api/gpu')
gpu_data = response.json()

# Spawn Jupyter session
response = requests.post(
    'http://localhost:11000/api/jupyter/spawn',
    json={
        'user': 'researcher1',
        'gpu_ids': [0],
        'memory_limit_gb': 16,
        'cpu_limit': 4
    }
)
session_data = response.json()
jupyter_url = session_data['data']['url']
"""
}


def print_api_info():
    """Print API information"""
    print("=" * 60)
    print("Agent 2: System Dashboard & Monitoring")
    print("=" * 60)

    print("\n📊 Dashboard API Endpoints:")
    print("-" * 60)
    for name, url in DASHBOARD_API.items():
        print(f"  {name:20} -> {url}")

    print("\n🔧 Components:")
    print("-" * 60)
    for name, path in COMPONENTS.items():
        print(f"  {name:20} -> {path}")

    print("\n💡 Usage Examples:")
    print("-" * 60)
    for name, example in USAGE_EXAMPLES.items():
        print(f"\n{name}:")
        print(example)


if __name__ == "__main__":
    print_api_info()
