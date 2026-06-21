"""Output formatting helpers for the CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from issuedb.models import Issue

if TYPE_CHECKING:
    from issuedb.cli import CLI


def format_output(self: CLI, data: Any, as_json: bool = False) -> str:
    """Format output for display.

    Args:
        data: Data to format (Issue, list of Issues, dict, etc).
        as_json: If True, output as JSON.

    Returns:
        Formatted string output.
    """
    if as_json:
        if isinstance(data, Issue):
            return json.dumps(data.to_dict(), indent=2)
        elif isinstance(data, list) and all(isinstance(i, Issue) for i in data):
            return json.dumps([i.to_dict() for i in data], indent=2)
        elif isinstance(data, dict):
            return json.dumps(data, indent=2)
        else:
            return json.dumps(data, indent=2)
    else:
        if isinstance(data, Issue):
            return self._format_issue(data)
        elif isinstance(data, list) and all(isinstance(i, Issue) for i in data):
            if not data:
                return "No issues found."
            return "\n\n".join(self._format_issue(i) for i in data)
        elif isinstance(data, dict):
            return self._format_dict(data)
        else:
            return str(data)


def _format_issue(self: CLI, issue: Issue) -> str:
    """Format a single issue for display.

    Args:
        issue: Issue to format.

    Returns:
        Formatted string.
    """
    lines = [
        f"ID: {issue.id}",
        f"Title: {issue.title}",
        f"Status: {issue.status.value}",
        f"Priority: {issue.priority.value}",
    ]

    if issue.due_date:
        lines.append(f"Due Date: {issue.due_date.strftime('%Y-%m-%d')}")

    if issue.tags:
        tag_names = [t.name for t in issue.tags]
        lines.append(f"Tags: {', '.join(tag_names)}")

    if issue.description:
        lines.append(f"Description: {issue.description}")

    lines.extend(
        [
            f"Created: {issue.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Updated: {issue.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
    )

    # Add code references if any
    if issue.id is not None:
        refs = self.repo.get_code_references(issue.id)
        if refs:
            lines.append("")
            lines.append("Code References:")
            for ref in refs:
                ref_str = f"  - {ref.file_path}"
                if ref.start_line and ref.end_line:
                    ref_str += f":{ref.start_line}-{ref.end_line}"
                elif ref.start_line:
                    ref_str += f":{ref.start_line}"
                if ref.note:
                    ref_str += f" ({ref.note})"
                lines.append(ref_str)

    return "\n".join(lines)


def _format_dict(self: CLI, data: dict[str, Any], indent: int = 0) -> str:
    """Format a dictionary for display (recursively for nested structures).

    Args:
        data: Dictionary to format.
        indent: Current indentation level (used for nested dicts/lists).

    Returns:
        Formatted string.
    """
    lines = []
    pad = "  " * indent
    for key, value in data.items():
        formatted_key = key.replace("_", " ").title()
        if isinstance(value, dict):
            lines.append(f"{pad}{formatted_key}:")
            if value:
                lines.append(self._format_dict(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{pad}{formatted_key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(self._format_dict(item, indent + 1))
                else:
                    lines.append(f"{pad}  - {item}")
        else:
            lines.append(f"{pad}{formatted_key}: {value}")
    return "\n".join(lines)
