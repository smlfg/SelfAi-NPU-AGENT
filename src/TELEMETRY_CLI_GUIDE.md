## Telemetry & CLI System - Complete Guide

This document provides comprehensive documentation for the telemetry tracking system and management CLI.

---

## 📊 Telemetry System

### Overview

The telemetry system provides automatic performance tracking and metrics collection for all LLM backend providers. It helps you:

- **Measure Performance**: Track latency and response times
- **Compare Providers**: Prove NPU is faster than CPU
- **Monitor Health**: Track success/failure rates
- **Optimize Usage**: Analyze token consumption

### Architecture

```
┌──────────────────────────────────────────────────────┐
│         TelemetryManager (Singleton)                  │
├──────────────────────────────────────────────────────┤
│  • Thread-safe metrics collection                    │
│  • Automatic JSON persistence                        │
│  • Per-provider statistics                           │
│  • Performance comparisons                           │
└───────────────┬──────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
  @track_latency   @track_token_usage
  (Decorator)       (Decorator)
        │                │
        └────────┬───────┘
                 │
                 ▼
        telemetry/stats.json
```

### Core Components

#### 1. TelemetryManager (Singleton)

```python
from src.core.telemetry import TelemetryManager

# Get singleton instance
telemetry = TelemetryManager.get_instance(
    stats_file=Path("telemetry/stats.json"),
    enabled=True,
)

# Record latency
telemetry.record_latency("NPUProvider", 0.342, success=True)

# Record token usage
telemetry.record_token_usage("NPUProvider", input_tokens=150, output_tokens=50)

# Get statistics
stats = telemetry.get_statistics()
print(stats['providers']['NPUProvider']['avg_latency'])

# Compare providers
comparison = telemetry.compare_providers()
print(f"NPU is {comparison['speedup']:.2f}x faster than CPU")

# Export report
report = telemetry.export_report(Path("report.txt"))
```

#### 2. @track_latency Decorator

Automatically tracks function execution time:

```python
from src.core.telemetry import track_latency

@track_latency("NPUProvider")
def generate_response(prompt: str) -> str:
    # Your implementation
    return "response"
```

For class methods (auto-detects provider name):

```python
class NPUProvider(LLMProvider):
    @track_latency()  # Uses self.provider_name
    def generate_response(self, system_prompt, user_prompt, ...):
        # Implementation
        pass
```

#### 3. @track_token_usage Decorator

Automatically tracks token consumption:

```python
from src.core.telemetry import track_token_usage

@track_token_usage("NPUProvider")
def generate_with_tokens(prompt: str) -> dict:
    return {
        "response": "Hello",
        "input_tokens": 10,
        "output_tokens": 5,
    }
```

### Integration with Backends

#### Example: Enhanced NPUProvider

```python
from src.backends.base import LLMProvider
from src.core.telemetry import track_latency, TelemetryManager

class NPUProvider(LLMProvider):
    def __init__(self, ...):
        super().__init__(provider_name="AnythingLLM", provider_type="npu")
        # ... initialization

    @track_latency()  # Automatically tracks latency
    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """Generate response (latency tracked automatically)."""
        # Implementation
        response = self._call_api(...)

        # Manually track tokens if available
        if hasattr(response, 'usage'):
            telemetry = TelemetryManager.get_instance()
            telemetry.record_token_usage(
                self.provider_name,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

        return response.text
```

### Metrics Structure

The telemetry system stores metrics in JSON format:

```json
{
  "session_start": "2025-01-19T10:30:00",
  "totals": {
    "requests": 150,
    "successes": 145,
    "failures": 5,
    "total_latency": 52.3,
    "total_tokens": 45000
  },
  "providers": {
    "NPUProvider": {
      "requests": 100,
      "successes": 98,
      "failures": 2,
      "total_latency": 28.5,
      "min_latency": 0.25,
      "max_latency": 0.45,
      "total_tokens": 30000,
      "latency_samples": [
        {"timestamp": "2025-01-19T10:31:00", "latency": 0.32},
        ...
      ]
    },
    "CPUProvider": {
      "requests": 50,
      "successes": 47,
      "failures": 3,
      "total_latency": 23.8,
      ...
    }
  }
}
```

### Performance Comparison

```python
comparison = telemetry.compare_providers()

# Output:
{
  "providers": ["NPUProvider", "CPUProvider"],
  "fastest_provider": "NPUProvider",
  "fastest_latency": 0.29,
  "npu_latency": 0.29,
  "cpu_latency": 0.476,
  "speedup": 1.64,
  "performance_gain_percent": 39.1
}
```

### Configuration

Enable/disable telemetry in `config.yaml`:

