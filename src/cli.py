"""Management CLI for SelfAI NPU Agent.

This module provides a command-line interface for managing and monitoring
the SelfAI NPU Agent system using the Typer framework.

Commands:
    - check: Run connectivity tests for configured backends
    - config show: Display current configuration (with masked secrets)
    - clear-logs: Rotate and clean old log files
    - telemetry: View performance metrics and statistics
"""

import json
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'typer' and 'rich' not installed. Install with: pip install typer rich")

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


# Create CLI app
app = typer.Typer(
    name="selfai",
    help="SelfAI NPU Agent Management CLI",
    add_completion=False,
)

# Console for rich output
console = Console() if RICH_AVAILABLE else None


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret value, showing only the last few characters.

    Args:
        value: The secret value to mask.
        show_chars: Number of characters to show at the end.

    Returns:
        Masked string (e.g., "********abc123").
    """
    if not value or len(value) <= show_chars:
        return "********"
    return "*" * 8 + value[-show_chars:]


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Run connectivity tests for all configured backends.

    This command tests:
    - AnythingLLM NPU backend connectivity
    - QNN model availability
    - CPU fallback model availability
    - Ollama planner/merge endpoints (if configured)
    """
    if not RICH_AVAILABLE:
        print("This command requires 'typer' and 'rich'. Install with: pip install typer rich")
        raise typer.Exit(1)

    console.print("\n[bold blue]🔍 Running Backend Connectivity Checks[/bold blue]\n")

    try:
        from config_loader import load_configuration
        from src.backends import NPUProvider, QNNProvider, CPUProvider
        from src.backends.qnn_provider import find_qnn_models

        config = load_configuration()
        results = []

        # Test AnythingLLM (NPU)
        console.print("[yellow]⏳ Testing AnythingLLM (NPU)...[/yellow]")
        try:
            npu = NPUProvider(
                api_key=config.npu_provider.api_key,
                base_url=config.npu_provider.base_url,
                workspace_slug=config.npu_provider.workspace_slug,
            )
            health = npu.healthcheck()
            results.append({
                "name": "AnythingLLM (NPU)",
                "status": "✅ Healthy" if health else "❌ Unhealthy",
                "details": f"URL: {config.npu_provider.base_url}",
            })
            if verbose:
                console.print(f"  [green]✓[/green] Connected to {config.npu_provider.base_url}")
        except Exception as exc:
            results.append({
                "name": "AnythingLLM (NPU)",
                "status": "❌ Failed",
                "details": str(exc),
            })
            if verbose:
                console.print(f"  [red]✗[/red] Error: {exc}")

        # Test QNN Models
        console.print("[yellow]⏳ Checking QNN models...[/yellow]")
        try:
            models_dir = project_root / "models"
            qnn_models = find_qnn_models(models_dir)
            if qnn_models:
                results.append({
                    "name": "QNN Models",
                    "status": f"✅ Found {len(qnn_models)}",
                    "details": f"Models: {', '.join(m.name for m in qnn_models)}",
                })
                if verbose:
                    for model in qnn_models:
                        console.print(f"  [green]✓[/green] Found: {model.name}")
            else:
                results.append({
                    "name": "QNN Models",
                    "status": "⚠️  Not found",
                    "details": f"Search path: {models_dir}",
                })
        except Exception as exc:
            results.append({
                "name": "QNN Models",
                "status": "❌ Error",
                "details": str(exc),
            })

        # Test CPU Model
        console.print("[yellow]⏳ Checking CPU fallback model...[/yellow]")
        try:
            cpu_model_path = Path(config.cpu_fallback.model_path)
            if cpu_model_path.exists():
                results.append({
                    "name": "CPU Fallback",
                    "status": "✅ Available",
                    "details": f"Model: {cpu_model_path.name}",
                })
                if verbose:
                    console.print(f"  [green]✓[/green] Found: {cpu_model_path}")
            else:
                results.append({
                    "name": "CPU Fallback",
                    "status": "❌ Not found",
                    "details": f"Expected: {cpu_model_path}",
                })
        except Exception as exc:
            results.append({
                "name": "CPU Fallback",
                "status": "❌ Error",
                "details": str(exc),
            })

        # Test Ollama (if configured)
        if hasattr(config, 'planner') and config.planner and config.planner.enabled:
            console.print("[yellow]⏳ Testing Ollama planner...[/yellow]")
            try:
                import httpx
                for provider in config.planner.providers:
                    try:
                        with httpx.Client(timeout=5.0) as client:
                            response = client.get(f"{provider.base_url}/api/tags")
                            response.raise_for_status()
                        results.append({
                            "name": f"Ollama ({provider.name})",
                            "status": "✅ Connected",
                            "details": f"Model: {provider.model}",
                        })
                        if verbose:
                            console.print(f"  [green]✓[/green] Connected to {provider.base_url}")
                    except Exception as exc:
                        results.append({
                            "name": f"Ollama ({provider.name})",
                            "status": "❌ Failed",
                            "details": str(exc),
                        })
            except Exception as exc:
                results.append({
                    "name": "Ollama Planner",
                    "status": "❌ Error",
                    "details": str(exc),
                })

        # Display results table
        console.print()
        table = Table(title="Backend Connectivity Results", show_header=True, header_style="bold magenta")
        table.add_column("Backend", style="cyan", width=25)
        table.add_column("Status", width=20)
        table.add_column("Details", width=50)

        for result in results:
            table.add_row(result["name"], result["status"], result["details"])

        console.print(table)
        console.print()

        # Summary
        healthy = sum(1 for r in results if "✅" in r["status"])
        total = len(results)
        if healthy == total:
            console.print(f"[bold green]✅ All {total} backends are healthy![/bold green]\n")
        else:
            console.print(f"[bold yellow]⚠️  {healthy}/{total} backends are healthy[/bold yellow]\n")

    except Exception as exc:
        console.print(f"[bold red]❌ Error running checks: {exc}[/bold red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command("config")
def config_show(
    show_secrets: bool = typer.Option(False, "--show-secrets", help="Show unmasked API keys (dangerous!)"),
) -> None:
    """Display current configuration with masked secrets."""
    if not RICH_AVAILABLE:
        print("This command requires 'typer' and 'rich'. Install with: pip install typer rich")
        raise typer.Exit(1)

    console.print("\n[bold blue]⚙️  Current Configuration[/bold blue]\n")

    try:
        from config_loader import load_configuration

        config = load_configuration()

        # NPU Provider
        console.print(Panel.fit(
            f"[cyan]Base URL:[/cyan] {config.npu_provider.base_url}\n"
            f"[cyan]Workspace:[/cyan] {config.npu_provider.workspace_slug}\n"
            f"[cyan]API Key:[/cyan] {config.npu_provider.api_key if show_secrets else mask_secret(config.npu_provider.api_key)}",
            title="[bold]NPU Provider (AnythingLLM)[/bold]",
            border_style="green",
        ))

        # CPU Fallback
        console.print(Panel.fit(
            f"[cyan]Model Path:[/cyan] {config.cpu_fallback.model_path}\n"
            f"[cyan]Context Size:[/cyan] {getattr(config.cpu_fallback, 'n_ctx', 4096)}\n"
            f"[cyan]GPU Layers:[/cyan] {getattr(config.cpu_fallback, 'n_gpu_layers', 0)}",
            title="[bold]CPU Fallback[/bold]",
            border_style="yellow",
        ))

        # System Settings
        streaming = getattr(config.system, 'streaming_enabled', False)
        telemetry = getattr(config.system, 'enable_telemetry', True)
        console.print(Panel.fit(
            f"[cyan]Streaming:[/cyan] {'✅ Enabled' if streaming else '❌ Disabled'}\n"
            f"[cyan]Telemetry:[/cyan] {'✅ Enabled' if telemetry else '❌ Disabled'}\n"
            f"[cyan]Timeout:[/cyan] {getattr(config.system, 'stream_timeout', 60.0)}s",
            title="[bold]System Settings[/bold]",
            border_style="blue",
        ))

        # Planner (if configured)
        if hasattr(config, 'planner') and config.planner:
            if config.planner.enabled:
                providers_info = "\n".join([
                    f"[cyan]• {p.name}:[/cyan] {p.model} @ {p.base_url}"
                    for p in config.planner.providers
                ])
                console.print(Panel.fit(
                    f"[cyan]Enabled:[/cyan] ✅ Yes\n{providers_info}",
                    title="[bold]Planner Configuration[/bold]",
                    border_style="magenta",
                ))

        # Agent Config
        if hasattr(config, 'agent_config') and config.agent_config:
            default_agent = getattr(config.agent_config, 'default_agent', 'N/A')
            console.print(Panel.fit(
                f"[cyan]Default Agent:[/cyan] {default_agent}",
                title="[bold]Agent Configuration[/bold]",
                border_style="cyan",
            ))

        console.print()

        if not show_secrets:
            console.print("[dim]💡 Tip: Use --show-secrets to display unmasked API keys[/dim]\n")

    except FileNotFoundError:
        console.print("[bold red]❌ Configuration file not found![/bold red]")
        console.print("[yellow]💡 Create config.yaml from config.yaml.template[/yellow]\n")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[bold red]❌ Error loading configuration: {exc}[/bold red]\n")
        raise typer.Exit(1)


@app.command()
def clear_logs(
    directory: str = typer.Option("logs", "--dir", "-d", help="Log directory to clean"),
    older_than_days: int = typer.Option(7, "--days", help="Delete logs older than N days"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted without deleting"),
) -> None:
    """Rotate and clean old log files."""
    if not RICH_AVAILABLE:
        print("This command requires 'typer' and 'rich'. Install with: pip install typer rich")
        raise typer.Exit(1)

    from datetime import datetime, timedelta

    log_dir = Path(directory)

    if not log_dir.exists():
        console.print(f"[yellow]⚠️  Log directory not found: {log_dir}[/yellow]\n")
        return

    console.print(f"\n[bold blue]🧹 Cleaning Logs[/bold blue]")
    console.print(f"Directory: {log_dir.absolute()}")
    console.print(f"Older than: {older_than_days} days")
    if dry_run:
        console.print("[yellow]Mode: DRY RUN (no files will be deleted)[/yellow]\n")
    else:
        console.print()

    cutoff_date = datetime.now() - timedelta(days=older_than_days)
    deleted_count = 0
    deleted_size = 0

    log_files = list(log_dir.rglob("*.log")) + list(log_dir.rglob("*.log.*"))

    for log_file in log_files:
        if log_file.is_file():
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff_date:
                size = log_file.stat().st_size
                deleted_size += size

                if dry_run:
                    console.print(f"[yellow]Would delete:[/yellow] {log_file.name} ({size:,} bytes, {mtime.strftime('%Y-%m-%d')})")
                else:
                    try:
                        log_file.unlink()
                        console.print(f"[red]Deleted:[/red] {log_file.name} ({size:,} bytes)")
                        deleted_count += 1
                    except OSError as exc:
                        console.print(f"[bold red]Error deleting {log_file.name}: {exc}[/bold red]")

    console.print()
    if dry_run:
        console.print(f"[bold yellow]Would delete {len([f for f in log_files if datetime.fromtimestamp(f.stat().st_mtime) < cutoff_date])} files ({deleted_size:,} bytes)[/bold yellow]\n")
    else:
        console.print(f"[bold green]✅ Deleted {deleted_count} files ({deleted_size:,} bytes)[/bold green]\n")


@app.command()
def telemetry(
    export: bool = typer.Option(False, "--export", "-e", help="Export full report to file"),
    clear: bool = typer.Option(False, "--clear", help="Clear all telemetry data"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Export file path"),
) -> None:
    """View performance metrics and statistics."""
    if not RICH_AVAILABLE:
        print("This command requires 'typer' and 'rich'. Install with: pip install typer rich")
        raise typer.Exit(1)

    try:
        from src.core.telemetry import TelemetryManager

        telemetry_mgr = TelemetryManager.get_instance()

        if clear:
            confirm = typer.confirm("Are you sure you want to clear all telemetry data?")
            if confirm:
                telemetry_mgr.clear_metrics()
                console.print("[bold green]✅ Telemetry data cleared[/bold green]\n")
            else:
                console.print("[yellow]Cancelled[/yellow]\n")
            return

        stats = telemetry_mgr.get_statistics()

        if not stats.get("enabled"):
            console.print("[bold yellow]⚠️  Telemetry is disabled[/bold yellow]\n")
            return

        console.print("\n[bold blue]📊 Performance Metrics[/bold blue]\n")

        # Overall statistics
        totals = stats.get("totals", {})
        console.print(Panel.fit(
            f"[cyan]Total Requests:[/cyan] {totals.get('requests', 0)}\n"
            f"[cyan]Successes:[/cyan] {totals.get('successes', 0)} "
            f"({totals.get('success_rate', 0):.1f}%)\n"
            f"[cyan]Failures:[/cyan] {totals.get('failures', 0)}\n"
            f"[cyan]Avg Latency:[/cyan] {totals.get('avg_latency', 0):.3f}s\n"
            f"[cyan]Total Tokens:[/cyan] {totals.get('total_tokens', 0):,}",
            title="[bold]Overall Statistics[/bold]",
            border_style="green",
        ))

        # Per-provider statistics
        providers = stats.get("providers", {})
        if providers:
            table = Table(title="Provider Performance", show_header=True, header_style="bold magenta")
            table.add_column("Provider", style="cyan")
            table.add_column("Requests", justify="right")
            table.add_column("Success Rate", justify="right")
            table.add_column("Avg Latency", justify="right")
            table.add_column("Tokens", justify="right")

            for name, data in providers.items():
                table.add_row(
                    name,
                    str(data.get("requests", 0)),
                    f"{data.get('success_rate', 0):.1f}%",
                    f"{data.get('avg_latency', 0):.3f}s",
                    f"{data.get('total_tokens', 0):,}",
                )

            console.print(table)

        # Performance comparison
        comparison = telemetry_mgr.compare_providers()
        if comparison.get("speedup"):
            console.print()
            console.print(Panel.fit(
                f"[cyan]NPU Latency:[/cyan] {comparison['npu_latency']:.3f}s\n"
                f"[cyan]CPU Latency:[/cyan] {comparison['cpu_latency']:.3f}s\n"
                f"[cyan]Speedup:[/cyan] [bold green]{comparison['speedup']:.2f}x[/bold green]\n"
                f"[cyan]Performance Gain:[/cyan] [bold green]{comparison['performance_gain_percent']:.1f}%[/bold green]",
                title="[bold]NPU vs CPU Performance[/bold]",
                border_style="green",
            ))

        console.print()

        # Export report
        if export:
            output_path = Path(file) if file else Path("telemetry/performance_report.txt")
            report = telemetry_mgr.export_report(output_path)
            console.print(f"[bold green]✅ Report exported to: {output_path}[/bold green]\n")
        else:
            console.print("[dim]💡 Tip: Use --export to save a full report[/dim]\n")

    except Exception as exc:
        console.print(f"[bold red]❌ Error: {exc}[/bold red]\n")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Display version information."""
    if not RICH_AVAILABLE:
        print("SelfAI NPU Agent v1.0.0")
        return

    console.print()
    console.print(Panel.fit(
        "[bold cyan]SelfAI NPU Agent[/bold cyan]\n"
        "[dim]Version:[/dim] 1.0.0\n"
        "[dim]Backend Abstraction:[/dim] v1.0.0\n"
        "[dim]Telemetry:[/dim] Enabled",
        border_style="blue",
    ))
    console.print()


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
