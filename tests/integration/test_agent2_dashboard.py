"""
Integration tests for Agent 2: System Dashboard & Monitoring
"""

import pytest
import requests
import time
from typing import Dict, Any


class TestAgent2Dashboard:
    """Integration tests for dashboard agent"""

    BASE_URL = "http://localhost:11000"

    @pytest.fixture(autouse=True)
    def setup(self):
        """Wait for service to be ready"""
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{self.BASE_URL}/api/status", timeout=2)
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                if i == max_retries - 1:
                    pytest.fail("Service did not become available")
                time.sleep(2)

    def test_service_health(self):
        """Test that the service is healthy"""
        response = requests.get(f"{self.BASE_URL}/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data

    def test_service_status(self):
        """Test service status endpoint"""
        response = requests.get(f"{self.BASE_URL}/api/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data

    def test_gpu_metrics(self):
        """Test GPU metrics endpoint"""
        response = requests.get(f"{self.BASE_URL}/api/gpu")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert "gpus" in data["data"]
        assert "system" in data["data"]

    def test_gpu_metrics_structure(self):
        """Test GPU metrics data structure"""
        response = requests.get(f"{self.BASE_URL}/api/gpu")
        data = response.json()

        gpus = data["data"]["gpus"]
        if gpus:  # If GPUs are available
            gpu = gpus[0]
            assert "gpu_id" in gpu
            assert "name" in gpu
            assert "utilization" in gpu
            assert "memory_used" in gpu
            assert "memory_total" in gpu

    def test_jupyter_list(self):
        """Test listing JupyterLab sessions"""
        response = requests.get(f"{self.BASE_URL}/api/jupyter")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_resources_endpoint(self):
        """Test resource allocation endpoint"""
        response = requests.get(f"{self.BASE_URL}/api/resources")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert "capacity" in data["data"]
        assert "utilization" in data["data"]

    def test_resource_capacity_structure(self):
        """Test resource capacity data structure"""
        response = requests.get(f"{self.BASE_URL}/api/resources")
        data = response.json()

        capacity = data["data"]["capacity"]
        assert "total_gpus" in capacity
        assert "total_memory_gb" in capacity
        assert "total_cpu_cores" in capacity
        assert "available_gpus" in capacity

    def test_health_check_details(self):
        """Test detailed health check information"""
        response = requests.get(f"{self.BASE_URL}/api/health")
        data = response.json()

        health_data = data["data"]
        assert "status" in health_data
        assert "checks" in health_data
        assert "summary" in health_data

        # Verify checks structure
        checks = health_data["checks"]
        assert len(checks) > 0

        for check in checks:
            assert "component" in check
            assert "status" in check
            assert "message" in check
            assert check["status"] in ["healthy", "degraded", "unhealthy"]

    def test_error_handling_invalid_endpoint(self):
        """Test error handling for invalid endpoints"""
        response = requests.get(f"{self.BASE_URL}/api/invalid")
        assert response.status_code == 404

    def test_error_handling_invalid_gpu_id(self):
        """Test error handling for invalid GPU ID"""
        response = requests.get(f"{self.BASE_URL}/api/gpu/999")
        # Should return 404 or error response
        assert response.status_code in [404, 500]

    def test_cors_headers(self):
        """Test that CORS headers are present"""
        response = requests.options(f"{self.BASE_URL}/api/health")
        assert "Access-Control-Allow-Origin" in response.headers

    def test_json_content_type(self):
        """Test that responses have correct content type"""
        response = requests.get(f"{self.BASE_URL}/api/status")
        assert "application/json" in response.headers.get("Content-Type", "")


class TestAgent2ResourceAllocation:
    """Test resource allocation functionality"""

    BASE_URL = "http://localhost:11000"

    def test_allocate_resources(self):
        """Test resource allocation"""
        response = requests.post(
            f"{self.BASE_URL}/api/resources/allocate",
            json={
                "user": "test_user",
                "gpu_count": 1,
                "memory_gb": 8,
                "cpu_cores": 2,
                "priority": 5
            }
        )

        # Should succeed or return 503 if resources unavailable
        assert response.status_code in [201, 503]

        if response.status_code == 201:
            data = response.json()
            assert data["status"] == "ok"
            assert "allocation_id" in data["data"]

            # Clean up - release resources
            allocation_id = data["data"]["allocation_id"]
            requests.delete(f"{self.BASE_URL}/api/resources/{allocation_id}")

    def test_allocate_invalid_resources(self):
        """Test allocation with invalid parameters"""
        response = requests.post(
            f"{self.BASE_URL}/api/resources/allocate",
            json={
                # Missing user field
                "gpu_count": 1,
                "memory_gb": 8
            }
        )
        assert response.status_code == 400


class TestAgent2JupyterOrchestration:
    """Test JupyterLab orchestration functionality"""

    BASE_URL = "http://localhost:11000"

    def test_jupyter_spawn_validation(self):
        """Test JupyterLab spawn validation"""
        response = requests.post(
            f"{self.BASE_URL}/api/jupyter/spawn",
            json={
                # Missing user field
                "gpu_ids": [0],
                "memory_limit_gb": 16
            }
        )
        assert response.status_code == 400

    def test_jupyter_session_not_found(self):
        """Test getting non-existent session"""
        response = requests.get(f"{self.BASE_URL}/api/jupyter/invalid_session")
        assert response.status_code == 404


# Performance tests
class TestAgent2Performance:
    """Performance tests for dashboard agent"""

    BASE_URL = "http://localhost:11000"

    def test_health_check_response_time(self):
        """Test that health check responds quickly"""
        start = time.time()
        response = requests.get(f"{self.BASE_URL}/api/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0  # Should respond in under 2 seconds

    def test_gpu_metrics_response_time(self):
        """Test that GPU metrics respond quickly"""
        start = time.time()
        response = requests.get(f"{self.BASE_URL}/api/gpu")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 3.0  # Should respond in under 3 seconds

    def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        import concurrent.futures

        def make_request():
            response = requests.get(f"{self.BASE_URL}/api/status")
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(status == 200 for status in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
