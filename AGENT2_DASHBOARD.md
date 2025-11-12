# Agent 2: System Dashboard & Monitoring

## Overview

Agent 2 provides comprehensive system dashboard and monitoring capabilities for AI/ML compute infrastructure, including GPU monitoring, JupyterLab orchestration, resource allocation, and system health checks.

## Components

### 1. GPU Monitor (`selfai/dashboard/gpu_monitor.py`)

Real-time GPU metrics collection and monitoring.

**Features:**
- GPU utilization tracking
- Memory usage monitoring
- Temperature monitoring
- Power consumption tracking
- Support for multiple GPU types:
  - NVIDIA GPUs (via pynvml)
  - AMD GPUs (via pyrsmi)
  - Qualcomm NPUs (Snapdragon X Elite)
- Mock metrics for development/testing

**Usage:**
```python
from selfai.dashboard import GPUMonitor

monitor = GPUMonitor()
metrics = monitor.get_gpu_metrics()

for gpu in metrics:
    print(f"GPU {gpu.gpu_id}: {gpu.utilization}% utilization")
```

### 2. JupyterLab Orchestrator (`selfai/dashboard/jupyter_orchestrator.py`)

Manages JupyterLab instance spawning and lifecycle.

**Features:**
- Spawn JupyterLab instances with resource constraints
- Automatic port allocation
- GPU assignment to sessions
- Memory and CPU limits
- Session tracking and management
- Automatic cleanup of stopped sessions

**Usage:**
```python
from selfai.dashboard import JupyterOrchestrator

orchestrator = JupyterOrchestrator()

# Spawn a session
session = orchestrator.spawn_jupyter(
    user="researcher1",
    gpu_ids=[0, 1],
    memory_limit_gb=32,
    cpu_limit=8
)

# Get session URL
url = orchestrator.get_session_url(session.session_id)
print(f"JupyterLab URL: {url}")
```

### 3. Resource Allocator (`selfai/dashboard/resource_allocator.py`)

Manages compute resource allocation across users.

**Features:**
- GPU allocation with tracking
- Memory management
- CPU core allocation
- Priority-based resource distribution
- Resource reservation and release
- Utilization tracking
- Pending request queue

**Usage:**
```python
from selfai.dashboard import ResourceAllocator

allocator = ResourceAllocator(
    total_gpus=4,
    total_memory_gb=128,
    total_cpu_cores=32
)

# Request resources
allocation = allocator.request_resources(
    user="researcher1",
    gpu_count=2,
    memory_gb=32,
    cpu_cores=8,
    priority=7
)

# Release resources when done
allocator.release_resources(allocation.allocation_id)
```

### 4. Health Checker (`selfai/dashboard/health_checker.py`)

Comprehensive system health monitoring and diagnostics.

**Features:**
- CPU health monitoring
- Memory usage checks
- Disk space monitoring
- GPU temperature monitoring
- Network connectivity tests
- Process monitoring
- Configurable thresholds

**Usage:**
```python
from selfai.dashboard import HealthChecker

checker = HealthChecker()
health = checker.check_health()

print(f"Overall Status: {health.status}")
for check in health.checks:
    print(f"{check.component}: {check.status} - {check.message}")
```

### 5. Dashboard Server (`selfai/dashboard/dashboard_server.py`)

Web server providing RESTful API for all monitoring functions.

**Features:**
- Flask-based web server
- RESTful API endpoints
- CORS enabled
- JSON responses
- Error handling
- Runs on port 11000

**Usage:**
```bash
# Start the server
python -m selfai.dashboard.dashboard_server --host 0.0.0.0 --port 11000

# Or use the playbook
bash playbooks/dgx-dashboard/start.sh
```

## API Endpoints

### Health & Status

#### GET `/api/health`
System health check with detailed diagnostics.

**Response:**
```json
{
  "status": "ok",
  "data": {
    "status": "healthy",
    "checks": [...],
    "summary": {
      "total_checks": 6,
      "healthy": 5,
      "degraded": 1,
      "unhealthy": 0
    }
  }
}
```

