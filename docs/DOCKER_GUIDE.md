# 🐳 Docker Guide for SelfAI NPU Agent

**Welcome!** This guide will help you run SelfAI NPU Agent using Docker, even if you've never used Docker before.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start: The "One-Command" Launch](#quick-start-the-one-command-launch)
- [Understanding Docker Mode](#understanding-docker-mode)
- [Development Workflow](#development-workflow)
- [Using CLI Commands Inside Docker](#using-cli-commands-inside-docker)
- [Managing Services](#managing-services)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## 🎯 Prerequisites

### What You Need

Before starting, make sure you have **Docker** installed on your system:

#### **Windows**
1. Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. Install and restart your computer
3. Launch Docker Desktop (it will run in the background)
4. You'll see a whale icon in your system tray when it's ready

#### **macOS**
1. Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Install by dragging to Applications
3. Launch Docker Desktop
4. Wait for the whale icon to appear in the menu bar

#### **Linux**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (optional, to avoid sudo)
sudo usermod -aG docker $USER
# Log out and back in for this to take effect
```

### Verify Installation

Open a terminal and run:

```bash
docker --version
docker-compose --version
```

You should see version numbers like:
```
Docker version 24.0.0
docker-compose version 1.29.2
```

**✅ If you see these, you're ready to go!**

---

## 🚀 Quick Start: The "One-Command" Launch

### Step 1: Clone the Repository

```bash
git clone https://github.com/smlfg/SelfAi-NPU-AGENT.git
cd SelfAi-NPU-AGENT
```

### Step 2: Prepare Configuration (First Time Only)

```bash
# Copy configuration templates
cp config.yaml.template config.yaml
cp .env.example .env

# Edit .env and add a placeholder API key
echo "API_KEY=docker-cpu-mode" >> .env
```

### Step 3: Download a Model (First Time Only)

Create the models directory and download a CPU model:

```bash
# Create models directory
mkdir -p models

# Download Phi-3-mini model (recommended, ~2.3GB)
# On Linux/macOS:
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf \
     -O models/Phi-3-mini-4k-instruct.Q4_K_M.gguf

# On Windows (PowerShell):
# Invoke-WebRequest -Uri "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf" -OutFile "models/Phi-3-mini-4k-instruct.Q4_K_M.gguf"
```

**Note:** The model download is ~2.3GB and may take a few minutes.

### Step 4: Launch with One Command! 🎉

```bash
docker-compose up
```

**That's it!** Docker will:
1. ✅ Build the SelfAI image (first time only, ~5 minutes)
2. ✅ Start the SelfAI container
3. ✅ Start the Ollama container (optional, for planning)
4. ✅ Show logs in your terminal

You should see output like:
```
selfai-npu-agent | ✓ Configuration loaded successfully
selfai-npu-agent | ✓ CPU-Modell 'Phi-3-mini-4k-instruct.Q4_K_M.gguf' geladen
selfai-npu-agent | Aktiver Agent: Code Helper
selfai-npu-agent |
selfai-npu-agent | Du: _
```

### Step 5: Start Chatting!

The container is now running interactively. Type your message:

```
Du: What is Python?
[CPU] ▶ Python is a high-level, interpreted programming language...
```

**To exit:** Press `Ctrl+C` or type `quit`

---

## 🏗️ Understanding Docker Mode

### Important: CPU Fallback by Default

When running SelfAI in Docker, you're using **CPU Fallback Mode**:

- ✅ **Works on any platform** (Windows, macOS, Linux)
- ✅ **No special hardware needed**
- ✅ **Consistent behavior across systems**
- ⚠️ **Slower than NPU** (hardware acceleration not available)

### Why Not NPU in Docker?

Passing the **Snapdragon X Elite NPU** to a Docker container requires:
- Specific WSL2 configuration (Windows only)
- NPU drivers mounted into the container
- Complex hardware passthrough setup

For most developers, **CPU mode is simpler and works everywhere.**

### Architecture in Docker

```
┌─────────────────────────────────────┐
│         Docker Container            │
│  ┌───────────────────────────────┐  │
│  │    SelfAI NPU Agent           │  │
│  │    (CPU Fallback Mode)        │  │
│  └───────────────────────────────┘  │
│               ↓                     │
│  ┌───────────────────────────────┐  │
│  │  GGUF Model (Phi-3-mini)      │  │
│  │  via llama-cpp-python         │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         ↑ (Volume Mount)
    /models (on host)
```

**Optional Ollama Service:**
- If you enable planning/merge phases, Ollama runs in a separate container
- Models are shared via Docker network

---

## 💻 Development Workflow

### Running in Background (Detached Mode)

For development, run containers in the background:

```bash
docker-compose up -d
```

Now containers run silently. To interact:

```bash
# Access SelfAI interactively
docker-compose exec selfai python selfai/selfai.py

# Or get a bash shell
docker-compose exec selfai bash
```

### Live Code Editing (Hot Reload)

The `docker-compose.yml` is already configured to **mount your code as a volume**:

```yaml
volumes:
  - ./selfai:/app/selfai  # Your code
  - ./config.yaml:/app/config.yaml
  - ./models:/app/models
  - ./memory:/app/memory
```

**This means:**
1. ✅ Edit code in VS Code (or any editor) on your host machine
2. ✅ Changes are **immediately reflected** inside the container
3. ✅ **No rebuild needed** for Python code changes
4. ⚠️ Restart the service if you change dependencies

### Making Code Changes

**Example: Edit a file**

1. **On your host machine**, open `selfai/selfai.py` in VS Code
2. Make your changes (e.g., add a print statement)
3. **Save the file**

**In Docker:**

```bash
# Restart the service to pick up changes
docker-compose restart selfai

# Or if running interactively, just Ctrl+C and restart
docker-compose up
```

### Testing Your Changes

```bash
# Run tests inside the container
docker-compose exec selfai pytest

# Run with coverage
docker-compose exec selfai pytest --cov=selfai --cov-report=html

# Run specific test file
docker-compose exec selfai pytest tests/test_domain.py
```

### Installing New Dependencies

If you add new packages to `requirements.txt`:

```bash
# Rebuild the Docker image
docker-compose build

# Restart with new image
docker-compose up -d
```

---

## 🛠️ Using CLI Commands Inside Docker

### Available CLI Tools

Once the container is running, you can use all SelfAI commands:

#### 1. **Main SelfAI CLI**

```bash
# Interactive chat
docker-compose exec selfai python selfai/selfai.py

# Show help
docker-compose exec selfai python selfai/selfai.py --help
```

#### 2. **Direct QNN Chat** (if QNN models available)

```bash
docker-compose exec selfai python llm_chat.py
```

#### 3. **Configuration Checker**

```bash
docker-compose exec selfai python check_dependencies.py
```

#### 4. **Preflight Check**

```bash
docker-compose exec selfai python preflight_check.py
```

### Using Commands Inside the Container

**Method 1: One-Off Commands**

```bash
# Format code
docker-compose exec selfai black selfai/

# Type check
docker-compose exec selfai mypy selfai/

# Run linter
docker-compose exec selfai pylint selfai/
```

**Method 2: Interactive Shell**

```bash
# Enter the container
docker-compose exec selfai bash

# Now you're inside! Run any command:
root@container:/app$ python selfai/selfai.py
root@container:/app$ pytest
root@container:/app$ black selfai/
root@container:/app$ exit
```

### Example: Planning with Ollama

If you enabled the Ollama service:

```bash
# Pull a model (first time)
docker-compose exec ollama ollama pull gemma3:1b

# List models
docker-compose exec ollama ollama list

# Test Ollama
docker-compose exec ollama ollama run gemma3:1b "Hello!"
```

Then in SelfAI:

```bash
docker-compose exec selfai python selfai/selfai.py
Du: /plan Create a web scraper for news sites
```

---

## 🎛️ Managing Services

### Starting Services

```bash
# Start all services (foreground, see logs)
docker-compose up

# Start in background (detached)
docker-compose up -d

# Start only SelfAI (without Ollama)
docker-compose up -d selfai
```

### Stopping Services

```bash
# Stop all services (keeps data)
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Stop and remove everything including volumes (⚠️ deletes data!)
docker-compose down -v
```

### Viewing Logs

```bash
# View all logs
docker-compose logs

# Follow logs (live update)
docker-compose logs -f

# View only SelfAI logs
docker-compose logs -f selfai

# View last 100 lines
docker-compose logs --tail=100
```

### Restarting Services

```bash
# Restart all services
docker-compose restart

# Restart only SelfAI
docker-compose restart selfai
```

### Rebuilding After Changes

```bash
# Rebuild images (after dependency changes)
docker-compose build

# Rebuild without cache (clean build)
docker-compose build --no-cache

# Rebuild and restart
docker-compose up -d --build
```

---

## 🔧 Troubleshooting

### Problem 1: Container Immediately Exits

**Symptom:**
```bash
docker-compose up
# Container starts then exits immediately
```

**Solution:**
```bash
# Check logs to see the error
docker-compose logs selfai

# Common causes:
# - Model file not found (check models/ directory)
# - Config file missing (copy config.yaml.template)
# - .env file missing (copy .env.example)
```

**Fix:**
```bash
# Ensure all files exist
ls -la config.yaml .env models/

# Restart
docker-compose restart
```

### Problem 2: "API_KEY is not set"

**Symptom:**
```
ValueError: API_KEY is not set
```

**Solution:**
```bash
# Edit .env file
echo "API_KEY=docker-cpu-mode" > .env

# Restart container
docker-compose restart selfai
```

### Problem 3: "Model file not found"

**Symptom:**
```
FileNotFoundError: models/Phi-3-mini-4k-instruct.Q4_K_M.gguf
```

**Solution:**
```bash
# Check if model exists
ls -lh models/

# Download model if missing
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf \
     -O models/Phi-3-mini-4k-instruct.Q4_K_M.gguf

# Restart
docker-compose restart selfai
```

### Problem 4: Port Already in Use

**Symptom:**
```
Error: bind: address already in use
```

**Solution:**
```bash
# Find what's using the port
lsof -i :11434  # For Ollama
# Or on Windows: netstat -ano | findstr :11434

# Either stop that process or change the port in docker-compose.yml:
ports:
  - "11435:11434"  # Use different host port
```

### Problem 5: Container Runs Slowly

**Symptom:**
- Responses take a very long time

**Solution:**
```bash
# Increase resource limits in docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '8.0'      # Increase CPUs
      memory: 16G      # Increase RAM

# Restart
docker-compose up -d --force-recreate
```

### Problem 6: Changes Not Reflected

**Symptom:**
- You edit code but container doesn't see changes

**Solution:**
```bash
# 1. Check if volume is mounted correctly
docker-compose exec selfai ls -la /app/selfai/

# 2. If files are old, restart
docker-compose restart selfai

# 3. If still not working, check docker-compose.yml volumes:
volumes:
  - ./selfai:/app/selfai  # Should be present
```

### Problem 7: "Permission Denied"

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/app/memory/...'
```

**Solution:**
```bash
# On Linux/macOS, fix permissions
sudo chown -R $USER:$USER memory/

# Or run container as your user
docker-compose down
# Edit docker-compose.yml:
user: "${UID}:${GID}"

docker-compose up -d
```

### Viewing Full Container State

```bash
# Check container status
docker-compose ps

# Inspect detailed info
docker inspect selfai-npu-agent

# Check resource usage
docker stats

# Enter container for debugging
docker-compose exec selfai bash
```

---

## ⚙️ Advanced Configuration

### Custom Docker Compose Override

Create `docker-compose.override.yml` for local customizations:

```yaml
version: '3.8'

services:
  selfai:
    environment:
      - DEBUG=true
    deploy:
      resources:
        limits:
          cpus: '8.0'
          memory: 16G
```

This file is automatically merged with `docker-compose.yml`.

### Using Different Models

**Edit `config.yaml` before starting:**

```yaml
cpu_fallback:
  model_path: "deepseek-llm-7b-chat.Q4_K_M.gguf"  # Change model
  n_ctx: 8192  # Larger context
```

**Download the model to `models/` directory.**

### Enabling Planning/Merge with Ollama

**In `config.yaml`:**

```yaml
planner:
  enabled: true
  providers:
    - name: "docker-ollama"
      base_url: "http://ollama:11434"  # Note: 'ollama' hostname
      model: "gemma3:1b"

merge:
  enabled: true
  providers:
    - name: "docker-ollama"
      base_url: "http://ollama:11434"
      model: "gemma3:3b"
```

**Pull models:**

```bash
docker-compose exec ollama ollama pull gemma3:1b
docker-compose exec ollama ollama pull gemma3:3b
```

### Mounting Additional Directories

**Edit `docker-compose.yml`:**

```yaml
volumes:
  - ./data:/app/data  # Add custom data directory
  - ./scripts:/app/scripts:ro  # Read-only scripts
```

---

## 📚 Quick Reference

### Essential Commands Cheat Sheet

```bash
# ========================================
# Starting/Stopping
# ========================================
docker-compose up                 # Start (foreground)
docker-compose up -d              # Start (background)
docker-compose stop               # Stop
docker-compose down               # Stop and remove
docker-compose restart            # Restart

# ========================================
# Building
# ========================================
docker-compose build              # Rebuild images
docker-compose build --no-cache   # Clean rebuild
docker-compose up -d --build      # Rebuild and restart

# ========================================
# Logs & Debugging
# ========================================
docker-compose logs               # View all logs
docker-compose logs -f selfai     # Follow SelfAI logs
docker-compose logs --tail=50     # Last 50 lines
docker-compose ps                 # Container status

# ========================================
# Running Commands
# ========================================
docker-compose exec selfai bash                     # Enter container
docker-compose exec selfai python selfai/selfai.py  # Run SelfAI
docker-compose exec selfai pytest                   # Run tests
docker-compose exec ollama ollama pull gemma3:1b    # Pull Ollama model

# ========================================
# Cleanup
# ========================================
docker-compose down -v            # Remove everything (⚠️ data too!)
docker system prune -a            # Clean all unused Docker data
```

---

## 🎓 Learning Resources

### Understanding Docker

- [Official Docker Tutorial](https://docs.docker.com/get-started/)
- [Docker Compose Overview](https://docs.docker.com/compose/)

### SelfAI Documentation

- [Main README](../README.md) - Project overview
- [Contributing Guide](../CONTRIBUTING.md) - Development setup
- [Architecture Details](../CLAUDE.md) - System architecture

---

## 🆘 Getting Help

### If You're Stuck

1. **Check Logs First:**
   ```bash
   docker-compose logs -f selfai
   ```

2. **Search Troubleshooting Section** (above) for your error

3. **Check GitHub Issues:**
   - [Existing Issues](https://github.com/smlfg/SelfAi-NPU-AGENT/issues)
   - Search for your error message

4. **Create a New Issue:**
   - Include your error message
   - Include relevant logs
   - Describe what you tried

5. **Ask in Discussions:**
   - [GitHub Discussions](https://github.com/smlfg/SelfAi-NPU-AGENT/discussions)

---

## ✅ Success Checklist

Before asking for help, verify:

- [ ] Docker Desktop is running (whale icon visible)
- [ ] You're in the project root directory
- [ ] `config.yaml` exists (copied from template)
- [ ] `.env` exists with `API_KEY=docker-cpu-mode`
- [ ] Model file exists in `models/` directory
- [ ] You ran `docker-compose build` at least once
- [ ] Ports 11434 (Ollama) and 8000 (SelfAI) are not in use

---

**🎉 Congratulations!** You're now running SelfAI NPU Agent in Docker!

**Next Steps:**
- Try the [Usage Examples](../README.md#usage-examples) in the main README
- Read the [Contributing Guide](../CONTRIBUTING.md) to start developing
- Explore the [Architecture](../CLAUDE.md) to understand the system

---

<p align="center">
  <strong>Made with ❤️ for Docker enthusiasts</strong>
</p>

<p align="center">
  <a href="../README.md">Main README</a> •
  <a href="../CONTRIBUTING.md">Contributing</a> •
  <a href="../CLAUDE.md">Architecture</a> •
  <a href="https://github.com/smlfg/SelfAi-NPU-AGENT/issues">Support</a>
</p>