```yaml
system:
  streaming_enabled: true
  enable_telemetry: true  # Enable metrics collection
```

Load configuration:

```python
from config_loader import load_configuration
from src.core.telemetry import TelemetryManager

config = load_configuration()

telemetry = TelemetryManager.get_instance(
    enabled=config.system.enable_telemetry
)
```

---

## 🛠️ Management CLI

### Overview

The management CLI provides command-line tools for:

- **Health Checks**: Test backend connectivity
- **Configuration**: View and validate settings
- **Maintenance**: Clean logs and manage system
- **Monitoring**: View performance metrics

### Installation

Install required dependencies:

```bash
pip install typer rich
```

Make manage.py executable (optional):

```bash
chmod +x manage.py
```

### Commands

#### 1. Check Backend Connectivity

Test all configured backends:

```bash
python manage.py check
```

With verbose output:

```bash
python manage.py check --verbose
```

**Output Example:**

```
🔍 Running Backend Connectivity Checks

⏳ Testing AnythingLLM (NPU)...
⏳ Checking QNN models...
⏳ Checking CPU fallback model...

┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Backend                 ┃ Status             ┃ Details              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ AnythingLLM (NPU)       │ ✅ Healthy         │ URL: http://...      │
│ QNN Models              │ ✅ Found 1         │ Models: Phi-3.5      │
│ CPU Fallback            │ ✅ Available       │ Model: Phi-3-mini... │
└─────────────────────────┴────────────────────┴──────────────────────┘

✅ All 3 backends are healthy!
```

#### 2. Show Configuration

Display current settings with masked secrets:

```bash
python manage.py config
```

Show unmasked API keys (use with caution):

```bash
python manage.py config --show-secrets
```

**Output Example:**

```
⚙️  Current Configuration

╭─ NPU Provider (AnythingLLM) ──────────────────────────╮
│ Base URL: http://localhost:3001/api/v1                │
│ Workspace: main                                        │
│ API Key: ********abc123                               │
╰────────────────────────────────────────────────────────╯

╭─ CPU Fallback ─────────────────────────────────────────╮
│ Model Path: Phi-3-mini-4k-instruct.Q4_K_M.gguf        │
│ Context Size: 4096                                     │
│ GPU Layers: 0                                          │
╰────────────────────────────────────────────────────────╯

╭─ System Settings ──────────────────────────────────────╮
│ Streaming: ✅ Enabled                                  │
│ Telemetry: ✅ Enabled                                  │
│ Timeout: 60.0s                                         │
╰────────────────────────────────────────────────────────╯
```

#### 3. Clear Log Files

Remove old log files:

```bash
python manage.py clear-logs
```

Custom options:

```bash
# Clean logs older than 30 days
python manage.py clear-logs --days 30

# Custom directory
python manage.py clear-logs --dir logs/debug

# Dry run (preview without deleting)
python manage.py clear-logs --dry-run
```

**Output Example:**

```
🧹 Cleaning Logs
Directory: /path/to/logs
Older than: 7 days

Deleted: debug_2025-01-10.log (2,548 bytes)
Deleted: error_2025-01-11.log (1,234 bytes)

✅ Deleted 2 files (3,782 bytes)
```

#### 4. View Telemetry

Display performance metrics:

```bash
python manage.py telemetry
```

Export full report:

```bash
python manage.py telemetry --export
python manage.py telemetry --export --file my_report.txt
```

Clear all metrics:

```bash
python manage.py telemetry --clear
```

**Output Example:**

```
📊 Performance Metrics

╭─ Overall Statistics ───────────────────────────────────╮
│ Total Requests: 150                                    │
│ Successes: 145 (96.7%)                                 │
│ Failures: 5                                            │
│ Avg Latency: 0.349s                                    │
│ Total Tokens: 45,230                                   │
╰────────────────────────────────────────────────────────╯

┏━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┓
┃ Provider    ┃ Requests ┃ Success Rate ┃ Avg Latency┃ Tokens ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━┩
│ NPUProvider │      100 │       98.0%  │     0.285s │ 30,150 │
│ CPUProvider │       50 │       94.0%  │     0.476s │ 15,080 │
└─────────────┴──────────┴──────────────┴────────────┴────────┘

╭─ NPU vs CPU Performance ───────────────────────────────╮
│ NPU Latency: 0.285s                                    │
│ CPU Latency: 0.476s                                    │
│ Speedup: 1.67x                                         │
│ Performance Gain: 40.1%                                │
╰────────────────────────────────────────────────────────╯
```

#### 5. Version Information

Show version details:

```bash
python manage.py version
```

#### 6. Help

View all commands:

```bash
python manage.py --help
```

Help for specific command:

```bash
python manage.py check --help
```

---

## 🔧 Integration Examples

