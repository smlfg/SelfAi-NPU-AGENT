# Docker Deployment Guide

Complete guide for deploying SelfAi NPU Agent using Docker and Docker Compose.

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+ recommended) or Windows with WSL2
- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **NVIDIA Docker Runtime**: For GPU support
- **GPU**: NVIDIA GPU with CUDA 12.4+ support (optional but recommended)

### Install Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Verify installation
docker --version
docker-compose --version
```

### Install NVIDIA Container Toolkit

```bash
# Add repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

## Architecture

### Multi-Layer Docker Setup

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Compose                          │
│              (Orchestration Layer)                       │
└──────────────┬──────────────────────────────────────────┘
               │
      ┌────────┼────────┬────────────┬──────────────┐
      │        │        │            │              │
      ▼        ▼        ▼            ▼              ▼
┌──────────┐ ┌────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
│ Agent 1  │ │Agent2│ │ Agent 3 │ │Agent 4 │ │ Agent N  │
│          │ │Dashbd│ │         │ │        │ │          │
└──────────┘ └────┘ └──────────┘ └────────┘ └──────────┘
      │         │         │           │            │
      └─────────┴─────────┴───────────┴────────────┘
                         │
                    ┌────▼─────┐
                    │   Base   │
                    │  Image   │
                    └──────────┘
                         │
                    ┌────▼─────┐
                    │  NVIDIA  │
                    │ PyTorch  │
                    └──────────┘
```

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/SelfAi-NPU-AGENT.git
cd SelfAi-NPU-AGENT
```

### 2. Build Base Image

```bash
# Build the shared base image (required once)
docker build -f shared/base.Dockerfile -t selfai-base:latest .
```

### 3. Build Agent Images

```bash
# Build Agent 2 (Dashboard)
bash agents/agent2_dashboard/build.sh

# Or build all agents
docker-compose build
```

### 4. Start Services

```bash
# Start all agents
docker-compose up -d

# Start specific agent
docker-compose up -d agent2_dashboard

# View logs
docker-compose logs -f agent2_dashboard
```

### 5. Verify Deployment

```bash
# Check service status
curl http://localhost:11000/api/status

# Check health
curl http://localhost:11000/api/health

# View GPU metrics
curl http://localhost:11000/api/gpu | jq
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# .env
COMPOSE_PROJECT_NAME=selfai
DASHBOARD_PORT=11000
LOG_LEVEL=INFO
NVIDIA_VISIBLE_DEVICES=all
```

### Agent-Specific Configuration

Each agent has a `playbook.yaml` file:

```yaml
# agents/agent2_dashboard/playbook.yaml
playbook:
  name: "DGX Dashboard"
  agent_id: "agent2_dashboard"
  version: "1.0.0"
  ports:
    - 11000
  resources:
    gpu_required: true
    memory_gb: 8
```

## Docker Compose Commands

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d agent2_dashboard

# Start with rebuild
docker-compose up -d --build

# Start in foreground (see logs)
docker-compose up agent2_dashboard
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop specific service
docker-compose stop agent2_dashboard
```

### Viewing Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs agent2_dashboard

# Follow logs (real-time)
docker-compose logs -f agent2_dashboard

# Last N lines
docker-compose logs --tail=100 agent2_dashboard
```

### Scaling Services

```bash
# Scale to multiple replicas (if supported)
docker-compose up -d --scale agent2_dashboard=2

# View running containers
docker-compose ps
```

### Inspecting Services

```bash
# List services
docker-compose ps

# View configuration
docker-compose config

# View service details
docker inspect agent2_dashboard

# Execute command in container
docker-compose exec agent2_dashboard bash

# View resource usage
docker stats
```

## Management

### Health Monitoring

```bash
# Check health status
docker-compose ps

# Detailed health check
curl http://localhost:11000/api/health | jq

# Container health
docker inspect --format='{{.State.Health.Status}}' agent2_dashboard

# All services health
for service in $(docker-compose ps --services); do
    echo "$service: $(docker inspect --format='{{.State.Health.Status}}' $service 2>/dev/null || echo 'no healthcheck')"
done
```

### Resource Management

```bash
# View resource usage
docker stats

# Limit resources (in docker-compose.yml)
services:
  agent2_dashboard:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          devices:
            - driver: nvidia
              count: 2
              capabilities: [gpu]
```

### Log Management

```bash
# Configure logging (in docker-compose.yml)
services:
  agent2_dashboard:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

# View log files
docker inspect agent2_dashboard | jq '.[0].LogPath'

# Clear logs
echo "" > $(docker inspect --format='{{.LogPath}}' agent2_dashboard)
```

## Networking

### Network Configuration

```yaml
# docker-compose.yml
networks:
  selfai_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

### Service Communication

```bash
# Services can communicate using service names
curl http://agent2_dashboard:11000/api/health

# View network details
docker network inspect selfai_network

# Connect container to network
docker network connect selfai_network container_name
```

### Port Mapping

```yaml
services:
  agent2_dashboard:
    ports:
      - "11000:11000"      # host:container
      - "127.0.0.1:11000:11000"  # bind to localhost only
