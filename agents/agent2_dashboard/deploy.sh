#!/bin/bash
# Deployment script for Agent 2: System Dashboard & Monitoring

set -e

echo "================================"
echo "Deploying Agent 2: Dashboard"
echo "================================"

# Navigate to project root
cd "$(dirname "$0")/../.."

# Load configuration
if [ -f agents/agent2_dashboard/playbook.yaml ]; then
    echo "Configuration loaded from playbook.yaml"
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p playbooks/dgx-dashboard/logs
mkdir -p jupyter_sessions

# Build images
echo "Building images..."
bash agents/agent2_dashboard/build.sh

# Deploy with docker-compose
echo "Deploying with docker-compose..."
docker-compose up -d agent2_dashboard

# Wait for service to be healthy
echo "Waiting for service to become healthy..."
sleep 5

# Check health
echo "Checking service health..."
curl -f http://localhost:11000/api/health || echo "Health check failed"

echo ""
echo "================================"
echo "Deployment complete!"
echo "================================"
echo ""
echo "Service running at:"
echo "  Dashboard API: http://localhost:11000/api/status"
echo ""
echo "Check logs:"
echo "  docker-compose logs -f agent2_dashboard"
echo ""
echo "Stop service:"
echo "  docker-compose down agent2_dashboard"
echo ""
