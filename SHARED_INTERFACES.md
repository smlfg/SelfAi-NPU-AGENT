# Shared Interfaces - Complete Integration Guide

This document provides a complete overview of the shared interfaces system and how Agent 2 integrates with it.

## System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    Docker Compose Layer                         │
│          (Orchestration & Multi-Agent Management)              │
└──────────────┬─────────────────────────────────────────────────┘
               │
      ┌────────┼────────┬────────────┬──────────────┐
      │        │        │            │              │
      ▼        ▼        ▼            ▼              ▼
┌──────────┐ ┌────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
│ Agent 1  │ │Agent2│ │ Agent 3 │ │Agent 4 │ │ Agent N  │
│ Infra    │ │Dashbd│ │ Storage │ │Network │ │          │
│ :10000   │ │:11000│ │ :12000  │ │:13000  │ │ :1N000   │
└──────────┘ └────┘ └──────────┘ └────────┘ └──────────┘
      │         │         │           │            │
      └─────────┴─────────┴───────────┴────────────┘
                         │
      ┌──────────────────┴──────────────────┐
      │                                     │
      ▼                                     ▼
┌─────────────────┐              ┌─────────────────┐
│ Shared          │              │  Shared         │
│ Components      │              │  Standards      │
├─────────────────┤              ├─────────────────┤
│ • base.Dockerfile│              │ • Config Schema │
│ • health_check.py│              │ • Health API    │
│ • utils/        │              │ • Port Ranges   │
│ • metrics       │              │ • Versioning    │
└─────────────────┘              └─────────────────┘
                         │
                    ┌────▼─────┐
                    │  Base    │
                    │  Image   │
                    │ (PyTorch)│
                    └──────────┘
```

## Component Overview

### 1. Shared Infrastructure (`shared/`)

| Component | Purpose | Used By |
|-----------|---------|---------|
| `base.Dockerfile` | Base Docker image | All agents |
| `config_schema.yaml` | Configuration standard | All agents |
| `health_check.py` | Health monitoring | All agents |
| `utils/config_loader.py` | Config validation | All agents |
| `utils/logging_utils.py` | Standardized logging | All agents |
| `utils/metrics.py` | Metrics collection | All agents |

### 2. Agent-Specific Files

| File | Purpose | Location |
|------|---------|----------|
| `playbook.yaml` | Agent configuration | `agents/agentN_name/` |
| `Dockerfile` | Agent container image | `agents/agentN_name/` |
| `build.sh` | Build script | `agents/agentN_name/` |
| `deploy.sh` | Deployment script | `agents/agentN_name/` |
| Source code | Agent implementation | `selfai/dashboard/` etc. |

### 3. Orchestration Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Multi-agent orchestration |
| `.env` | Environment variables |
| `tests/conftest.py` | Test configuration |
| `tests/integration/` | Integration tests |

## Agent 2 Integration Example

### 1. Configuration (`agents/agent2_dashboard/playbook.yaml`)

```yaml
playbook:
  name: "DGX Dashboard"
  agent_id: "agent2_dashboard"
  version: "1.0.0"
  description: "Web UI + GPU Monitoring"

  dependencies:
    - "flask>=2.3.0"
    - "flask-cors>=4.0.0"
    - "psutil>=5.9.0"

  ports:
    - 11000

  resources:
    gpu_required: true
    gpu_count: 0
    memory_gb: 8
    cpu_cores: 4

  health_check:
    endpoint: "/api/health"
    interval_seconds: 30
    timeout_seconds: 10
    retries: 3

  environment:
    DASHBOARD_HOST: "0.0.0.0"
    DASHBOARD_PORT: "11000"
    LOG_LEVEL: "INFO"
```

### 2. Dockerfile (`agents/agent2_dashboard/Dockerfile`)

```dockerfile
# Extend shared base image
FROM selfai-base:latest

LABEL agent_id="agent2_dashboard"
LABEL version="1.0.0"

# Install agent-specific dependencies
COPY requirements-dashboard.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dashboard.txt

# Copy agent code
COPY selfai/dashboard/ /app/selfai/dashboard/

# Copy shared utilities
COPY shared/ /app/shared/

# Set environment
ENV DASHBOARD_PORT=11000
ENV HEALTH_CHECK_PORT=11000
ENV HEALTH_CHECK_ENDPOINT=/api/health

# Expose port
EXPOSE 11000

# Use shared health check
HEALTHCHECK CMD python /app/shared/health_check.py

# Run
CMD ["python", "-m", "selfai.dashboard.dashboard_server", "--host", "0.0.0.0", "--port", "11000"]
```

### 3. Service Implementation (Health Check)

```python
# selfai/dashboard/dashboard_server.py
from flask import Flask, jsonify

