"""Example: Integrating telemetry with backend providers.

This script demonstrates how to integrate the telemetry system with
the LLM backend abstraction layer for automatic performance tracking.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def example_basic_telemetry():
    """Example 1: Basic telemetry usage."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Telemetry Usage")
    print("=" * 70)

    from src.core.telemetry import TelemetryManager

    # Get singleton instance
    telemetry = TelemetryManager.get_instance(
        stats_file=Path("telemetry/demo_stats.json"),
        enabled=True,
    )

    # Simulate some backend calls
    print("\nSimulating backend calls...")

    # NPU calls (faster)
    for i in range(10):
        telemetry.record_latency("NPUProvider", 0.3 + (i * 0.01), success=True)
        telemetry.record_token_usage("NPUProvider", 100, 50)

    # CPU calls (slower)
    for i in range(5):
        telemetry.record_latency("CPUProvider", 0.5 + (i * 0.02), success=True)
        telemetry.record_token_usage("CPUProvider", 100, 50)

    # Get statistics
    stats = telemetry.get_statistics()
    print(f"\nTotal requests: {stats['totals']['requests']}")
    print(f"NPU avg latency: {stats['providers']['NPUProvider']['avg_latency']:.3f}s")
    print(f"CPU avg latency: {stats['providers']['CPUProvider']['avg_latency']:.3f}s")

    # Compare providers
    comparison = telemetry.compare_providers()
    if comparison.get('speedup'):
        print(f"\nNPU is {comparison['speedup']:.2f}x faster than CPU!")
        print(f"Performance gain: {comparison['performance_gain_percent']:.1f}%")


def example_decorator_usage():
    """Example 2: Using telemetry decorators."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Telemetry Decorators")
    print("=" * 70)

    from src.core.telemetry import track_latency, track_token_usage, TelemetryManager
    import time
    import random

    # Reset for clean demo
    TelemetryManager.reset_instance()
    telemetry = TelemetryManager.get_instance(enabled=True)

    @track_latency("CustomBackend")
    def simulate_llm_call(prompt: str) -> str:
        """Simulate an LLM call with random latency."""
        time.sleep(random.uniform(0.2, 0.4))
        return f"Response to: {prompt}"

    @track_token_usage("CustomBackend")
    def generate_with_tokens(prompt: str) -> dict:
        """Generate response with token counts."""
        return {
            "response": simulate_llm_call(prompt),
            "input_tokens": len(prompt.split()) * 3,
            "output_tokens": random.randint(20, 50),
        }

    # Make some calls
    print("\nMaking decorated function calls...")
    for i in range(5):
        result = generate_with_tokens(f"Test prompt {i}")
        print(f"  Call {i+1}: {result['output_tokens']} tokens")

    # Check stats
    stats = telemetry.get_statistics()
    backend_stats = stats['providers']['CustomBackend']
    print(f"\nCustomBackend statistics:")
    print(f"  Requests: {backend_stats['requests']}")
    print(f"  Avg latency: {backend_stats['avg_latency']:.3f}s")
    print(f"  Total tokens: {backend_stats['total_tokens']}")


def example_backend_integration():
    """Example 3: Full backend integration with telemetry."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Backend Integration")
    print("=" * 70)

    try:
        from src.backends import BackendManager, CPUProvider
        from src.core.telemetry import TelemetryManager
        from config_loader import load_configuration

        # Load configuration
        print("\nLoading configuration...")
        config = load_configuration()

        # Initialize telemetry
        telemetry = TelemetryManager.get_instance(
            enabled=getattr(config.system, 'enable_telemetry', True)
        )
        print(f"Telemetry enabled: {telemetry.enabled}")

        # Create provider (with telemetry tracking)
        print("\nInitializing CPU provider...")
        cpu = CPUProvider(
            model_path=str(project_root / "models" / config.cpu_fallback.model_path),
            n_ctx=getattr(config.cpu_fallback, 'n_ctx', 4096),
        )

        # Create manager
        manager = BackendManager(providers=[cpu])

        # Generate responses (telemetry tracks automatically if decorators are added)
        print("\nGenerating responses...")
        for i in range(3):
            try:
                response = manager.generate_response(
                    system_prompt="You are a helpful assistant.",
                    user_prompt=f"Count to {i+1}",
                )
                print(f"  Response {i+1}: {response[:50]}...")
            except Exception as e:
                print(f"  Error: {e}")

        # View statistics
        stats = telemetry.get_statistics()
        print(f"\nTelemetry statistics:")
        print(f"  Total requests: {stats['totals']['requests']}")
        if stats['totals']['requests'] > 0:
            print(f"  Success rate: {stats['totals']['success_rate']:.1f}%")
            print(f"  Avg latency: {stats['totals']['avg_latency']:.3f}s")

    except FileNotFoundError as e:
        print(f"\nConfiguration error: {e}")
        print("Please create config.yaml from config.yaml.template")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


def example_export_report():
    """Example 4: Export performance report."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Export Performance Report")
    print("=" * 70)

    from src.core.telemetry import TelemetryManager

    telemetry = TelemetryManager.get_instance()

    # Export to file
    output_file = Path("telemetry/example_report.txt")
    report = telemetry.export_report(output_file)

    print(f"\nReport exported to: {output_file}")
    print("\nReport preview:")
    print("-" * 70)
    print(report)
    print("-" * 70)


def example_cli_integration():
    """Example 5: CLI integration."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: CLI Integration")
    print("=" * 70)

    print("\nThe management CLI provides these commands:")
    print("  python manage.py check           - Test backend connectivity")
    print("  python manage.py config          - Show configuration")
    print("  python manage.py telemetry       - View metrics")
    print("  python manage.py clear-logs      - Clean log files")
    print("  python manage.py version         - Show version")
    print("\nTry running: python manage.py --help")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Telemetry Integration Examples" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")

    # Run examples
    example_basic_telemetry()
    example_decorator_usage()
    example_backend_integration()
    example_export_report()
    example_cli_integration()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
