# Dockerfile for SelfAI NPU Agent (CPU Fallback Mode)
# Multi-stage build for optimized image size

# ============================================================================
# Stage 1: Builder - Install dependencies and compile wheels
# ============================================================================
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements files
COPY requirements-core.txt requirements.txt ./

# Create virtual environment
RUN python -m venv /opt/venv

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements-core.txt

# ============================================================================
# Stage 2: Runtime - Create minimal runtime image
# ============================================================================
FROM python:3.12-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash selfai

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY --chown=selfai:selfai . /app/

# Create necessary directories
RUN mkdir -p /app/memory /app/models /app/memory/plans && \
    chown -R selfai:selfai /app/memory

# Switch to non-root user
USER selfai

# Expose port (if needed for future web UI)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "selfai/selfai.py"]

# Build arguments for metadata
ARG BUILD_DATE
ARG VERSION=2.0.0
ARG VCS_REF

# Labels (OCI standard)
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="SelfAI NPU Agent" \
      org.opencontainers.image.description="AI-powered terminal chatbot with multi-backend inference" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.authors="SelfAI Team" \
      org.opencontainers.image.url="https://github.com/smlfg/SelfAi-NPU-AGENT" \
      org.opencontainers.image.source="https://github.com/smlfg/SelfAi-NPU-AGENT" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="MIT"
