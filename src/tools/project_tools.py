"""Project-specific tools for file searching and content analysis.

This tool provides advanced file search and content analysis within the project.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base_tool import BaseTool, ToolParameter, ToolResult


class ProjectTool(BaseTool):
    """Tool for project file search and content analysis.

    Provides operations for:
    - Searching files by pattern (glob)
    - Searching file contents (grep-like)
    - Reading project files safely

    Attributes:
        project_root: Root directory of the project
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize the project tool.

        Args:
            project_root: Project root directory (default: current directory)
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.project_root = self.project_root.resolve()

    @property
    def name(self) -> str:
        """Tool name."""
        return "project"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Search and analyze project files. Operations: 'find' to search files by pattern, "
            "'search' to search file contents, 'read' to read file safely."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="operation",
                type="string",
                description="Operation: 'find' (search by filename), 'search' (search content), 'read' (read file)",
                required=True,
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="File pattern for 'find' (e.g., '*.py') or search query for 'search'",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="File path for 'read' operation or subdirectory for 'find'",
                required=False,
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results to return (default: 20)",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="max_chars",
                type="integer",
                description="Maximum characters to read from file (default: 4000)",
                required=False,
                default=4000,
            ),
        ]

    def _resolve_path(self, relative_path: str) -> tuple[Path | None, str | None]:
        """Resolve and validate path within project.

        Args:
            relative_path: Relative path from project root

        Returns:
            Tuple of (resolved_path, error_message)
        """
        try:
            candidate = (self.project_root / relative_path).resolve()

            # Security check
            if self.project_root not in candidate.parents and self.project_root != candidate:
                return None, f"Path '{relative_path}' is outside project root"

            return candidate, None

        except Exception as exc:
            return None, f"Invalid path: {exc}"

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute project operation.

        Args:
            operation: 'find', 'search', or 'read'
            Additional parameters depend on operation

        Returns:
            ToolResult with operation outcome
        """
        operation = kwargs.get("operation", "").lower()

        if operation == "find":
            return self._find_files(kwargs)
        elif operation == "search":
            return self._search_content(kwargs)
        elif operation == "read":
            return self._read_file(kwargs)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown operation: {operation}. Use 'find', 'search', or 'read'",
            )

    def _find_files(self, params: dict[str, Any]) -> ToolResult:
        """Find files by pattern.

        Args:
            params: Search parameters

        Returns:
            ToolResult with list of matching files
        """
        pattern = params.get("pattern", "*")
        subdir = params.get("path", ".")
        max_results = params.get("max_results", 20)

        # Resolve subdirectory
        base_dir, error = self._resolve_path(subdir)
        if error:
            return ToolResult(success=False, output="", error=error)

        if not base_dir.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {subdir}")

        # Search for files
        try:
            files: list[str] = []
            for path in base_dir.rglob(pattern):
                if not path.is_file():
                    continue
                if len(files) >= max_results:
                    break

                try:
                    rel_path = str(path.relative_to(self.project_root))
                    files.append(rel_path)
                except ValueError:
                    continue

            if not files:
                return ToolResult(success=True, output=f"No files found matching '{pattern}'")

            output = "\n".join(files)

            return ToolResult(
                success=True,
                output=output,
                metadata={"count": len(files), "files": files},
            )

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Search failed: {exc}")

    def _search_content(self, params: dict[str, Any]) -> ToolResult:
        """Search file contents for a query string.

        Args:
            params: Search parameters

        Returns:
            ToolResult with matching files and line numbers
        """
        query = params.get("pattern", "")
        file_pattern = params.get("path", "*.md")  # Default to markdown
        max_results = params.get("max_results", 20)

        if not query:
            return ToolResult(success=False, output="", error="Search query is required")

        query_lower = query.lower()
        results: list[dict[str, Any]] = []

        # Search through files
        try:
            for path in self.project_root.rglob(file_pattern):
                if not path.is_file():
                    continue

                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue

                if query_lower not in content.lower():
                    continue

                # Find matching lines
                matches = []
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if query_lower in line.lower():
                        matches.append({"line": line_num, "text": line.strip()})
                        if len(matches) >= 3:  # Limit to 3 matches per file
                            break

                try:
                    rel_path = str(path.relative_to(self.project_root))
                except ValueError:
                    continue

                results.append({"file": rel_path, "matches": matches})

                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(success=True, output=f"No matches found for '{query}'")

            # Format output
            lines = []
            for result in results:
                lines.append(f"{result['file']}:")
                for match in result["matches"]:
                    lines.append(f"  Line {match['line']}: {match['text']}")

            output = "\n".join(lines)

            return ToolResult(
                success=True,
                output=output,
                metadata={"count": len(results), "query": query, "results": results},
            )

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Search failed: {exc}")

    def _read_file(self, params: dict[str, Any]) -> ToolResult:
        """Read a project file safely.

        Args:
            params: Read parameters

        Returns:
            ToolResult with file contents
        """
        file_path = params.get("path", "")
        max_chars = params.get("max_chars", 4000)

        if not file_path:
            return ToolResult(success=False, output="", error="File path is required")

        # Resolve path
        resolved_path, error = self._resolve_path(file_path)
        if error:
            return ToolResult(success=False, output="", error=error)

        if not resolved_path.is_file():
            return ToolResult(success=False, output="", error=f"File not found: {file_path}")

        try:
            content = resolved_path.read_text(encoding="utf-8")

            # Truncate if needed
            truncated = False
            if len(content) > max_chars:
                content = content[:max_chars]
                truncated = True

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": file_path,
                    "truncated": truncated,
                    "size": len(content),
                },
            )

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Error reading file: {exc}")
