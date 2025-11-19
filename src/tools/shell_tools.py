"""Shell command execution tool with security controls.

SECURITY WARNING: Shell command execution is inherently risky. This tool
implements several security measures but should be used with caution.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from .base_tool import BaseTool, ToolParameter, ToolResult


class ShellTool(BaseTool):
    """Tool for executing shell commands with security controls.

    Security features:
    - Whitelist of allowed commands (optional)
    - Blacklist of dangerous commands
    - Timeout enforcement
    - Working directory restriction
    - No shell=True by default (prevents injection)

    Attributes:
        allowed_commands: Optional whitelist of allowed commands
        blacklist_commands: Commands that are never allowed
        timeout: Maximum execution time in seconds
        working_dir: Working directory for command execution
    """

    # Dangerous commands that should never be allowed
    DEFAULT_BLACKLIST = {
        "rm", "rmdir", "del", "format", "mkfs",
        "dd", "fdisk", "parted",
        "shutdown", "reboot", "halt",
        "kill", "killall", "pkill",
        "chmod", "chown", "chgrp",
        "sudo", "su",
    }

    def __init__(
        self,
        allowed_commands: list[str] | None = None,
        blacklist_commands: set[str] | None = None,
        timeout: int = 30,
        working_dir: Path | None = None,
    ):
        """Initialize the shell tool.

        Args:
            allowed_commands: Optional whitelist of allowed commands
            blacklist_commands: Additional blacklisted commands (merged with defaults)
            timeout: Maximum execution time in seconds (default: 30)
            working_dir: Working directory for execution (default: current directory)
        """
        self.allowed_commands = set(allowed_commands) if allowed_commands else None
        self.blacklist_commands = self.DEFAULT_BLACKLIST.copy()
        if blacklist_commands:
            self.blacklist_commands.update(blacklist_commands)
        self.timeout = timeout
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()

    @property
    def name(self) -> str:
        """Tool name."""
        return "shell"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Execute shell commands safely. "
            "Use this to run system commands, scripts, or command-line tools. "
            "Commands are executed with timeout and security restrictions."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="command",
                type="string",
                description="Shell command to execute (e.g., 'ls -la', 'git status')",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description=f"Maximum execution time in seconds (default: {self.timeout})",
                required=False,
                default=self.timeout,
            ),
        ]

    def _validate_command(self, command: str) -> tuple[bool, str | None]:
        """Validate command against security policies.

        Args:
            command: Command string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not command or not command.strip():
            return False, "Command cannot be empty"

        # Parse command to get the executable
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            return False, f"Invalid command syntax: {exc}"

        if not parts:
            return False, "Command cannot be empty"

        executable = parts[0]

        # Extract base command (remove path)
        base_cmd = Path(executable).name

        # Check blacklist
        if base_cmd in self.blacklist_commands:
            return False, f"Command '{base_cmd}' is blacklisted for security reasons"

        # Check whitelist if enabled
        if self.allowed_commands is not None:
            if base_cmd not in self.allowed_commands:
                return False, f"Command '{base_cmd}' is not in the allowed list"

        return True, None

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute shell command.

        Args:
            command: Shell command to execute
            timeout: Execution timeout in seconds

        Returns:
            ToolResult with command output or error
        """
        command = kwargs.get("command", "").strip()
        timeout = kwargs.get("timeout", self.timeout)

        # Validate command
        is_valid, error = self._validate_command(command)
        if not is_valid:
            return ToolResult(success=False, output="", error=error)

        # Parse command (safer than shell=True)
        try:
            cmd_parts = shlex.split(command)
        except ValueError as exc:
            return ToolResult(success=False, output="", error=f"Invalid command: {exc}")

        # Execute command
        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
                check=False,  # Don't raise on non-zero exit
            )

            # Build output
            output_parts = []
            if result.stdout:
                output_parts.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                output_parts.append(f"STDERR:\n{result.stderr}")

            output = "\n".join(output_parts) if output_parts else "(no output)"

            # Determine success based on exit code
            success = result.returncode == 0

            return ToolResult(
                success=success,
                output=output,
                metadata={
                    "exit_code": result.returncode,
                    "command": command,
                    "working_dir": str(self.working_dir),
                },
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds",
            )

        except FileNotFoundError:
            return ToolResult(
                success=False,
                output="",
                error=f"Command not found: {cmd_parts[0]}",
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Command execution failed: {exc}",
            )
