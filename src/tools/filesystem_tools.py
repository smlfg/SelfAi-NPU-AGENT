"""Filesystem tools for file operations.

This module provides safe filesystem operations with proper error handling
and security checks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base_tool import BaseTool, ToolParameter, ToolResult


class FileSystemTool(BaseTool):
    """Tool for filesystem operations (read, write, list).

    This tool provides safe file operations with security checks to prevent
    accessing files outside the allowed directory.

    Attributes:
        project_root: Root directory for file operations (security boundary)
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize the filesystem tool.

        Args:
            project_root: Root directory for operations (default: current working directory)
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.project_root = self.project_root.resolve()

    @property
    def name(self) -> str:
        """Tool name."""
        return "filesystem"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Perform filesystem operations: read files, write files, and list directory contents. "
            "All paths are relative to the project root for security."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="operation",
                type="string",
                description="Operation to perform: 'read', 'write', or 'list'",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="File or directory path (relative to project root)",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write (required for 'write' operation)",
                required=False,
            ),
            ToolParameter(
                name="create_dirs",
                type="boolean",
                description="Create parent directories if they don't exist (for 'write' operation)",
                required=False,
                default=True,
            ),
        ]

    def _resolve_path(self, relative_path: str) -> tuple[Path | None, str | None]:
        """Resolve and validate a path within project root.

        Args:
            relative_path: Relative path from project root

        Returns:
            Tuple of (resolved_path, error_message)
            - resolved_path: Path object if valid, None if invalid
            - error_message: Error description if invalid, None if valid
        """
        try:
            # Resolve path
            candidate = (self.project_root / relative_path).resolve()

            # Security check: ensure path is within project root
            if self.project_root not in candidate.parents and self.project_root != candidate:
                return None, f"Path '{relative_path}' is outside project root"

            return candidate, None

        except Exception as exc:
            return None, f"Invalid path: {exc}"

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute filesystem operation.

        Args:
            operation: 'read', 'write', or 'list'
            path: File or directory path
            content: Content to write (for 'write' operation)
            create_dirs: Create parent directories (for 'write' operation)

        Returns:
            ToolResult with operation outcome
        """
        operation = kwargs.get("operation", "").lower()
        relative_path = kwargs.get("path", "")

        if not relative_path:
            return ToolResult(success=False, output="", error="Path is required")

        # Resolve path
        resolved_path, error = self._resolve_path(relative_path)
        if error:
            return ToolResult(success=False, output="", error=error)

        # Execute operation
        if operation == "read":
            return self._read_file(resolved_path)
        elif operation == "write":
            content = kwargs.get("content", "")
            create_dirs = kwargs.get("create_dirs", True)
            return self._write_file(resolved_path, content, create_dirs)
        elif operation == "list":
            return self._list_directory(resolved_path)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown operation: {operation}. Use 'read', 'write', or 'list'",
            )

    def _read_file(self, path: Path) -> ToolResult:
        """Read a file.

        Args:
            path: Path to file

        Returns:
            ToolResult with file contents or error
        """
        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")

        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(path.relative_to(self.project_root)), "size": len(content)},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Error reading file: {exc}")

    def _write_file(self, path: Path, content: str, create_dirs: bool) -> ToolResult:
        """Write content to a file.

        Args:
            path: Path to file
            content: Content to write
            create_dirs: Whether to create parent directories

        Returns:
            ToolResult with success status
        """
        try:
            # Create parent directories if needed
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            path.write_text(content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {path.relative_to(self.project_root)}",
                metadata={"path": str(path.relative_to(self.project_root)), "size": len(content)},
            )

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Error writing file: {exc}")

    def _list_directory(self, path: Path) -> ToolResult:
        """List directory contents.

        Args:
            path: Path to directory

        Returns:
            ToolResult with directory listing or error
        """
        if not path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")

        if not path.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")

        try:
            entries = []
            for item in sorted(path.iterdir()):
                item_type = "dir" if item.is_dir() else "file"
                entries.append(f"{item.name} ({item_type})")

            output = "\n".join(entries) if entries else "(empty directory)"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": str(path.relative_to(self.project_root)),
                    "count": len(entries),
                },
            )

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Error listing directory: {exc}")