#### GET `/api/status`
API status and version information.

### GPU Monitoring

#### GET `/api/gpu`
Get metrics for all GPUs.

**Response:**
```json
{
  "status": "ok",
  "data": {
    "gpus": [
      {
        "gpu_id": 0,
        "name": "NVIDIA A100",
        "utilization": 45.5,
        "memory_used": 8192,
        "memory_total": 40960,
        "memory_percent": 20.0,
        "temperature": 65.0,
        "power_draw": 150.5
      }
    ],
    "system": {
      "cpu_percent": 35.2,
      "memory_total_gb": 128.0
    }
  }
}
```

#### GET `/api/gpu/{gpu_id}`
Get metrics for a specific GPU.

### JupyterLab Orchestration

#### GET `/api/jupyter`
List all JupyterLab sessions.

**Query Parameters:**
- `user` (optional): Filter by username

#### POST `/api/jupyter/spawn`
Spawn a new JupyterLab session.

**Request Body:**
```json
{
  "user": "researcher1",
  "gpu_ids": [0, 1],
  "memory_limit_gb": 32,
  "cpu_limit": 8
}
```

**Response:**
```json
{
  "status": "ok",
  "data": {
    "session_id": "researcher1_20250112_143022",
    "url": "http://localhost:8888/?token=abc123...",
    "port": 8888,
    "gpu_ids": [0, 1]
  }
}
```

#### GET `/api/jupyter/{session_id}`
Get information about a specific session.

#### DELETE `/api/jupyter/{session_id}`
Stop a JupyterLab session.

### Resource Allocation

#### GET `/api/resources`
Get resource capacity and utilization.

**Response:**
```json
{
  "status": "ok",
  "data": {
    "capacity": {
      "total_gpus": 4,
      "available_gpus": [2, 3],
      "total_memory_gb": 128,
      "available_memory_gb": 64
    },
    "utilization": {
      "gpu_utilization_percent": 50.0,
      "memory_utilization_percent": 50.0
    }
  }
}
```

#### POST `/api/resources/allocate`
Request resource allocation.

**Request Body:**
```json
{
  "user": "researcher1",
  "gpu_count": 2,
  "memory_gb": 32,
  "cpu_cores": 8,
  "priority": 7
}
```

#### DELETE `/api/resources/{allocation_id}`
Release allocated resources.

## Installation

### Quick Start

```bash
# Install dependencies
bash playbooks/dgx-dashboard/install.sh

# Start the server
bash playbooks/dgx-dashboard/start.sh
```

### Manual Installation

```bash
# Install dashboard dependencies
pip install -r requirements-dashboard.txt

# Optional: Install GPU monitoring
pip install pynvml  # For NVIDIA GPUs

# Optional: Install JupyterLab
pip install jupyterlab
```

## Configuration

Edit `playbooks/dgx-dashboard/config.env`:

```bash
# Server Configuration
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=11000

# Resource Limits
TOTAL_GPUS=4
TOTAL_MEMORY_GB=128
TOTAL_CPU_CORES=32

# JupyterLab Configuration
JUPYTER_BASE_PORT=8888
```

## Usage Examples

### Python Client

```python
import requests

# Check system health
response = requests.get('http://localhost:11000/api/health')
health = response.json()

# Get GPU metrics
response = requests.get('http://localhost:11000/api/gpu')
gpu_data = response.json()

# Spawn JupyterLab session
response = requests.post(
    'http://localhost:11000/api/jupyter/spawn',
    json={
        'user': 'researcher1',
        'gpu_ids': [0],
        'memory_limit_gb': 16,
        'cpu_limit': 4
    }
)
session = response.json()
jupyter_url = session['data']['url']

# Allocate resources
response = requests.post(
    'http://localhost:11000/api/resources/allocate',
    json={
        'user': 'researcher1',
        'gpu_count': 2,
        'memory_gb': 32,
        'cpu_cores': 8,
        'priority': 7
    }
)
allocation = response.json()
```

### cURL Examples

