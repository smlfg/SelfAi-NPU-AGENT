#!/bin/bash
# Stop DGX Dashboard Server

set -e

echo "================================"
echo "Stopping DGX Dashboard Server"
echo "================================"

# Check if PID file exists
if [ -f playbooks/dgx-dashboard/dashboard.pid ]; then
    pid=$(cat playbooks/dgx-dashboard/dashboard.pid)

    # Check if process is running
    if ps -p $pid > /dev/null 2>&1; then
        echo "Stopping server (PID: $pid)..."
        kill $pid

        # Wait for process to stop
        timeout=10
        while ps -p $pid > /dev/null 2>&1 && [ $timeout -gt 0 ]; do
            sleep 1
            timeout=$((timeout - 1))
        done

        if ps -p $pid > /dev/null 2>&1; then
            echo "Process did not stop gracefully, forcing..."
            kill -9 $pid
        fi

        echo "Server stopped"
    else
        echo "Server is not running (stale PID file)"
    fi

    rm -f playbooks/dgx-dashboard/dashboard.pid
else
    # Try to find and kill by port
    DASHBOARD_PORT=${DASHBOARD_PORT:-11000}
    pid=$(lsof -ti :$DASHBOARD_PORT 2>/dev/null || true)

    if [ -n "$pid" ]; then
        echo "Found process on port $DASHBOARD_PORT (PID: $pid)"
        echo "Stopping..."
        kill $pid
        sleep 2
        echo "Server stopped"
    else
        echo "Server is not running"
    fi
fi

echo "Done"
