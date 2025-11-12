#!/bin/bash
# Start DGX Dashboard Server

set -e

# Load configuration
if [ -f playbooks/dgx-dashboard/config.env ]; then
    echo "Loading configuration..."
    source playbooks/dgx-dashboard/config.env
fi

# Default values
DASHBOARD_HOST=${DASHBOARD_HOST:-0.0.0.0}
DASHBOARD_PORT=${DASHBOARD_PORT:-11000}
DASHBOARD_DEBUG=${DASHBOARD_DEBUG:-false}

echo "================================"
echo "Starting DGX Dashboard Server"
echo "================================"
echo "Host: $DASHBOARD_HOST"
echo "Port: $DASHBOARD_PORT"
echo "================================"

# Create logs directory
mkdir -p playbooks/dgx-dashboard/logs

# Check if port is already in use
if lsof -Pi :$DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Error: Port $DASHBOARD_PORT is already in use"
    echo "Stop the existing process first:"
    echo "  bash playbooks/dgx-dashboard/stop.sh"
    exit 1
fi

# Start the server
if [ "$DASHBOARD_DEBUG" = "true" ]; then
    # Run in foreground with debug
    python3 -m selfai.dashboard.dashboard_server \
        --host "$DASHBOARD_HOST" \
        --port "$DASHBOARD_PORT" \
        --debug
else
    # Run in background
    nohup python3 -m selfai.dashboard.dashboard_server \
        --host "$DASHBOARD_HOST" \
        --port "$DASHBOARD_PORT" \
        > playbooks/dgx-dashboard/logs/dashboard.log 2>&1 &

    echo $! > playbooks/dgx-dashboard/dashboard.pid

    echo ""
    echo "Dashboard server started (PID: $(cat playbooks/dgx-dashboard/dashboard.pid))"
    echo ""
    echo "Access the API at:"
    echo "  http://$DASHBOARD_HOST:$DASHBOARD_PORT/api/status"
    echo ""
    echo "View logs:"
    echo "  tail -f playbooks/dgx-dashboard/logs/dashboard.log"
    echo ""
    echo "Stop the server:"
    echo "  bash playbooks/dgx-dashboard/stop.sh"
    echo ""
fi
