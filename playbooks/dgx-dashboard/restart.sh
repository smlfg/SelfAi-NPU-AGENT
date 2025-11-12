#!/bin/bash
# Restart DGX Dashboard Server

echo "================================"
echo "Restarting DGX Dashboard Server"
echo "================================"

# Stop the server
bash playbooks/dgx-dashboard/stop.sh

# Wait a moment
sleep 2

# Start the server
bash playbooks/dgx-dashboard/start.sh
