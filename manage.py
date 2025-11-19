#!/usr/bin/env python3
"""Management CLI entry point for SelfAI NPU Agent.

This script provides a unified command-line interface for managing,
monitoring, and maintaining the SelfAI NPU Agent system.

Usage:
    python manage.py check                    # Run connectivity tests
    python manage.py config                   # Show configuration
    python manage.py clear-logs               # Clean old logs
    python manage.py telemetry                # View performance metrics
    python manage.py version                  # Show version info
    python manage.py --help                   # Show all commands

For detailed help on any command:
    python manage.py <command> --help

Examples:
    python manage.py check --verbose
    python manage.py config --show-secrets
    python manage.py clear-logs --days 30 --dry-run
    python manage.py telemetry --export
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Import and run CLI
try:
    from src.cli import main

    if __name__ == "__main__":
        main()

except ImportError as exc:
    print(f"Error: {exc}")
    print("\nRequired dependencies not found. Install with:")
    print("  pip install typer rich")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\nInterrupted by user.")
    sys.exit(130)
except Exception as exc:
    print(f"Unexpected error: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
