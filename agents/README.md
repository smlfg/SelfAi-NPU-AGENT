# DGX Spark Playbooks - Agents

This directory contains all agent playbooks for the SelfAi NPU Agent project. Each agent is a self-contained service with its own Docker configuration, conforming to the shared interface standards.

## Directory Structure

```
agents/
├── agent2_dashboard/          # System Dashboard & Monitoring
│   ├── playbook.yaml          # Agent configuration
│   ├── Dockerfile            # Docker image definition
│   ├── build.sh              # Build script
│   └── deploy.sh             # Deployment script
├── agent1_infra/              # (Future) Infrastructure Management
├── agent3_xxx/                # (Future) Other agents
└── README.md                  # This file
```

## Shared Standards

All agents conform to the shared standards defined in `shared/`:

### 1. Configuration Schema (`shared/config_schema.yaml`)

Every agent must have a `playbook.yaml` file following this structure:

```yaml
playbook:
  name: "Agent Name"
  agent_id: "agentN_name"
  version: "X.Y.Z"
  description: "Brief description"

  dependencies: [...]           # Python packages
  system_dependencies: [...]    # System packages
  ports: [...]                 # Exposed ports
  volumes: [...]               # Volume mounts

  resources:
    gpu_required: bool
    gpu_count: int
    memory_gb: int
    cpu_cores: int

  health_check:
    endpoint: "/api/health"
    interval_seconds: 30
    timeout_seconds: 10
    retries: 3
```

### 2. Docker Base Image (`shared/base.Dockerfile`)

All agents extend the shared base image:

```dockerfile
FROM selfai-base:latest
# Agent-specific configuration
```

The base image includes:
- NVIDIA PyTorch with CUDA 12.4
- Common Python dependencies
- System monitoring tools
- Shared utilities

### 3. Health Check API (`shared/health_check.py`)

All agents must implement a health check endpoint at `/api/health`:

```python
from shared.health_check import HealthChecker

# Service implements /api/health endpoint
# Returns: {"status": "ok", "data": {...}}
```

## Agent 2: System Dashboard & Monitoring

**Status**: ✅ Production Ready

### Overview

Web UI and API for GPU monitoring, JupyterLab orchestration, resource allocation, and system health checks.

### Quick Start

```bash
# Build
cd agents/agent2_dashboard
bash build.sh

# Deploy
bash deploy.sh

# Or use docker-compose
cd ../..
docker-compose up -d agent2_dashboard

# Check status
curl http://localhost:11000/api/status
```

### Configuration

- **Port**: 11000
- **GPU Required**: Yes (for monitoring)
- **Resources**: 8GB RAM, 4 CPU cores
- **Health Check**: `/api/health`

### API Endpoints

- `GET /api/health` - Health check
- `GET /api/status` - Service status
- `GET /api/gpu` - GPU metrics
- `GET /api/jupyter` - JupyterLab sessions
- `GET /api/resources` - Resource allocation

### Documentation

See `AGENT2_DASHBOARD.md` for complete documentation.

## Creating a New Agent

To create a new agent (e.g., Agent 3):

### 1. Create Agent Directory

```bash
mkdir -p agents/agent3_name
cd agents/agent3_name
```

### 2. Create `playbook.yaml`

```yaml
playbook:
  name: "Agent 3 Name"
  agent_id: "agent3_name"
  version: "1.0.0"
  description: "Agent description"

  dependencies:
    - "package1>=1.0.0"

  ports:
    - 12000

  resources:
    gpu_required: true
    memory_gb: 16
    cpu_cores: 8

  health_check:
    endpoint: "/api/health"
```

### 3. Create `Dockerfile`

```dockerfile
FROM selfai-base:latest

LABEL agent_id="agent3_name"
LABEL version="1.0.0"

# Install agent-specific dependencies
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

# Copy agent code
COPY agent3_code/ /app/agents/agent3_name/

# Set environment
ENV AGENT_PORT=12000

# Expose port
EXPOSE 12000

# Health check
HEALTHCHECK CMD python /app/shared/health_check.py

# Run
CMD ["python", "main.py"]
```

### 4. Create Build Script

```bash
#!/bin/bash
# agents/agent3_name/build.sh

docker build -f shared/base.Dockerfile -t selfai-base:latest .
docker build -f agents/agent3_name/Dockerfile -t selfai/agent3_name:1.0.0 .
```

### 5. Create Deploy Script

```bash
#!/bin/bash
# agents/agent3_name/deploy.sh

bash agents/agent3_name/build.sh
docker-compose up -d agent3_name
```