@app.route('/api/health', methods=['GET'])
def health():
    """
    Health check endpoint (required by shared standard)
    """
    try:
        health_data = self.health_checker.get_health_dict()

        return jsonify({
            "status": "ok",
            "data": health_data
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

### 4. Docker Compose Integration

```yaml
# docker-compose.yml
services:
  agent2_dashboard:
    build:
      context: .
      dockerfile: agents/agent2_dashboard/Dockerfile
    container_name: agent2_dashboard
    ports:
      - "11000:11000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "python", "/app/shared/health_check.py"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - selfai_network
```

## Shared Interface Contracts

### 1. Configuration Contract

**All agents MUST provide:**

```yaml
playbook:
  name: string              # Required
  agent_id: string          # Required, format: agentN_name
  version: string           # Required, format: X.Y.Z
  description: string       # Required
  ports: [int]             # Required, list of ports
  health_check:            # Required
    endpoint: string
    interval_seconds: int
    timeout_seconds: int
    retries: int
```

**Validation:**

```python
from shared.utils import validate_config, load_playbook_config

config = load_playbook_config('agents/agent2_dashboard/playbook.yaml')
is_valid = validate_config(config)  # Returns True or raises ValueError
```

### 2. Health Check Contract

**All agents MUST implement:**

1. **Endpoint**: `/api/health`
2. **Method**: GET
3. **Response Format**:
   ```json
   {
     "status": "ok" | "error",
     "data": {
       "status": "healthy" | "degraded" | "unhealthy",
       "checks": [
         {
           "component": "string",
           "status": "healthy" | "degraded" | "unhealthy",
           "message": "string",
           "details": {}
         }
       ],
       "summary": {
         "total_checks": int,
         "healthy": int,
         "degraded": int,
         "unhealthy": int
       }
     }
   }
   ```

4. **Response Time**: < 10 seconds
5. **HTTP Status Codes**:
   - 200: Service healthy
   - 500: Service error

**Testing:**

```python
from shared.health_check import check_service

assert check_service(port=11000, endpoint="/api/health") == True
```

### 3. Docker Contract

**All agents MUST:**

1. **Extend base image**: `FROM selfai-base:latest`
2. **Include health check**: `HEALTHCHECK CMD python /app/shared/health_check.py`
3. **Set labels**:
   ```dockerfile
   LABEL agent_id="agentN_name"
   LABEL version="X.Y.Z"
   ```
4. **Use standard paths**:
   - Application: `/app`
   - Shared utilities: `/app/shared`
   - Agent code: `/app/agents/agentN_name`
   - Logs: `/app/logs`

### 4. Logging Contract

**All agents SHOULD use:**

```python
from shared.utils import setup_logging

logger = setup_logging(
    name="agent2_dashboard",
    level="INFO",
    log_file="/app/logs/agent.log"
)

logger.info("Service started")
logger.error("Error occurred")
```

**Log Format:**
```
YYYY-MM-DD HH:MM:SS - agent_name - LEVEL - message
```

### 5. Metrics Contract

**All agents SHOULD provide:**

```python
from shared.utils import MetricsCollector

metrics = MetricsCollector("agent2_dashboard")
metrics.increment("requests_total")
metrics.set_gauge("active_users", 42)
metrics.record_histogram("response_time", 0.125)

# Export at /api/metrics endpoint
@app.route('/api/metrics')
def get_metrics():
    return jsonify(metrics.export())
```

## Integration Flow

### 1. Development Flow

```bash
# 1. Create agent directory
mkdir -p agents/agentN_name

# 2. Create playbook.yaml (following schema)
cat > agents/agentN_name/playbook.yaml << EOF
playbook:
  name: "Agent Name"
  agent_id: "agentN_name"
  version: "1.0.0"
  ...
EOF

# 3. Create Dockerfile (extending base)
cat > agents/agentN_name/Dockerfile << EOF
FROM selfai-base:latest
...
EOF

# 4. Implement service with health check
# (in Python, implement /api/health endpoint)

# 5. Create build script
cat > agents/agentN_name/build.sh << 'EOF'
#!/bin/bash
docker build -f shared/base.Dockerfile -t selfai-base:latest .
docker build -f agents/agentN_name/Dockerfile -t selfai/agentN_name:1.0.0 .
EOF

# 6. Add to docker-compose.yml
# (add service definition)

# 7. Test
docker-compose up -d agentN_name
curl http://localhost:1N000/api/health
```

### 2. Build Flow

```bash
# Build base image (once)
docker build -f shared/base.Dockerfile -t selfai-base:latest .

# Build agent image
docker build -f agents/agent2_dashboard/Dockerfile -t selfai/agent2_dashboard:1.0.0 .

# Or use build script
bash agents/agent2_dashboard/build.sh
```

### 3. Deployment Flow

```bash
# Deploy with compose
docker-compose up -d agent2_dashboard

# Verify health
curl http://localhost:11000/api/health

# View logs
docker-compose logs -f agent2_dashboard

# Scale (if supported)
docker-compose up -d --scale agent2_dashboard=2
```

### 4. Testing Flow

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Test specific agent
pytest tests/integration/test_agent2_dashboard.py -v

# Test shared components
pytest tests/integration/test_shared_health_check.py -v
```

## Port Allocation

Standardized port ranges for agents:

| Agent | Port Range | Example |
|-------|------------|---------|
| Agent 1 (Infrastructure) | 10000-10999 | 10000 |
| Agent 2 (Dashboard) | 11000-11999 | 11000 |
| Agent 3 (Storage) | 12000-12999 | 12000 |
| Agent 4 (Network) | 13000-13999 | 13000 |
| Agent N | 1N000-1N999 | 1N000 |

## Environment Variables

Standard environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `AGENT_ID` | Agent identifier | `agent2_dashboard` |
| `AGENT_PORT` | Primary port | `11000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `HEALTH_CHECK_PORT` | Health check port | `11000` |
| `HEALTH_CHECK_ENDPOINT` | Health check path | `/api/health` |
| `NVIDIA_VISIBLE_DEVICES` | GPU visibility | `all` or `0,1` |

## Complete Example: Adding Agent 3

### Step 1: Create Configuration

```yaml
# agents/agent3_storage/playbook.yaml
playbook:
  name: "Storage Manager"
  agent_id: "agent3_storage"
  version: "1.0.0"
  description: "Distributed storage management"

  dependencies:
    - "minio>=7.0.0"

  ports:
    - 12000

  resources:
    gpu_required: false
    memory_gb: 16
    cpu_cores: 4

  health_check:
    endpoint: "/api/health"
    interval_seconds: 30
    timeout_seconds: 10
    retries: 3
```

### Step 2: Create Dockerfile

```dockerfile
# agents/agent3_storage/Dockerfile
FROM selfai-base:latest

LABEL agent_id="agent3_storage"
LABEL version="1.0.0"

# Install dependencies
RUN pip install --no-cache-dir minio

# Copy code
COPY agent3_code/ /app/agents/agent3_storage/
COPY shared/ /app/shared/

# Environment
ENV AGENT_PORT=12000
ENV HEALTH_CHECK_PORT=12000

# Expose port
EXPOSE 12000

# Health check
HEALTHCHECK CMD python /app/shared/health_check.py

# Run
CMD ["python", "-m", "agent3_storage.main"]
```

### Step 3: Implement Health Check

```python
# agent3_storage/main.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "data": {
            "status": "healthy",
            "checks": [
                {
                    "component": "Storage",
                    "status": "healthy",
                    "message": "Storage system operational"
                }
            ]
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=12000)
```

### Step 4: Add to Docker Compose

```yaml
# docker-compose.yml
services:
  agent3_storage:
    build:
      context: .
      dockerfile: agents/agent3_storage/Dockerfile
    container_name: agent3_storage
    ports:
      - "12000:12000"
    healthcheck:
      test: ["CMD", "python", "/app/shared/health_check.py"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - selfai_network
```

### Step 5: Test

```bash
# Build
bash agents/agent3_storage/build.sh

# Deploy
docker-compose up -d agent3_storage

# Test health
curl http://localhost:12000/api/health

# Integration test
pytest tests/integration/test_agent3_storage.py -v
```

## Troubleshooting

### Issue: Configuration Validation Fails

```python
# Debug configuration
from shared.utils import load_playbook_config, validate_config

try:
    config = load_playbook_config('agents/agent2_dashboard/playbook.yaml')
    validate_config(config)
    print("Configuration valid")
except ValueError as e:
    print(f"Configuration error: {e}")
```

### Issue: Health Check Fails

```bash
# Test manually
python shared/health_check.py

# Or
curl http://localhost:11000/api/health

# Check environment
docker exec agent2_dashboard env | grep HEALTH_CHECK
```

### Issue: Container Won't Start

```bash
# Check logs
docker-compose logs agent2_dashboard

# Inspect container
docker inspect agent2_dashboard

# Check base image
docker images | grep selfai-base
```

## Best Practices

1. **Always validate configuration** before deploying
2. **Implement comprehensive health checks** covering all critical components
3. **Use shared utilities** for common tasks (logging, metrics, config)
4. **Follow port allocation** standards
5. **Test locally** before pushing to production
6. **Document** agent-specific configuration and behavior
7. **Version** all changes using semantic versioning
8. **Monitor** health checks and metrics in production

## References

- [Shared Infrastructure README](shared/README.md)
- [Agents Directory README](agents/README.md)
- [Docker Deployment Guide](DOCKER_DEPLOYMENT.md)
- [Agent 2 Documentation](AGENT2_DASHBOARD.md)
- [Configuration Schema](shared/config_schema.yaml)

## Support

For integration issues:
1. Check this guide
2. Review shared component documentation
3. Test health checks manually
4. Check integration tests for examples
5. File an issue on GitHub

---

**Version**: 1.0.0
**Last Updated**: 2025-01-12
**Status**: Production Ready
