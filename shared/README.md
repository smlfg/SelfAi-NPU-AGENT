# Shared Infrastructure for DGX Spark Playbooks

This directory contains shared components and interfaces used by all agent playbooks.

## Components

### 1. Base Docker Image (`base.Dockerfile`)

Shared base image for all agents based on NVIDIA PyTorch with CUDA support.

**Features:**
- NVIDIA PyTorch 24.10 with Python 3
- CUDA Toolkit 12.4
- Common Python dependencies (Flask, psutil, PyYAML, etc.)
- System monitoring tools
- Health check support

**Usage:**
```bash
# Build base image
docker build -f shared/base.Dockerfile -t selfai-base:latest .

# Use in agent Dockerfile
FROM selfai-base:latest
```

### 2. Configuration Schema (`config_schema.yaml`)

Unified configuration schema that all agents must follow.

**Structure:**
```yaml
playbook:
  name: string              # Human-readable name
  agent_id: string          # Unique identifier (agentN_name)
  version: string           # Semantic version (X.Y.Z)
  description: string       # Brief description

  dependencies: [...]       # Python packages
  system_dependencies: [...] # System packages
  ports: [...]             # Exposed ports
  volumes: [...]           # Volume mounts

  resources:
    gpu_required: bool
    gpu_count: int
    memory_gb: int
    cpu_cores: int

  health_check:
    endpoint: string
    interval_seconds: int
    timeout_seconds: int
    retries: int
```

**Validation:**
```python
from shared.utils import load_playbook_config, validate_config

config = load_playbook_config('agents/agent2_dashboard/playbook.yaml')
validate_config(config)  # Raises ValueError if invalid
```

### 3. Health Check API (`health_check.py`)

Standardized health checking for all services.

**Usage:**
```python
from shared.health_check import HealthChecker, check_service, wait_for_service

# Simple check
is_healthy = check_service(port=11000, endpoint="/api/health")

# Detailed check
checker = HealthChecker(port=11000, endpoint="/api/health")
is_healthy, message = checker.check()

# Wait for service to be ready
success = wait_for_service(port=11000, max_wait=60)

# Check multiple endpoints
results = checker.check_multiple_endpoints({
    "health": "/api/health",
    "status": "/api/status"
})
```

**Docker Integration:**
```dockerfile
# In Dockerfile
HEALTHCHECK CMD python /app/shared/health_check.py

# Environment variables
ENV HEALTH_CHECK_PORT=11000
ENV HEALTH_CHECK_ENDPOINT=/api/health
```

**Service Implementation:**
```python
# Your service must implement /api/health endpoint
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",  # or "error"
        "data": {
            "status": "healthy",  # "healthy", "degraded", "unhealthy"
            "checks": [...]
        }
    })
```

### 4. Shared Utilities (`utils/`)

Common utilities for all agents.

#### Config Loader (`utils/config_loader.py`)

```python
from shared.utils import load_playbook_config, validate_config

# Load configuration
config = load_playbook_config('path/to/playbook.yaml')

# Validate against schema
validate_config(config)  # Returns True or raises ValueError
```

#### Logging Utilities (`utils/logging_utils.py`)

```python
from shared.utils import setup_logging, get_logger

# Set up logging
logger = setup_logging(
    name="agent2_dashboard",
    level="INFO",
    log_file="/app/logs/agent.log"
)

logger.info("Service started")
logger.error("Error occurred")

# Get existing logger
logger = get_logger("agent2_dashboard")
```

#### Metrics Collection (`utils/metrics.py`)

```python
from shared.utils import MetricsCollector

# Initialize collector
metrics = MetricsCollector("agent2_dashboard")

# Record metrics
metrics.increment("requests_total")
metrics.set_gauge("gpu_utilization", 75.5)
metrics.record_histogram("response_time", 0.125)

# Export metrics
data = metrics.export()  # Returns dict
json_data = metrics.export_json()  # Returns JSON string

# Reset metrics
metrics.reset()
```

## Standards and Conventions

### Agent Naming

- **Format**: `agentN_name` where N is the agent number
- **Examples**: `agent2_dashboard`, `agent1_infra`, `agent3_storage`

### Port Allocation

Reserve ports for each agent:
- Agent 1: 10000-10999
- Agent 2: 11000-11999
- Agent 3: 12000-12999
- etc.

### Versioning

Follow semantic versioning:
- **MAJOR**: Incompatible API changes
- **MINOR**: Backward-compatible functionality
- **PATCH**: Backward-compatible bug fixes

