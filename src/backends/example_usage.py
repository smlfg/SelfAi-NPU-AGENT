"""Example usage of the refactored LLM backend abstraction layer.

This script demonstrates how to use the new clean backend architecture with
automatic fallback from NPU to CPU.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def example_basic_usage():
    """Basic usage example: Create providers and generate a response."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Usage with Automatic Fallback")
    print("=" * 70)

    from src.backends import BackendManager, NPUProvider, CPUProvider

    # Create NPU provider (will fail if AnythingLLM not running)
    try:
        npu = NPUProvider(
            api_key="YOUR_API_KEY",  # Replace with actual key
            base_url="http://localhost:3001/api/v1",
            workspace_slug="main",
        )
        print("✓ NPU provider initialized")
    except Exception as e:
        print(f"✗ NPU provider failed: {e}")
        npu = None

    # Create CPU provider (fallback)
    try:
        cpu = CPUProvider(
            model_path=str(project_root / "models" / "Phi-3-mini-4k-instruct.Q4_K_M.gguf"),
            n_ctx=4096,
        )
        print("✓ CPU provider initialized")
    except Exception as e:
        print(f"✗ CPU provider failed: {e}")
        return

    # Create manager with available providers
    providers = [p for p in [npu, cpu] if p is not None]
    if not providers:
        print("✗ No providers available!")
        return

    manager = BackendManager(providers=providers)
    print(f"\n✓ BackendManager created with {len(providers)} provider(s)")

    # Generate response
    print("\nGenerating response...")
    try:
        response = manager.generate_response(
            system_prompt="You are a helpful Python programming assistant.",
            user_prompt="Explain what a list comprehension is in one sentence.",
        )
        print(f"\n✓ Response:\n{response}")
        print(f"\n✓ Used provider: {manager.get_active_provider().provider_name}")
    except Exception as e:
        print(f"✗ Generation failed: {e}")


def example_streaming():
    """Streaming response example."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Streaming Response")
    print("=" * 70)

    from src.backends import BackendManager, CPUProvider

    # Use CPU provider for streaming demo
    try:
        cpu = CPUProvider(
            model_path=str(project_root / "models" / "Phi-3-mini-4k-instruct.Q4_K_M.gguf"),
        )
    except Exception as e:
        print(f"✗ CPU provider failed: {e}")
        return

    manager = BackendManager(providers=[cpu])

    print("\nStreaming response (word by word):")
    print("-" * 70)
    try:
        for chunk in manager.stream_generate_response(
            system_prompt="You are a creative writer.",
            user_prompt="Write a haiku about artificial intelligence.",
        ):
            print(chunk, end="", flush=True)
        print("\n" + "-" * 70)
    except Exception as e:
        print(f"\n✗ Streaming failed: {e}")


def example_provider_management():
    """Provider management example."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Provider Management")
    print("=" * 70)

    from src.backends import BackendManager, CPUProvider, NPUProvider

    # Create providers
    providers = []

    try:
        npu = NPUProvider(
            api_key="test-key",
            base_url="http://localhost:3001/api/v1",
            workspace_slug="main",
        )
        providers.append(npu)
    except Exception:
        pass

    try:
        cpu = CPUProvider(
            model_path=str(project_root / "models" / "Phi-3-mini-4k-instruct.Q4_K_M.gguf"),
        )
        providers.append(cpu)
    except Exception:
        pass

    if not providers:
        print("✗ No providers available!")
        return

    manager = BackendManager(providers=providers)

    # List all providers
    print("\nRegistered Providers:")
    print("-" * 70)
    for info in manager.list_providers():
        active_marker = "→" if info["active"] else " "
        print(f"{active_marker} [{info['index']}] {info['name']} ({info['type']})")

    # Health check
    print("\nHealth Check Results:")
    print("-" * 70)
    health = manager.healthcheck_all()
    for name, is_healthy in health.items():
        status = "✓ Healthy" if is_healthy else "✗ Unhealthy"
        print(f"{name}: {status}")

    # Switch provider
    if len(providers) > 1:
        print("\nSwitching to second provider...")
        manager.set_active_provider(1)
        active = manager.get_active_provider()
        print(f"✓ Active provider is now: {active.provider_name}")


def example_error_handling():
    """Error handling example."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Error Handling")
    print("=" * 70)

    from src.backends import BackendManager, BackendError

    # Create manager with no providers (will fail)
    manager = BackendManager(providers=[])

    print("\nAttempting to generate with no providers...")
    try:
        response = manager.generate_response(
            system_prompt="Test",
            user_prompt="Test",
        )
        print(f"Response: {response}")
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    except BackendError as e:
        print(f"✓ Caught backend error: {e}")


def example_configuration_integration():
    """Example of integrating with config_loader."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Configuration Integration")
    print("=" * 70)

    try:
        from config_loader import load_configuration
        from src.backends import BackendManager, NPUProvider, CPUProvider

        # Load configuration
        print("\nLoading configuration...")
        config = load_configuration()
        print("✓ Configuration loaded")

        # Create providers from config
        providers = []

        # NPU provider from config
        try:
            npu = NPUProvider(
                api_key=config.npu_provider.api_key,
                base_url=config.npu_provider.base_url,
                workspace_slug=config.npu_provider.workspace_slug,
                stream=getattr(config.system, "streaming_enabled", True),
                timeout=getattr(config.system, "stream_timeout", 60.0),
            )
            providers.append(npu)
            print("✓ NPU provider created from config")
        except Exception as e:
            print(f"✗ NPU provider failed: {e}")

        # CPU provider from config
        try:
            cpu = CPUProvider(
                model_path=config.cpu_fallback.model_path,
                n_ctx=getattr(config.cpu_fallback, "n_ctx", 4096),
                n_gpu_layers=getattr(config.cpu_fallback, "n_gpu_layers", 0),
            )
            providers.append(cpu)
            print("✓ CPU provider created from config")
        except Exception as e:
            print(f"✗ CPU provider failed: {e}")

        if providers:
            manager = BackendManager(providers=providers)
            print(f"\n✓ BackendManager ready with {len(providers)} provider(s)")
            print(f"Active: {manager.get_active_provider().provider_name}")
        else:
            print("\n✗ No providers could be initialized")

    except Exception as e:
        print(f"✗ Configuration integration failed: {e}")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "LLM Backend Abstraction Layer - Examples" + " " * 18 + "║")
    print("╚" + "=" * 68 + "╝")

    # Run examples
    example_basic_usage()
    example_streaming()
    example_provider_management()
    example_error_handling()
    example_configuration_integration()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