```bash
# Check health
curl http://localhost:11000/api/health | jq

# Get GPU stats
curl http://localhost:11000/api/gpu | jq

# Spawn Jupyter
curl -X POST http://localhost:11000/api/jupyter/spawn \
  -H "Content-Type: application/json" \
  -d '{
    "user": "researcher1",
    "gpu_ids": [0, 1],
    "memory_limit_gb": 32,
    "cpu_limit": 8
  }' | jq

# Get resources
curl http://localhost:11000/api/resources | jq
```

## Management

### Start/Stop/Restart

```bash
# Start
bash playbooks/dgx-dashboard/start.sh

# Stop
bash playbooks/dgx-dashboard/stop.sh

# Restart
bash playbooks/dgx-dashboard/restart.sh

# Check status
bash playbooks/dgx-dashboard/status.sh
```

### Monitoring

```bash
# View logs
tail -f playbooks/dgx-dashboard/logs/dashboard.log

# Check API status
curl http://localhost:11000/api/status

# Monitor GPU usage
watch -n 1 'curl -s http://localhost:11000/api/gpu | jq .data.gpus'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Dashboard Server (Port 11000)              │
│                      Flask REST API                         │
└──────────────┬──────────────────────────────────────────────┘
               │
      ┌────────┼────────┬────────────┬──────────────┐
      │        │        │            │              │
      ▼        ▼        ▼            ▼              ▼
┌──────────┐ ┌────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
│   GPU    │ │Jupyter│ │Resource│ │ Health │ │  Agent   │
│ Monitor  │ │Orchest│ │Allocat │ │Checker │ │  System  │
└──────────┘ └────┘ └──────────┘ └────────┘ └──────────┘
      │         │         │           │            │
      ▼         ▼         ▼           ▼            ▼
┌──────────────────────────────────────────────────────┐
│            Hardware & System Resources               │
│  GPUs │ JupyterLab │ Memory │ CPU │ Disk │ Network │
└──────────────────────────────────────────────────────┘
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 11000
lsof -i :11000

# Kill the process
kill -9 <PID>
```

### GPU Monitoring Not Working

```bash
# Install NVIDIA GPU support
pip install pynvml

# Test GPU access
nvidia-smi

# Check permissions
ls -la /dev/nvidia*
```

### JupyterLab Not Spawning

```bash
# Install JupyterLab
pip install jupyterlab

# Test manually
jupyter lab --version

# Check available ports
netstat -tuln | grep 8888
```

## Security Considerations

- API runs on all interfaces (0.0.0.0) by default
- Consider adding authentication for production use
- Use firewall rules to restrict access
- JupyterLab tokens are generated automatically
- Review resource limits to prevent resource exhaustion

## Integration with SelfAI

The dashboard agent integrates with the main SelfAI system:

1. **Agent Configuration**: Located in `selfai/agents/system_dashboard_monitoring/`
2. **System Prompt**: Defines the agent's role and capabilities
3. **Memory Categories**: Tracks system metrics, GPU data, Jupyter sessions, etc.
4. **Tools**: Can be extended with custom monitoring tools

### Using with SelfAI

```python
# In selfai/selfai.py
from selfai.dashboard import DashboardServer

# Start dashboard alongside main agent
dashboard = DashboardServer(port=11000)
# ... integrate with agent system
```

## Future Enhancements

- [ ] Web UI dashboard with real-time charts
- [ ] Alert system for resource thresholds
- [ ] Email/Slack notifications
- [ ] Historical metrics storage (time-series DB)
- [ ] Multi-node cluster support
- [ ] User authentication and authorization
- [ ] Resource usage billing/accounting
- [ ] Container orchestration (Docker/Kubernetes)
- [ ] Integration with Slurm/PBS job schedulers

## Support

For issues or questions:
1. Check the logs: `tail -f playbooks/dgx-dashboard/logs/dashboard.log`
2. Review the API status: `curl http://localhost:11000/api/status`
3. Consult the main project documentation
4. File an issue on the project repository

## License

See main project LICENSE file.
