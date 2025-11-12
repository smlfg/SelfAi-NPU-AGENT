"""
Pytest configuration for integration tests
"""

import pytest
import subprocess
import time
import os


@pytest.fixture(scope="session", autouse=True)
def ensure_service_running():
    """
    Ensure the dashboard service is running for integration tests.
    This fixture runs once per test session.
    """
    # Check if running in CI or if we should start the service
    if os.environ.get("CI") == "true":
        # In CI, assume service is already running
        yield
        return

    # Check if service is already running
    try:
        import requests
        response = requests.get("http://localhost:11000/api/status", timeout=2)
        if response.status_code == 200:
            print("\nService already running, using existing instance")
            yield
            return
    except:
        pass

    # Start the service
    print("\nStarting dashboard service for tests...")
    process = subprocess.Popen(
        ["python", "-m", "selfai.dashboard.dashboard_server", "--host", "0.0.0.0", "--port", "11000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for service to be ready
    max_wait = 30
    for i in range(max_wait):
        try:
            import requests
            response = requests.get("http://localhost:11000/api/status", timeout=2)
            if response.status_code == 200:
                print("Service started successfully")
                break
        except:
            time.sleep(1)
    else:
        process.kill()
        pytest.fail("Service did not start within timeout")

    yield

    # Cleanup
    print("\nStopping dashboard service...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