```

## Volumes and Persistence

### Volume Configuration

```yaml
services:
  agent2_dashboard:
    volumes:
      # Named volume
      - dashboard_logs:/app/logs

      # Bind mount
      - ./playbooks/dgx-dashboard/logs:/app/logs

      # Read-only mount
      - ./config:/app/config:ro

volumes:
  dashboard_logs:
    driver: local
```

### Backup Volumes

```bash
# Backup volume
docker run --rm -v dashboard_logs:/source -v $(pwd):/backup \
    alpine tar czf /backup/dashboard_logs.tar.gz -C /source .

# Restore volume
docker run --rm -v dashboard_logs:/target -v $(pwd):/backup \
    alpine tar xzf /backup/dashboard_logs.tar.gz -C /target
```

## Security

### Best Practices

1. **Non-root user** in containers:
   ```dockerfile
   RUN useradd -m -u 1000 selfai
   USER selfai
   ```

2. **Read-only filesystem**:
   ```yaml
   services:
     agent2_dashboard:
       read_only: true
       tmpfs:
         - /tmp
   ```

3. **Drop capabilities**:
   ```yaml
   services:
     agent2_dashboard:
       cap_drop:
         - ALL
       cap_add:
         - NET_BIND_SERVICE
   ```

4. **Secrets management**:
   ```yaml
   services:
     agent2_dashboard:
       secrets:
         - api_key

   secrets:
     api_key:
       file: ./secrets/api_key.txt
   ```

5. **Network isolation**:
   ```yaml
   services:
     agent2_dashboard:
       networks:
         - internal
       ports:
         - "127.0.0.1:11000:11000"
   ```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Find process using port
lsof -i :11000

# Kill process
sudo kill -9 <PID>

# Or change port in docker-compose.yml
```

#### 2. GPU Not Accessible

```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi

# Check Docker daemon config
cat /etc/docker/daemon.json

# Should contain:
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
```

#### 3. Container Won't Start

```bash
# View logs
docker-compose logs agent2_dashboard

# Check container status
docker-compose ps

# Inspect container
docker inspect agent2_dashboard

# Run with debug
docker-compose up agent2_dashboard
```

#### 4. Health Check Failing

```bash
# Manual health check
curl http://localhost:11000/api/health

# Check from inside container
docker-compose exec agent2_dashboard \
    curl http://localhost:11000/api/health

# View health check logs
docker inspect agent2_dashboard | jq '.[0].State.Health'
```

#### 5. Build Failures

```bash
# Clear build cache
docker-compose build --no-cache

# Remove old images
docker system prune -a

# Check disk space
df -h
docker system df
```

## Production Deployment

### 1. Multi-Stage Builds

```dockerfile
# Build stage
FROM selfai-base:latest AS builder
COPY . /build
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM selfai-base:latest
COPY --from=builder /build /app
CMD ["python", "main.py"]
```

### 2. Image Registry

```bash
# Tag image
docker tag selfai/agent2_dashboard:1.0.0 registry.example.com/selfai/agent2_dashboard:1.0.0

# Login to registry
docker login registry.example.com

# Push image
docker push registry.example.com/selfai/agent2_dashboard:1.0.0
```

### 3. Production Compose File

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  agent2_dashboard:
    image: registry.example.com/selfai/agent2_dashboard:1.0.0
    restart: always
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
```

### 4. Deploy to Production

```bash
# Deploy
docker-compose -f docker-compose.prod.yml up -d

# Rolling update
docker-compose -f docker-compose.prod.yml up -d --no-deps --build agent2_dashboard
```

## Monitoring and Logging

### Prometheus Metrics

```yaml
services:
  agent2_dashboard:
    ports:
      - "9090:9090"  # Metrics port
```

### Logging to External Service

```yaml
services:
  agent2_dashboard:
    logging:
      driver: "syslog"
      options:
        syslog-address: "tcp://logs.example.com:514"
        tag: "agent2_dashboard"
```

### Health Check Monitoring

```bash
# Continuous health monitoring
watch -n 5 'curl -s http://localhost:11000/api/health | jq .status'
```

## Performance Optimization

### 1. Image Size Reduction

```dockerfile
# Multi-stage build
# Use alpine base
# Remove unnecessary files
# Combine RUN commands
```

### 2. Build Cache

```bash
# Use build cache
docker-compose build

# BuildKit for faster builds
DOCKER_BUILDKIT=1 docker-compose build
```

### 3. Resource Limits

```yaml
services:
  agent2_dashboard:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-docker)
- [Agent Configuration Schema](shared/config_schema.yaml)
- [Agent 2 Documentation](AGENT2_DASHBOARD.md)

## Support

For issues:
1. Check agent logs: `docker-compose logs agent2_dashboard`
2. Review health status: `curl http://localhost:11000/api/health`
3. Consult troubleshooting section above
4. File an issue on GitHub

---

**Last Updated**: 2025-01-12
**Docker Version**: 20.10+
**Compose Version**: 2.0+
