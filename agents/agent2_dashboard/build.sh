#!/bin/bash
# Build script for Agent 2: System Dashboard & Monitoring

set -e

echo "================================"
echo "Building Agent 2: Dashboard"
echo "================================"

# Navigate to project root
cd "$(dirname "$0")/../.."

# Build base image first
echo "Building base image..."
docker build -f shared/base.Dockerfile -t selfai-base:latest .

# Build agent image
echo "Building agent2_dashboard image..."
docker build \
    -f agents/agent2_dashboard/Dockerfile \
    -t selfai/agent2_dashboard:1.0.0 \
    -t selfai/agent2_dashboard:latest \
    .

echo ""
echo "================================"
echo "Build complete!"
echo "================================"
echo ""
echo "Images built:"
echo "  - selfai-base:latest"
echo "  - selfai/agent2_dashboard:1.0.0"
echo "  - selfai/agent2_dashboard:latest"
echo ""
echo "Next steps:"
echo "  docker-compose up -d agent2_dashboard"
echo ""
