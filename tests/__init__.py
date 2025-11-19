"""
SelfAI NPU Agent Test Suite

This package contains comprehensive tests for the SelfAI NPU Agent project.

Test Organization:
    - conftest.py: Shared fixtures and mocks
    - test_config_loader.py: Configuration loading and validation
    - test_fallback.py: Backend fallback mechanism
    - test_pipeline.py: Planner and DPPM logic
    - test_execution_dispatcher.py: Subtask execution
    - fixtures/: Additional test data and fixtures

Running Tests:
    # All tests
    pytest

    # Specific test file
    pytest tests/test_fallback.py

    # Specific test
    pytest tests/test_fallback.py::test_fallback_chain_all_backends_succeed

    # With coverage
    pytest --cov=selfai --cov=config_loader --cov-report=html

    # Verbose output
    pytest -v

    # Show print statements
    pytest -s
"""
