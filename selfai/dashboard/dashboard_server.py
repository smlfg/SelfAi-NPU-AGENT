"""
Dashboard Web Server
Flask-based web server for the System Dashboard & Monitoring API.
Serves GPU metrics, JupyterLab orchestration, resource allocation, and health checks.
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
from typing import Dict
import os

from .gpu_monitor import GPUMonitor
from .jupyter_orchestrator import JupyterOrchestrator
from .resource_allocator import ResourceAllocator
from .health_checker import HealthChecker


class DashboardServer:
    """
    Web server for System Dashboard & Monitoring.

    Features:
    - RESTful API for all monitoring functions
    - CORS enabled for cross-origin requests
    - JSON responses
    - Error handling
    - Static file serving for web UI
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 11000,
        debug: bool = False,
        static_dir: str = "./dashboard_ui"
    ):
        self.host = host
        self.port = port
        self.debug = debug
        self.static_dir = static_dir

        # Initialize components
        self.gpu_monitor = GPUMonitor()
        self.jupyter_orchestrator = JupyterOrchestrator()
        self.resource_allocator = ResourceAllocator()
        self.health_checker = HealthChecker()

        # Create Flask app
        self.app = Flask(__name__, static_folder=static_dir)
        CORS(self.app)

        # Configure logging
        if not debug:
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register all API routes"""

        # ===== Health & Status =====
        @self.app.route('/api/health', methods=['GET'])
        def health():
            """System health check endpoint"""
            try:
                health_data = self.health_checker.get_health_dict()
                return jsonify({
                    "status": "ok",
                    "data": health_data
                }), 200
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/status', methods=['GET'])
        def status():
            """Overall system status"""
            try:
                return jsonify({
                    "status": "ok",
                    "message": "Dashboard API is running",
                    "version": "1.0.0",
                    "endpoints": {
                        "health": "/api/health",
                        "gpu": "/api/gpu",
                        "jupyter": "/api/jupyter",
                        "resources": "/api/resources"
                    }
                }), 200
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        # ===== GPU Monitoring =====
        @self.app.route('/api/gpu', methods=['GET'])
        def get_gpu_metrics():
            """Get GPU metrics"""
            try:
                metrics = self.gpu_monitor.get_metrics_dict()
                system_info = self.gpu_monitor.get_system_info()

                return jsonify({
                    "status": "ok",
                    "data": {
                        "gpus": metrics,
                        "system": system_info
                    }
                }), 200
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/gpu/<int:gpu_id>', methods=['GET'])
        def get_gpu_by_id(gpu_id):
            """Get metrics for specific GPU"""
            try:
                metrics = self.gpu_monitor.get_metrics_dict()
                gpu_metric = next((m for m in metrics if m['gpu_id'] == gpu_id), None)

                if gpu_metric:
                    return jsonify({
                        "status": "ok",
                        "data": gpu_metric
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "message": f"GPU {gpu_id} not found"
                    }), 404
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        # ===== JupyterLab Orchestration =====
        @self.app.route('/api/jupyter', methods=['GET'])
        def list_jupyter_sessions():
            """List all JupyterLab sessions"""
            try:
                user = request.args.get('user')
                sessions = self.jupyter_orchestrator.get_sessions_dict()

                if user:
                    sessions = [s for s in sessions if s['user'] == user]

                return jsonify({
                    "status": "ok",
                    "data": sessions
                }), 200
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/jupyter/spawn', methods=['POST'])
        def spawn_jupyter():
            """Spawn a new JupyterLab session"""
            try:
                data = request.get_json()

                user = data.get('user')
                if not user:
                    return jsonify({
                        "status": "error",
                        "message": "User field is required"
                    }), 400

                gpu_ids = data.get('gpu_ids', [])
                memory_limit_gb = data.get('memory_limit_gb', 16)
                cpu_limit = data.get('cpu_limit', 4)

                session = self.jupyter_orchestrator.spawn_jupyter(
                    user=user,
                    gpu_ids=gpu_ids,
                    memory_limit_gb=memory_limit_gb,
                    cpu_limit=cpu_limit
                )

                return jsonify({
                    "status": "ok",
                    "data": {
                        "session_id": session.session_id,
                        "url": self.jupyter_orchestrator.get_session_url(session.session_id),
                        "port": session.port,
                        "gpu_ids": session.gpu_ids
                    }
                }), 201
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/jupyter/<session_id>', methods=['GET'])
        def get_jupyter_session(session_id):
            """Get specific JupyterLab session"""
            try:
                session = self.jupyter_orchestrator.get_session(session_id)

                if session:
                    return jsonify({
                        "status": "ok",
                        "data": {
                            "session_id": session.session_id,
                            "user": session.user,
                            "status": session.status,
                            "port": session.port,
                            "gpu_ids": session.gpu_ids,
                            "url": self.jupyter_orchestrator.get_session_url(session_id)
                        }
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "message": f"Session {session_id} not found"
                    }), 404
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/jupyter/<session_id>', methods=['DELETE'])
        def stop_jupyter_session(session_id):
            """Stop a JupyterLab session"""
            try:
                success = self.jupyter_orchestrator.stop_session(session_id)

                if success:
                    return jsonify({
                        "status": "ok",
                        "message": f"Session {session_id} stopped"
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "message": f"Failed to stop session {session_id}"
                    }), 404
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        # ===== Resource Allocation =====
        @self.app.route('/api/resources', methods=['GET'])
        def get_resources():
            """Get resource capacity and utilization"""
            try:
                capacity = self.resource_allocator.get_capacity()
                utilization = self.resource_allocator.get_utilization()
                allocations = self.resource_allocator.get_allocations_dict()

                return jsonify({
                    "status": "ok",
                    "data": {
                        "capacity": {
                            "total_gpus": capacity.total_gpus,
                            "total_memory_gb": capacity.total_memory_gb,
                            "total_cpu_cores": capacity.total_cpu_cores,
                            "available_gpus": capacity.available_gpus,
                            "available_memory_gb": capacity.available_memory_gb,
                            "available_cpu_cores": capacity.available_cpu_cores
                        },
                        "utilization": utilization,
                        "allocations": allocations
                    }
                }), 200
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/resources/allocate', methods=['POST'])
        def allocate_resources():
            """Request resource allocation"""
            try:
                data = request.get_json()

                user = data.get('user')
                if not user:
                    return jsonify({
                        "status": "error",
                        "message": "User field is required"
                    }), 400

                gpu_count = data.get('gpu_count', 0)
                memory_gb = data.get('memory_gb', 0)
                cpu_cores = data.get('cpu_cores', 1)
                priority = data.get('priority', 5)

                allocation = self.resource_allocator.request_resources(
                    user=user,
                    gpu_count=gpu_count,
                    memory_gb=memory_gb,
                    cpu_cores=cpu_cores,
                    priority=priority
                )

                if allocation:
                    return jsonify({
                        "status": "ok",
                        "data": {
                            "allocation_id": allocation.allocation_id,
                            "gpu_ids": allocation.gpu_ids,
                            "memory_gb": allocation.memory_gb,
                            "cpu_cores": allocation.cpu_cores
                        }
                    }), 201
                else:
                    return jsonify({
                        "status": "error",
                        "message": "Insufficient resources, request queued"
                    }), 503
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        @self.app.route('/api/resources/<allocation_id>', methods=['DELETE'])
        def release_resources(allocation_id):
            """Release allocated resources"""
            try:
                success = self.resource_allocator.release_resources(allocation_id)

                if success:
                    return jsonify({
                        "status": "ok",
                        "message": f"Resources {allocation_id} released"
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "message": f"Allocation {allocation_id} not found"
                    }), 404
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        # ===== Web UI =====
        @self.app.route('/')
        def index():
            """Serve web UI"""
            if os.path.exists(os.path.join(self.static_dir, 'index.html')):
                return send_from_directory(self.static_dir, 'index.html')
            else:
                return jsonify({
                    "message": "Dashboard API",
                    "version": "1.0.0",
                    "api_docs": "/api/status"
                }), 200

    def run(self):
        """Start the web server"""
        print(f"Starting Dashboard Server on {self.host}:{self.port}")
        print(f"API available at: http://{self.host}:{self.port}/api")
        print(f"\nAvailable endpoints:")
        print(f"  - Health:    http://{self.host}:{self.port}/api/health")
        print(f"  - GPU:       http://{self.host}:{self.port}/api/gpu")
        print(f"  - Jupyter:   http://{self.host}:{self.port}/api/jupyter")
        print(f"  - Resources: http://{self.host}:{self.port}/api/resources")

        self.app.run(
            host=self.host,
            port=self.port,
            debug=self.debug
        )


def main():
    """Main entry point for the dashboard server"""
    import argparse

    parser = argparse.ArgumentParser(description='System Dashboard & Monitoring Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=11000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    server = DashboardServer(
        host=args.host,
        port=args.port,
        debug=args.debug
    )

    server.run()


if __name__ == "__main__":
    main()
