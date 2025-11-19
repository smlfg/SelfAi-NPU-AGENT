"""Calendar tools for managing events and schedules.

This tool provides JSON-based calendar event storage with date normalization.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .base_tool import BaseTool, ToolParameter, ToolResult


class CalendarTool(BaseTool):
    """Tool for calendar event management.

    Stores events in a JSON file with support for adding, listing, and querying events.

    Attributes:
        calendar_path: Path to the calendar JSON file
    """

    def __init__(self, calendar_path: Path | None = None):
        """Initialize the calendar tool.

        Args:
            calendar_path: Path to calendar JSON file (default: data/calendar_events.json)
        """
        if calendar_path is None:
            calendar_path = Path("data/calendar_events.json")

        self.calendar_path = Path(calendar_path)

        # Create parent directory
        self.calendar_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize empty calendar if doesn't exist
        if not self.calendar_path.exists():
            self._save_events([])

    @property
    def name(self) -> str:
        """Tool name."""
        return "calendar"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Manage calendar events: add new events, list upcoming events, "
            "and query events by date range. Supports date/time normalization."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="operation",
                type="string",
                description="Operation: 'add' to create event, 'list' to show events, 'query' to search by date",
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="Event title (required for 'add' operation)",
                required=False,
            ),
            ToolParameter(
                name="date",
                type="string",
                description="Event date in YYYY-MM-DD format (required for 'add' operation)",
                required=False,
            ),
            ToolParameter(
                name="start_time",
                type="string",
                description="Start time in HH:MM format (optional for 'add')",
                required=False,
            ),
            ToolParameter(
                name="end_time",
                type="string",
                description="End time in HH:MM format (optional for 'add')",
                required=False,
            ),
            ToolParameter(
                name="location",
                type="string",
                description="Event location (optional for 'add')",
                required=False,
            ),
            ToolParameter(
                name="notes",
                type="string",
                description="Event notes (optional for 'add')",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of events to return (default: 10)",
                required=False,
                default=10,
            ),
        ]

    def _load_events(self) -> list[dict[str, Any]]:
        """Load events from JSON file.

        Returns:
            List of event dictionaries
        """
        try:
            with open(self.calendar_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    def _save_events(self, events: list[dict[str, Any]]) -> None:
        """Save events to JSON file.

        Args:
            events: List of event dictionaries
        """
        try:
            with open(self.calendar_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[CalendarTool] Error saving events: {exc}")

    def _normalize_date(self, date_str: str) -> str | None:
        """Normalize date string to YYYY-MM-DD format.

        Args:
            date_str: Date string in various formats

        Returns:
            Normalized date string or None if invalid
        """
        if not date_str or not date_str.strip():
            return None

        formats = [
            "%Y-%m-%d",      # 2025-01-15
            "%d.%m.%Y",      # 15.01.2025
            "%d.%m.%y",      # 15.01.25
            "%d.%m.",        # 15.01. (assume current year)
            "%Y/%m/%d",      # 2025/01/15
            "%d/%m/%Y",      # 15/01/2025
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                # If format doesn't include year, use current year
                if fmt == "%d.%m.":
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None  # Invalid date

    def _normalize_time(self, time_str: str | None) -> str | None:
        """Normalize time string to HH:MM format.

        Args:
            time_str: Time string in various formats

        Returns:
            Normalized time string or None if invalid
        """
        if not time_str or not time_str.strip():
            return None

        formats = ["%H:%M", "%H.%M", "%H%M"]

        for fmt in formats:
            try:
                return datetime.strptime(time_str.strip(), fmt).strftime("%H:%M")
            except ValueError:
                continue

        return None  # Invalid time

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute calendar operation.

        Args:
            operation: 'add', 'list', or 'query'
            Additional parameters depend on operation

        Returns:
            ToolResult with operation outcome
        """
        operation = kwargs.get("operation", "").lower()

        if operation == "add":
            return self._add_event(kwargs)
        elif operation == "list":
            return self._list_events(kwargs)
        elif operation == "query":
            return self._query_events(kwargs)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown operation: {operation}. Use 'add', 'list', or 'query'",
            )

    def _add_event(self, params: dict[str, Any]) -> ToolResult:
        """Add a new calendar event.

        Args:
            params: Event parameters

        Returns:
            ToolResult with created event details
        """
        title = params.get("title", "").strip()
        date_str = params.get("date", "")

        if not title:
            return ToolResult(success=False, output="", error="Title is required")

        if not date_str:
            return ToolResult(success=False, output="", error="Date is required")

        # Normalize date and times
        normalized_date = self._normalize_date(date_str)
        if not normalized_date:
            return ToolResult(success=False, output="", error=f"Invalid date format: {date_str}")

        normalized_start = self._normalize_time(params.get("start_time"))
        normalized_end = self._normalize_time(params.get("end_time"))

        # Create event
        event = {
            "id": uuid4().hex,
            "title": title,
            "date": normalized_date,
            "start_time": normalized_start,
            "end_time": normalized_end,
            "location": params.get("location", "").strip() or None,
            "notes": params.get("notes", "").strip() or None,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

        # Save event
        events = self._load_events()
        events.append(event)
        self._save_events(events)

        output = f"Event created: {title} on {normalized_date}"
        if normalized_start:
            output += f" at {normalized_start}"

        return ToolResult(
            success=True,
            output=output,
            metadata={"event": event},
        )

    def _list_events(self, params: dict[str, Any]) -> ToolResult:
        """List upcoming events.

        Args:
            params: Query parameters

        Returns:
            ToolResult with event list
        """
        limit = params.get("limit", 10)
        events = self._load_events()

        # Sort by date, then start_time
        def sort_key(event: dict) -> tuple:
            return (
                event.get("date", ""),
                event.get("start_time") or "00:00",
            )

        events.sort(key=sort_key)

        # Apply limit
        events = events[:limit]

        if not events:
            return ToolResult(success=True, output="No events found")

        # Format output
        lines = []
        for event in events:
            date_time = event["date"]
            if event.get("start_time"):
                date_time += f" {event['start_time']}"
            lines.append(f"- {event['title']} ({date_time})")

        output = "\n".join(lines)

        return ToolResult(
            success=True,
            output=output,
            metadata={"count": len(events), "events": events},
        )

    def _query_events(self, params: dict[str, Any]) -> ToolResult:
        """Query events by date.

        Args:
            params: Query parameters

        Returns:
            ToolResult with matching events
        """
        date_str = params.get("date", "")
        if not date_str:
            return ToolResult(success=False, output="", error="Date is required for query")

        normalized_date = self._normalize_date(date_str)
        if not normalized_date:
            return ToolResult(success=False, output="", error=f"Invalid date: {date_str}")

        events = self._load_events()
        matching = [e for e in events if e.get("date") == normalized_date]

        if not matching:
            return ToolResult(success=True, output=f"No events found on {normalized_date}")

        # Format output
        lines = [f"Events on {normalized_date}:"]
        for event in matching:
            time_str = event.get("start_time", "all day")
            lines.append(f"- {event['title']} ({time_str})")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"count": len(matching), "events": matching},
        )
