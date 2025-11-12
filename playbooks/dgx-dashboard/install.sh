#!/bin/bash
# DGX Dashboard Installation Script

set -e

echo "================================"
echo "DGX Dashboard Installation"
echo "================================"

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create logs directory
echo "Creating logs directory..."
mkdir -p playbooks/dgx-dashboard/logs

# Install Python dependencies
echo "Installing Python dependencies..."
pip install flask flask-cors psutil

# Optional: Install GPU monitoring libraries
echo ""
echo "Optional GPU monitoring libraries:"
echo "  - For NVIDIA GPUs: pip install pynvml"
echo "  - For AMD GPUs: pip install pyrsmi"
echo ""
read -p "Install NVIDIA GPU support (pynvml)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install pynvml
fi

# Optional: Install JupyterLab
echo ""
read -p "Install JupyterLab? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install jupyterlab
fi

# Create sessions directory
echo "Creating sessions directory..."
mkdir -p jupyter_sessions

# Set permissions
echo "Setting permissions..."
chmod +x playbooks/dgx-dashboard/*.sh

echo ""
echo "================================"
echo "Installation complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "  1. Review configuration: playbooks/dgx-dashboard/config.env"
echo "  2. Start the server: bash playbooks/dgx-dashboard/start.sh"
echo "  3. Access the API: http://localhost:11000/api/status"
echo ""