### 6. Add to `docker-compose.yml`

```yaml
services:
  agent3_name:
    build:
      context: .
      dockerfile: agents/agent3_name/Dockerfile
    container_name: agent3_name
    ports:
      - "12000:12000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    networks:
      - selfai_network
```

### 7. Implement Health Check

Ensure your agent implements a `/api/health` endpoint:

```python
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "data": {
            "status": "healthy",
            "checks": [...]
        }
    })
```

### 8. Add Integration Tests

Create `tests/integration/test_agent3_name.py`:

```python
import pytest
from shared.health_check import check_service

def test_agent3_health():
    assert check_service(port=12000, endpoint="/api/health")
```

## Testing

### Run All Integration Tests

```bash
# Install test dependencies
pip install pytest requests

# Run tests
pytest tests/integration/ -v

# Run specific agent tests
pytest tests/integration/test_agent2_dashboard.py -v
```

### Test Health Checks

```bash
# Using Python
python -c "from shared.health_check import check_service; print(check_service(11000))"

# Using curl
curl http://localhost:11000/api/health
```

## Deployment

### Local Development

```bash
# Start all agents
docker-compose up -d

# Start specific agent
docker-compose up -d agent2_dashboard

# View logs
docker-compose logs -f agent2_dashboard

# Stop agents
docker-compose down
```

### Production Deployment

1. **Build images**:
   ```bash
   bash agents/agent2_dashboard/build.sh
   ```

2. **Tag for registry**:
   ```bash
   docker tag selfai/agent2_dashboard:1.0.0 registry.example.com/selfai/agent2_dashboard:1.0.0
   ```

3. **Push to registry**:
   ```bash
   docker push registry.example.com/selfai/agent2_dashboard:1.0.0
   ```

4. **Deploy with compose**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Monitoring

### Check Agent Health

```bash
# All agents
for port in 11000 12000 13000; do
    curl -s http://localhost:$port/api/health | jq .status
done

# Specific agent
curl http://localhost:11000/api/health | jq
```

### View Logs

```bash
# Real-time logs
docker-compose logs -f agent2_dashboard

# Last 100 lines
docker-compose logs --tail=100 agent2_dashboard

# Logs from all agents
docker-compose logs
```

### Resource Usage

```bash
# Container stats
docker stats

# GPU usage
nvidia-smi

# Via dashboard API (Agent 2)
curl http://localhost:11000/api/gpu | jq
```

## Troubleshooting

### Agent Won't Start

```bash
# Check logs
docker-compose logs agent2_dashboard

# Check configuration
docker-compose config

# Validate playbook
python -c "from shared.utils import validate_config, load_playbook_config; \
    config = load_playbook_config('agents/agent2_dashboard/playbook.yaml'); \
    print(validate_config(config))"
```

### Health Check Failing

```bash
# Manual health check
python shared/health_check.py

# Check from inside container
docker exec agent2_dashboard python /app/shared/health_check.py

# View health status
docker inspect --format='{{.State.Health.Status}}' agent2_dashboard
```

### Port Conflicts

```bash
# Find process using port
lsof -i :11000

# Kill process
kill -9 <PID>

# Or change port in playbook.yaml
```

### GPU Not Accessible

```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi

# Check docker-compose GPU config
docker-compose config | grep -A 5 "devices:"

# Verify GPU access in container
docker exec agent2_dashboard nvidia-smi
```

## Best Practices

1. **Configuration**: Always use `playbook.yaml` for configuration
2. **Logging**: Use shared logging utilities from `shared/utils/logging_utils.py`
3. **Health Checks**: Implement comprehensive health checks
4. **Testing**: Write integration tests for all endpoints
5. **Documentation**: Update README when adding features
6. **Versioning**: Follow semantic versioning (MAJOR.MINOR.PATCH)
7. **Resource Limits**: Set appropriate resource limits in playbook
8. **Error Handling**: Return proper HTTP status codes and error messages

## Agent Checklist

When creating a new agent, ensure:

- [ ] `playbook.yaml` conforms to schema
- [ ] Dockerfile extends `selfai-base:latest`
- [ ] Health check endpoint implemented
- [ ] Build and deploy scripts created
- [ ] Added to `docker-compose.yml`
- [ ] Integration tests written
- [ ] Documentation updated
- [ ] Resource limits set appropriately
- [ ] Environment variables documented
- [ ] Logging configured

## Support

For issues or questions:

1. Check agent-specific documentation
2. Review shared standards in `shared/`
3. Check integration tests for examples
4. Consult main project documentation

## License

See main project LICENSE file.
