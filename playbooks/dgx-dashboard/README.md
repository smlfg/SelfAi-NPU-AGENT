# DGX Dashboard Playbook

This playbook contains scripts and configuration for deploying and managing the System Dashboard & Monitoring system.

## Overview

The DGX Dashboard provides:
- Real-time GPU monitoring and metrics
- JupyterLab session orchestration
- Resource allocation management
- System health checks and diagnostics

## Quick Start

```bash
# 1. Install dependencies
bash playbooks/dgx-dashboard/install.sh

# 2. Start the dashboard server
bash playbooks/dgx-dashboard/start.sh

# 3. Access the dashboard
open http://localhost:11000/api/status
```

## Components

- **GPU Monitor**: Tracks GPU utilization, memory, temperature, and power
- **Jupyter Orchestrator**: Manages JupyterLab instances with resource constraints
- **Resource Allocator**: Distributes compute resources across users
- **Health Checker**: Performs comprehensive system health checks

## API Endpoints

### Health & Status
- `GET /api/health` - System health check
- `GET /api/status` - API status and version

### GPU Monitoring
- `GET /api/gpu` - Get all GPU metrics
- `GET /api/gpu/{gpu_id}` - Get specific GPU metrics

### JupyterLab
- `GET /api/jupyter` - List all sessions
- `POST /api/jupyter/spawn` - Spawn new session
- `GET /api/jupyter/{session_id}` - Get session info
- `DELETE /api/jupyter/{session_id}` - Stop session

### Resource Allocation
- `GET /api/resources` - Get capacity and utilization
- `POST /api/resources/allocate` - Request resources
- `DELETE /api/resources/{allocation_id}` - Release resources

## Configuration

Edit `playbooks/dgx-dashboard/config.env` to customize:

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

## Management Scripts

- `start.sh` - Start the dashboard server
- `stop.sh` - Stop the dashboard server
- `restart.sh` - Restart the dashboard server
- `status.sh` - Check server status
- `install.sh` - Install dependencies

## Monitoring

Check server logs:
```bash
tail -f playbooks/dgx-dashboard/logs/dashboard.log
```

View system health:
```bash
curl http://localhost:11000/api/health | jq
```

## Troubleshooting

### Port already in use
```bash
# Find process using port 11000
lsof -i :11000
# Kill the process
kill -9 <PID>
```

### GPU monitoring not working
```bash
# Install pynvml for NVIDIA GPUs
pip install pynvml

# Test GPU access
nvidia-smi
```

### JupyterLab not spawning
```bash
# Ensure Jupyter is installed
pip install jupyterlab

# Check available ports
netstat -tuln | grep 8888
```

## Security Notes

- The API runs on all interfaces (0.0.0.0) by default
- Consider adding authentication for production use
- Use firewall rules to restrict access
- JupyterLab tokens are generated automatically

## Support

For issues or questions, see the main project documentation.
