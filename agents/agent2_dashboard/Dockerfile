# Agent 2: System Dashboard & Monitoring - Dockerfile
# Extends shared base image

FROM selfai-base:latest

LABEL agent_id="agent2_dashboard"
LABEL agent_name="DGX Dashboard"
LABEL version="1.0.0"
LABEL description="Web UI + GPU Monitoring"

# Set working directory for this agent
WORKDIR /app/agents/agent2_dashboard

# Copy agent-specific requirements
COPY requirements-dashboard.txt /tmp/requirements-dashboard.txt

# Install agent-specific dependencies
RUN pip install --no-cache-dir -r /tmp/requirements-dashboard.txt

# Optional: Install NVIDIA GPU monitoring (if available)
RUN pip install --no-cache-dir pynvml || echo "pynvml installation failed, continuing..."

# Optional: Install JupyterLab (commented out by default to reduce image size)
# RUN pip install --no-cache-dir jupyterlab

# Copy agent code
COPY selfai/dashboard/ /app/selfai/dashboard/
COPY selfai/agents/system_dashboard_monitoring/ /app/selfai/agents/system_dashboard_monitoring/

# Copy playbook configuration
COPY agents/agent2_dashboard/playbook.yaml /app/agents/agent2_dashboard/playbook.yaml

# Copy shared utilities
COPY shared/ /app/shared/

# Create necessary directories
RUN mkdir -p /app/logs \
    && mkdir -p /app/jupyter_sessions \
    && mkdir -p /app/playbooks/dgx-dashboard/logs

# Set environment variables from playbook
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_PORT=11000
ENV DASHBOARD_DEBUG=false
ENV LOG_LEVEL=INFO
ENV HEALTH_CHECK_PORT=11000
ENV HEALTH_CHECK_ENDPOINT=/api/health
ENV PYTHONPATH=/app:${PYTHONPATH}

# Expose dashboard port
EXPOSE 11000

# Health check using shared health_check.py
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python /app/shared/health_check.py || exit 1

# Run the dashboard server
CMD ["python", "-m", "selfai.dashboard.dashboard_server", "--host", "0.0.0.0", "--port", "11000"]
