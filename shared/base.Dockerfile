# Shared Base Image for DGX Spark Playbooks
# Based on NVIDIA PyTorch with CUDA support

FROM nvcr.io/nvidia/pytorch:24.10-py3

LABEL maintainer="SelfAi NPU Agent Team"
LABEL description="Base image for DGX agent playbooks with CUDA and GPU support"

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # NVIDIA Container Toolkit
    nvidia-container-toolkit \
    # CUDA Toolkit
    cuda-toolkit-12-4 \
    # Build tools
    build-essential \
    cmake \
    git \
    curl \
    wget \
    # Python tools
    python3-dev \
    python3-pip \
    # System monitoring
    htop \
    nvtop \
    lsof \
    net-tools \
    # Networking
    iputils-ping \
    dnsutils \
    # Text processing
    jq \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install base Python packages
RUN pip install --no-cache-dir --upgrade \
    pip \
    setuptools \
    wheel

# Install common Python dependencies for all agents
RUN pip install --no-cache-dir \
    # Web frameworks
    flask>=2.3.0 \
    flask-cors>=4.0.0 \
    requests>=2.31.0 \
    # Data processing
    numpy>=1.24.0 \
    pandas>=2.0.0 \
    # System monitoring
    psutil>=5.9.0 \
    # Configuration
    PyYAML>=6.0 \
    python-dotenv>=1.0.0 \
    # Utilities
    tqdm>=4.65.0 \
    click>=8.1.0

# Create application directory
WORKDIR /app

# Create shared utilities directory
RUN mkdir -p /app/shared/utils

# Copy shared utilities (will be mounted or copied by child images)
COPY shared/ /app/shared/

# Create directory for agent-specific code
RUN mkdir -p /app/agents

# Set up health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python /app/shared/health_check.py || exit 1

# Default command (to be overridden by child images)
CMD ["python", "--version"]
