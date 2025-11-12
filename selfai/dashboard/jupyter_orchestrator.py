"""
JupyterLab Orchestration Module
Manages JupyterLab instance spawning, lifecycle, and resource allocation.
"""

import subprocess
import json
import os
import signal
import psutil
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import socket


@dataclass
class JupyterSession:
    """JupyterLab session information"""
    session_id: str
    user: str
    port: int
    pid: Optional[int]
    status: str  # "running", "stopped", "failed"
    gpu_ids: List[int]
    memory_limit_gb: int
    cpu_limit: int
    started_at: str
    notebook_dir: str
    token: str


class JupyterOrchestrator:
    """
    JupyterLab orchestration system for managing multiple user sessions.

    Features:
    - Spawn JupyterLab instances with resource constraints
    - Assign GPU resources to sessions
    - Track and manage session lifecycle
    - Automatic port allocation
    - Session cleanup and monitoring
    """

    def __init__(self, base_port: int = 8888, sessions_dir: str = "./jupyter_sessions"):
        self.base_port = base_port
        self.sessions_dir = sessions_dir
        self.sessions: Dict[str, JupyterSession] = {}
        self.port_pool = set(range(base_port, base_port + 100))

        # Create sessions directory
        os.makedirs(sessions_dir, exist_ok=True)

        # Load existing sessions
        self._load_sessions()

    def _load_sessions(self):
        """Load existing session information from disk"""
        sessions_file = os.path.join(self.sessions_dir, "sessions.json")
        if os.path.exists(sessions_file):
            try:
                with open(sessions_file, 'r') as f:
                    data = json.load(f)
                    for session_data in data:
                        session = JupyterSession(**session_data)
                        self.sessions[session.session_id] = session
                        self.port_pool.discard(session.port)
                        # Check if process is still running
                        if session.pid and not self._is_process_running(session.pid):
                            session.status = "stopped"
            except Exception as e:
                print(f"Error loading sessions: {e}")

    def _save_sessions(self):
        """Save session information to disk"""
        sessions_file = os.path.join(self.sessions_dir, "sessions.json")
        try:
            with open(sessions_file, 'w') as f:
                sessions_data = [asdict(s) for s in self.sessions.values()]
                json.dump(sessions_data, f, indent=2)
        except Exception as e:
            print(f"Error saving sessions: {e}")

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running"""
        try:
            return psutil.pid_exists(pid)
        except:
            return False

    def _find_free_port(self) -> int:
        """Find an available port"""
        for port in sorted(self.port_pool):
            if self._is_port_available(port):
                self.port_pool.discard(port)
                return port
        raise RuntimeError("No available ports")

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return True
        except OSError:
            return False

    def spawn_jupyter(
        self,
        user: str,
        gpu_ids: List[int] = None,
        memory_limit_gb: int = 16,
        cpu_limit: int = 4,
        notebook_dir: str = None
    ) -> JupyterSession:
        """
        Spawn a new JupyterLab instance for a user.

        Args:
            user: Username for the session
            gpu_ids: List of GPU IDs to assign (None for no GPU)
            memory_limit_gb: Memory limit in GB
            cpu_limit: Number of CPU cores
            notebook_dir: Working directory for notebooks

        Returns:
            JupyterSession object
        """
        # Generate session ID
        session_id = f"{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Find available port
        port = self._find_free_port()

        # Set notebook directory
        if notebook_dir is None:
            notebook_dir = os.path.join(self.sessions_dir, session_id)
        os.makedirs(notebook_dir, exist_ok=True)

        # Generate token
        import secrets
        token = secrets.token_urlsafe(32)

        # Build environment variables
        env = os.environ.copy()
        if gpu_ids:
            env['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, gpu_ids))
        else:
            env['CUDA_VISIBLE_DEVICES'] = ''

        # Build JupyterLab command
        cmd = [
            'jupyter', 'lab',
            '--no-browser',
            f'--port={port}',
            f'--NotebookApp.token={token}',
            f'--NotebookApp.notebook_dir={notebook_dir}',
            '--NotebookApp.allow_origin=*',
            '--NotebookApp.allow_remote_access=True'
        ]

        try:
            # Start JupyterLab process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setpgrp if os.name != 'nt' else None
            )

            # Create session object
            session = JupyterSession(
                session_id=session_id,
                user=user,
                port=port,
                pid=process.pid,
                status="running",
                gpu_ids=gpu_ids or [],
                memory_limit_gb=memory_limit_gb,
                cpu_limit=cpu_limit,
                started_at=datetime.now().isoformat(),
                notebook_dir=notebook_dir,
                token=token
            )

            # Store session
            self.sessions[session_id] = session
            self._save_sessions()

            return session

        except Exception as e:
            # Return port to pool on failure
            self.port_pool.add(port)
            raise RuntimeError(f"Failed to spawn JupyterLab: {e}")

    def stop_session(self, session_id: str) -> bool:
        """
        Stop a JupyterLab session.

        Args:
            session_id: Session ID to stop

        Returns:
            True if successful, False otherwise
        """
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        if session.pid and self._is_process_running(session.pid):
            try:
                # Send SIGTERM to process group
                if os.name != 'nt':
                    os.killpg(os.getpgid(session.pid), signal.SIGTERM)
                else:
                    os.kill(session.pid, signal.SIGTERM)

                session.status = "stopped"
                self.port_pool.add(session.port)
                self._save_sessions()
                return True
            except Exception as e:
                print(f"Error stopping session {session_id}: {e}")
                return False
        else:
            session.status = "stopped"
            self.port_pool.add(session.port)
            self._save_sessions()
            return True

    def get_session(self, session_id: str) -> Optional[JupyterSession]:
        """Get session information"""
        return self.sessions.get(session_id)

    def list_sessions(self, user: Optional[str] = None) -> List[JupyterSession]:
        """
        List all sessions, optionally filtered by user.

        Args:
            user: Filter by username (None for all)

        Returns:
            List of JupyterSession objects
        """
        sessions = list(self.sessions.values())
        if user:
            sessions = [s for s in sessions if s.user == user]
        return sessions

    def get_session_url(self, session_id: str) -> Optional[str]:
        """Get the URL to access a JupyterLab session"""
        session = self.sessions.get(session_id)
        if session and session.status == "running":
            return f"http://localhost:{session.port}/?token={session.token}"
        return None

    def get_sessions_dict(self) -> List[Dict]:
        """Get all sessions as dictionary format for JSON serialization"""
        return [asdict(s) for s in self.sessions.values()]

    def cleanup_stopped_sessions(self):
        """Remove stopped sessions from tracking"""
        stopped_sessions = [
            sid for sid, session in self.sessions.items()
            if session.status == "stopped" and not self._is_process_running(session.pid)
        ]

        for session_id in stopped_sessions:
            del self.sessions[session_id]

        if stopped_sessions:
            self._save_sessions()


if __name__ == "__main__":
    # Test orchestrator
    orchestrator = JupyterOrchestrator()

    print("Current sessions:")
    for session in orchestrator.list_sessions():
        print(f"  {session.session_id}: {session.status} on port {session.port}")

    # Example: spawn a session (commented out to avoid actually starting Jupyter)
    # session = orchestrator.spawn_jupyter(
    #     user="testuser",
    #     gpu_ids=[0],
    #     memory_limit_gb=16,
    #     cpu_limit=4
    # )
    # print(f"\nSpawned session: {session.session_id}")
    # print(f"URL: {orchestrator.get_session_url(session.session_id)}")