Example: `1.0.0`, `1.2.3`, `2.0.0`

### Health Check Requirements

All agents must:
1. Implement `/api/health` endpoint
2. Return JSON with `status` field ("ok" or "error")
3. Include detailed health information in `data` field
4. Respond within 10 seconds
5. Use shared health check in Dockerfile

### Resource Specifications

Specify resource requirements in `playbook.yaml`:
```yaml
resources:
  gpu_required: true    # Whether GPU is required
  gpu_count: 2          # Number of GPUs needed
  memory_gb: 16         # Memory in GB
  cpu_cores: 8          # Number of CPU cores
```

### Volume Mounts

Standard volume structure:
```yaml
volumes:
  - host: "./logs"
    container: "/app/logs"
    mode: "rw"
  - host: "./config"
    container: "/app/config"
    mode: "ro"
```

### Environment Variables

Standard environment variables:
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `HEALTH_CHECK_PORT`: Port for health check
- `HEALTH_CHECK_ENDPOINT`: Endpoint for health check
- `AGENT_ID`: Agent identifier

## Creating a New Shared Component

### 1. Add to Shared Directory

```bash
# Create new module
touch shared/new_component.py

# Or add to utils
touch shared/utils/new_util.py
```

### 2. Implement Component

```python
# shared/new_component.py
"""
Shared component description
"""

class NewComponent:
    """Component implementation"""
    pass
```

### 3. Update Shared Init

```python
# shared/utils/__init__.py
from .new_util import NewUtil

__all__ = [..., 'NewUtil']
```

### 4. Document Component

Add to this README and include usage examples.

### 5. Update Base Dockerfile (if needed)

```dockerfile
# shared/base.Dockerfile
COPY shared/new_component.py /app/shared/
```

### 6. Test Component

```python
# tests/test_shared_new_component.py
import pytest
from shared.new_component import NewComponent

def test_new_component():
    component = NewComponent()
    assert component.method() == expected
```

## Testing Shared Components

### Unit Tests

```bash
# Run shared component tests
pytest tests/test_shared*.py -v
```

### Integration Tests

```bash
# Test health check with running service
pytest tests/integration/test_shared_health_check.py -v
```

## Usage Examples

### Complete Agent Setup

```python
# agent_main.py
from shared.utils import setup_logging, MetricsCollector
from shared.health_check import wait_for_service

# Setup logging
logger = setup_logging("agent2_dashboard", level="INFO")

# Initialize metrics
metrics = MetricsCollector("agent2_dashboard")

# Your agent code here
logger.info("Agent started")
metrics.increment("startup_count")
```

### Docker Integration

```dockerfile
# agents/agentN_name/Dockerfile
FROM selfai-base:latest

# Copy shared utilities
COPY shared/ /app/shared/

# Use shared health check
HEALTHCHECK CMD python /app/shared/health_check.py

# Agent code
CMD ["python", "main.py"]
```

### Health Check in Docker Compose

```yaml
# docker-compose.yml
services:
  agent2_dashboard:
    healthcheck:
      test: ["CMD", "python", "/app/shared/health_check.py"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Best Practices

1. **Keep shared components minimal**: Only add truly shared code
2. **Version shared components**: Update version in schema when changing
3. **Backward compatibility**: Don't break existing agents
4. **Document changes**: Update README when adding/changing components
5. **Test thoroughly**: Test with all agents before releasing
6. **Performance**: Keep shared components lightweight
7. **Security**: Validate all inputs, use secure defaults

## Troubleshooting

### Import Errors

```python
# Ensure PYTHONPATH includes project root
import sys
sys.path.insert(0, '/app')
from shared.health_check import HealthChecker
```

### Health Check Failing

```bash
# Test manually
python shared/health_check.py

# Check environment variables
echo $HEALTH_CHECK_PORT
echo $HEALTH_CHECK_ENDPOINT

# Test endpoint
curl http://localhost:$HEALTH_CHECK_PORT$HEALTH_CHECK_ENDPOINT
```

### Configuration Validation Errors

```python
# Validate configuration
from shared.utils import validate_config, load_playbook_config

config = load_playbook_config('playbook.yaml')
try:
    validate_config(config)
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Contributing

When contributing to shared components:

1. Discuss changes with team first
2. Ensure backward compatibility
3. Update documentation
4. Add tests
5. Test with all existing agents
6. Update version if needed

## Support

For issues with shared components:
1. Check this documentation
2. Review agent examples
3. Check integration tests
4. File an issue on GitHub

## License

See main project LICENSE file.
