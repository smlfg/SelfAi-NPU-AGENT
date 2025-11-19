#!/usr/bin/env python3
"""Test script for verifying the refactored infrastructure.

This script tests:
1. Configuration loading and validation
2. Logging system setup
3. Exception handling

Run this after installing requirements-refactored.txt to verify the setup.

Usage:
    python test_infrastructure.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all modules can be imported."""
    print("=" * 70)
    print("TEST 1: Module Imports")
    print("=" * 70)

    try:
        from src.core import (
            load_settings,
            Settings,
            setup_logging,
            get_logger,
            SelfAIException,
            NPUConnectionError,
        )
        print("✓ All core modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        print("\nPlease install dependencies:")
        print("  pip install -r requirements-refactored.txt")
        return False


def test_logging():
    """Test logging system."""
    print("\n" + "=" * 70)
    print("TEST 2: Logging System")
    print("=" * 70)

    try:
        from src.core import setup_logging, get_logger, log_performance
        import time

        # Setup logging
        setup_logging(log_level="INFO", console_colors=True)
        logger = get_logger(__name__)

        # Test basic logging
        logger.debug("This is a debug message (should not appear)")
        logger.info("This is an info message", extra={"test": True})
        logger.warning("This is a warning message")

        # Test performance logging
        start = time.time()
        time.sleep(0.1)  # Simulate work
        log_performance(
            logger,
            operation="test_operation",
            duration_seconds=time.time() - start,
            backend="test",
            tokens=123,
        )

        print("✓ Logging system works correctly")
        return True
    except Exception as e:
        print(f"✗ Logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exceptions():
    """Test exception hierarchy."""
    print("\n" + "=" * 70)
    print("TEST 3: Exception Handling")
    print("=" * 70)

    try:
        from src.core import (
            SelfAIException,
            NPUConnectionError,
            FallbackTriggered,
            ConfigurationError,
        )

        # Test basic exception
        try:
            raise NPUConnectionError(
                "Test connection error",
                context={"url": "http://localhost:3001", "timeout": 30},
            )
        except NPUConnectionError as e:
            assert e.backend_name == "npu"
            assert "url" in e.context
            print(f"✓ NPUConnectionError works: {e}")

        # Test fallback exception
        try:
            raise FallbackTriggered("anythingllm", "qnn", reason="timeout")
        except FallbackTriggered as e:
            assert e.from_backend == "anythingllm"
            assert e.to_backend == "qnn"
            print(f"✓ FallbackTriggered works: {e}")

        # Test exception chaining
        try:
            try:
                raise ValueError("Original error")
            except ValueError as original:
                raise ConfigurationError(
                    "Wrapped error",
                    context={"key": "test"},
                    original_error=original,
                ) from original
        except ConfigurationError as e:
            assert e.original_error is not None
            assert isinstance(e.original_error, ValueError)
            print(f"✓ Exception chaining works: {e}")

        print("✓ All exception tests passed")
        return True
    except Exception as e:
        print(f"✗ Exception test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration():
    """Test configuration loading."""
    print("\n" + "=" * 70)
    print("TEST 4: Configuration Loading")
    print("=" * 70)

    try:
        from src.core import load_settings, get_config_summary
        from src.core.exceptions import ConfigurationError

        # Try to load settings
        try:
            settings = load_settings()
            print("✓ Configuration loaded successfully")

            # Display summary
            summary = get_config_summary(settings)
            print(f"\nConfiguration Summary:")
            print(f"  NPU Base URL: {summary['npu_provider']['base_url']}")
            print(f"  NPU Workspace: {summary['npu_provider']['workspace_slug']}")
            print(f"  API Key Set: {summary['npu_provider']['api_key_set']}")
            print(f"  CPU Model: {summary['cpu_fallback']['model_path']}")
            print(f"  Default Agent: {summary['agent_config']['default_agent']}")
            print(f"  Planner Enabled: {summary['planner']['enabled']}")
            print(f"  Planner Providers: {summary['planner']['providers_count']}")

            # Test type safety
            assert isinstance(settings.npu_provider.base_url, str)
            assert isinstance(settings.cpu_fallback.n_ctx, int)
            assert isinstance(settings.system.streaming_enabled, bool)
            print("\n✓ Type validation works correctly")

            return True

        except ConfigurationError as e:
            print(f"⚠ Configuration error (expected if config.yaml or .env not set up):")
            print(f"  {e}")
            print("\nTo fix:")
            print("  1. Copy config.yaml.template to config.yaml")
            print("  2. Copy .env.example to .env")
            print("  3. Set API_KEY in .env")
            return False

    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pydantic_validation():
    """Test Pydantic validation."""
    print("\n" + "=" * 70)
    print("TEST 5: Pydantic Validation")
    print("=" * 70)

    try:
        from src.core.config import NPUProviderSettings, CPUFallbackSettings
        from pydantic import ValidationError

        # Test valid configuration
        npu = NPUProviderSettings(
            api_key="test-key",
            base_url="http://localhost:3001/api/v1",
            workspace_slug="main",
        )
        print(f"✓ Valid NPU config created: {npu.base_url}")

        # Test invalid URL (should fail)
        try:
            invalid_npu = NPUProviderSettings(
                api_key="test-key",
                base_url="localhost:3001",  # Missing http://
                workspace_slug="main",
            )
            print("✗ Validation should have failed for invalid URL")
            return False
        except ValidationError as e:
            print(f"✓ Validation correctly rejected invalid URL")

        # Test invalid timeout
        from src.core.config import ProviderSettings

        try:
            invalid_provider = ProviderSettings(
                name="test",
                type="local_ollama",
                base_url="http://localhost:11434",
                model="gemma3:1b",
                timeout=-10,  # Invalid negative timeout
            )
            print("✗ Validation should have failed for negative timeout")
            return False
        except ValidationError as e:
            print(f"✓ Validation correctly rejected negative timeout")

        print("✓ All Pydantic validation tests passed")
        return True

    except Exception as e:
        print(f"✗ Pydantic validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("REFACTORED INFRASTRUCTURE TEST SUITE")
    print("=" * 70)

    results = []

    # Run tests
    results.append(("Module Imports", test_imports()))

    # Only run other tests if imports succeed
    if results[0][1]:
        results.append(("Logging System", test_logging()))
        results.append(("Exception Handling", test_exceptions()))
        results.append(("Configuration Loading", test_configuration()))
        results.append(("Pydantic Validation", test_pydantic_validation()))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} | {test_name}")

    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n🎉 All tests passed! Infrastructure is working correctly.")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
