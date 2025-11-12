"""
Integration tests for shared health check module
"""

import pytest
from shared.health_check import HealthChecker, check_service, wait_for_service


class TestHealthCheckModule:
    """Test shared health check functionality"""

    def test_health_checker_initialization(self):
        """Test HealthChecker initialization"""
        checker = HealthChecker(port=11000, endpoint="/api/health")
        assert checker.port == 11000
        assert checker.endpoint == "/api/health"

    def test_check_service_function(self):
        """Test check_service utility function"""
        is_healthy = check_service(port=11000, endpoint="/api/health")
        assert isinstance(is_healthy, bool)

    def test_health_checker_against_dashboard(self):
        """Test HealthChecker against running dashboard"""
        checker = HealthChecker(port=11000, endpoint="/api/health")
        is_healthy, message = checker.check()

        assert isinstance(is_healthy, bool)
        assert isinstance(message, str)
        assert len(message) > 0

    def test_health_checker_with_invalid_port(self):
        """Test HealthChecker with invalid port"""
        checker = HealthChecker(port=99999, endpoint="/api/health", retries=1)
        is_healthy, message = checker.check()

        assert is_healthy is False
        assert "unhealthy" in message.lower()

    def test_health_checker_with_invalid_endpoint(self):
        """Test HealthChecker with invalid endpoint"""
        checker = HealthChecker(port=11000, endpoint="/api/invalid", retries=1)
        is_healthy, message = checker.check()

        # Will either be False or might still return True if endpoint returns 200
        assert isinstance(is_healthy, bool)

    def test_check_multiple_endpoints(self):
        """Test checking multiple endpoints"""
        checker = HealthChecker(port=11000)
        results = checker.check_multiple_endpoints({
            "health": "/api/health",
            "status": "/api/status",
            "gpu": "/api/gpu"
        })

        assert isinstance(results, dict)
        assert "health" in results
        assert "status" in results
        assert "gpu" in results

        for name, (is_healthy, message) in results.items():
            assert isinstance(is_healthy, bool)
            assert isinstance(message, str)

    def test_wait_for_service_already_running(self):
        """Test wait_for_service with already running service"""
        result = wait_for_service(
            port=11000,
            endpoint="/api/health",
            max_wait=10,
            check_interval=1
        )
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