### Example 1: Backend with Telemetry

```python
from src.backends import BackendManager, NPUProvider, CPUProvider
from src.core.telemetry import TelemetryManager
from config_loader import load_configuration

# Load config
config = load_configuration()

# Initialize telemetry
telemetry = TelemetryManager.get_instance(
    enabled=config.system.enable_telemetry
)

# Create providers (decorators handle tracking)
npu = NPUProvider(...)
cpu = CPUProvider(...)

# Create manager
manager = BackendManager(providers=[npu, cpu])

# Use normally - telemetry tracks automatically
response = manager.generate_response(
    system_prompt="You are helpful.",
    user_prompt="Hello!",
)

# View stats
stats = telemetry.get_statistics()
print(f"Avg latency: {stats['totals']['avg_latency']:.3f}s")
```

### Example 2: Custom Telemetry Integration

```python
from src.core.telemetry import TelemetryManager, track_latency

# Your custom function
@track_latency("CustomBackend")
def my_custom_llm_call(prompt: str) -> str:
    # Your implementation
    time.sleep(0.5)  # Simulated work
    return "response"

# Call it
result = my_custom_llm_call("test")

# Telemetry automatically recorded
telemetry = TelemetryManager.get_instance()
stats = telemetry.get_statistics()
print(stats['providers']['CustomBackend'])
```

### Example 3: Programmatic CLI

```python
from src.cli import check, telemetry, config_show
import typer

# Use CLI functions programmatically
app = typer.Typer()

@app.command()
def my_workflow():
    """Custom workflow using CLI commands."""
    # Run checks
    check(verbose=True)

    # Show config
    config_show(show_secrets=False)

    # View telemetry
    telemetry(export=True, file="my_report.txt")

if __name__ == "__main__":
    app()
```

---

## 📈 Best Practices

### 1. Enable Telemetry in Production

Always enable telemetry to gather performance data:

```yaml
# config.yaml
system:
  enable_telemetry: true
```

### 2. Regular Monitoring

Schedule periodic checks:

```bash
# Add to cron or task scheduler
0 */6 * * * python /path/to/manage.py check >> /var/log/selfai/health.log
0 0 * * * python /path/to/manage.py telemetry --export --file /var/log/selfai/daily_report.txt
```

### 3. Log Rotation

Clean old logs regularly:

```bash
# Weekly log cleanup
0 0 * * 0 python /path/to/manage.py clear-logs --days 14
```

### 4. Performance Analysis

Export and analyze telemetry data:

```bash
python manage.py telemetry --export --file reports/$(date +%Y%m%d).txt
```

### 5. Health Checks

Before important operations:

```python
from src.cli import check
from config_loader import load_configuration

# Ensure backends are healthy
try:
    check(verbose=False)
except SystemExit:
    print("Backends unhealthy - aborting operation")
    sys.exit(1)

# Proceed with operation
...
```

---

## 🧪 Testing

### Unit Tests

```python
import pytest
from src.core.telemetry import TelemetryManager

def test_telemetry():
    # Reset singleton for testing
    TelemetryManager.reset_instance()

    telemetry = TelemetryManager.get_instance(enabled=True)

    # Record some metrics
    telemetry.record_latency("TestProvider", 0.5, success=True)
    telemetry.record_token_usage("TestProvider", 100, 50)

    # Verify
    stats = telemetry.get_statistics()
    assert stats['providers']['TestProvider']['requests'] == 1
    assert stats['providers']['TestProvider']['avg_latency'] == 0.5
```

### Integration Tests

```bash
# Test all CLI commands
python manage.py check
python manage.py config
python manage.py telemetry
python manage.py version
```

---

## 🐛 Troubleshooting

### Issue: "typer not found"

**Solution**: Install dependencies

```bash
pip install typer rich
```

### Issue: "Telemetry not tracking"

**Solution**: Check configuration

```python
config = load_configuration()
print(config.system.enable_telemetry)  # Should be True
```

### Issue: "Stats file not saving"

**Solution**: Check permissions

```bash
mkdir -p telemetry
chmod 755 telemetry
```

### Issue: "CLI colors not showing"

**Solution**: Rich library may need color support

```bash
# Force color output
export FORCE_COLOR=1
python manage.py check
```

---

## 📚 API Reference

See inline docstrings in:
- `src/core/telemetry.py` - TelemetryManager, decorators
- `src/cli.py` - CLI commands

---

## 🎯 Future Enhancements

Planned features:
- Prometheus metrics export
- Grafana dashboard templates
- Real-time monitoring WebSocket API
- Alert system for failures
- Database backend (SQLite/PostgreSQL)

---

**Last Updated**: 2025-01-19
**Version**: 1.0.0
