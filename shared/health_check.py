"""
Shared Health Check API
Provides health checking functionality for all agent playbooks.
"""

import requests
import sys
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class HealthCheckConfig:
    """Health check configuration"""
    port: int
    endpoint: str = "/api/health"
    timeout: int = 10
    retries: int = 3
    retry_delay: int = 2


class HealthChecker:
    """
    Universal health checker for all agent services.

    Usage:
        checker = HealthChecker(port=11000, endpoint="/api/health")
        is_healthy, message = checker.check()
        if is_healthy:
            print("Service is healthy")
    """

    def __init__(
        self,
        port: int,
        endpoint: str = "/api/health",
        timeout: int = 10,
        retries: int = 3,
        retry_delay: int = 2
    ):
        self.port = port
        self.endpoint = endpoint
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.base_url = f"http://localhost:{port}"

    def check(self) -> Tuple[bool, str]:
        """
        Perform health check on the service.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        url = f"{self.base_url}{self.endpoint}"

        for attempt in range(self.retries):
            try:
                response = requests.get(url, timeout=self.timeout)

                # Check status code
                if response.status_code == 200:
                    # Parse response
                    try:
                        data = response.json()
                        status = data.get("status", "unknown")

                        if status in ["ok", "healthy"]:
                            return True, f"Service healthy (status: {status})"
                        else:
                            return False, f"Service unhealthy (status: {status})"
                    except Exception as e:
                        # If we can't parse JSON, but got 200, assume healthy
                        return True, "Service healthy (200 OK)"
                else:
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.retries}: "
                        f"HTTP {response.status_code}"
                    )

            except requests.exceptions.ConnectionError:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.retries}: "
                    f"Connection refused on port {self.port}"
                )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.retries}: "
                    f"Request timeout after {self.timeout}s"
                )

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.retries}: "
                    f"Error: {e}"
                )

            # Wait before retry (except on last attempt)
            if attempt < self.retries - 1:
                time.sleep(self.retry_delay)

        return False, f"Service unhealthy after {self.retries} attempts"

    def check_multiple_endpoints(
        self,
        endpoints: Dict[str, str]
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Check multiple endpoints.

        Args:
            endpoints: Dict mapping name to endpoint path

        Returns:
            Dict mapping name to (is_healthy, message) tuple
        """
        results = {}

        for name, endpoint in endpoints.items():
            url = f"{self.base_url}{endpoint}"

            try:
                response = requests.get(url, timeout=self.timeout)

                if response.status_code == 200:
                    results[name] = (True, f"{name} healthy")
                else:
                    results[name] = (False, f"{name} returned {response.status_code}")

            except Exception as e:
                results[name] = (False, f"{name} error: {e}")

        return results


def check_service(port: int, endpoint: str = "/api/health") -> bool:
    """
    Simple function to check if a service is healthy.

    Args:
        port: Port number
        endpoint: Health check endpoint path

    Returns:
        True if healthy, False otherwise
    """
    checker = HealthChecker(port=port, endpoint=endpoint)
    is_healthy, _ = checker.check()
    return is_healthy


def wait_for_service(
    port: int,
    endpoint: str = "/api/health",
    max_wait: int = 60,
    check_interval: int = 2
) -> bool:
    """
    Wait for a service to become healthy.

    Args:
        port: Port number
        endpoint: Health check endpoint
        max_wait: Maximum wait time in seconds
        check_interval: Time between checks in seconds

    Returns:
        True if service became healthy, False if timeout
    """
    checker = HealthChecker(port=port, endpoint=endpoint, retries=1)
    elapsed = 0

    logger.info(f"Waiting for service on port {port} to become healthy...")

    while elapsed < max_wait:
        is_healthy, message = checker.check()

        if is_healthy:
            logger.info(f"Service healthy after {elapsed}s")
            return True

        time.sleep(check_interval)
        elapsed += check_interval

    logger.error(f"Service did not become healthy after {max_wait}s")
    return False


def main():
    """
    Main entry point for health check script.
    Used by Docker HEALTHCHECK.
    """
    import os

    # Get port from environment or default
    port = int(os.environ.get("HEALTH_CHECK_PORT", "11000"))
    endpoint = os.environ.get("HEALTH_CHECK_ENDPOINT", "/api/health")

    checker = HealthChecker(port=port, endpoint=endpoint, retries=1)
    is_healthy, message = checker.check()

    if is_healthy:
        logger.info(message)
        sys.exit(0)
    else:
        logger.error(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
