#!/bin/bash
# Check DGX Dashboard Server Status

# Load configuration
if [ -f playbooks/dgx-dashboard/config.env ]; then
    source playbooks/dgx-dashboard/config.env
fi

DASHBOARD_PORT=${DASHBOARD_PORT:-11000}

echo "================================"
echo "DGX Dashboard Server Status"
echo "================================"

# Check if PID file exists
if [ -f playbooks/dgx-dashboard/dashboard.pid ]; then
    pid=$(cat playbooks/dgx-dashboard/dashboard.pid)
    if ps -p $pid > /dev/null 2>&1; then
        echo "Status: RUNNING"
        echo "PID: $pid"
    else
        echo "Status: STOPPED (stale PID file)"
        rm -f playbooks/dgx-dashboard/dashboard.pid
    fi
else
    # Check by port
    pid=$(lsof -ti :$DASHBOARD_PORT 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo "Status: RUNNING"
        echo "PID: $pid"
    else
        echo "Status: STOPPED"
    fi
fi

# Try to access the API
echo ""
echo "Testing API connection..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$DASHBOARD_PORT/api/status | grep -q 200; then
    echo "API Status: OK"
    echo ""
    echo "API Response:"
    curl -s http://localhost:$DASHBOARD_PORT/api/status | python3 -m json.tool 2>/dev/null || curl -s http://localhost:$DASHBOARD_PORT/api/status
else
    echo "API Status: NOT ACCESSIBLE"
fi

echo ""
echo "================================"
