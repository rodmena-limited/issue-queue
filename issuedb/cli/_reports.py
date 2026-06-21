"""Audit, info, summary, and report CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def get_audit_logs(
    self: CLI,
    issue_id: int | None = None,
    as_json: bool = False,
) -> str:
    """Get audit logs.

    Args:
        issue_id: Filter by issue ID.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    logs = self.repo.get_audit_logs(issue_id=issue_id)

    if as_json:
        return json.dumps([log.to_dict() for log in logs], indent=2)
    else:
        if not logs:
            return "No audit logs found."

        lines = []
        for log in logs:
            lines.append("-" * 50)
            lines.append(f"Timestamp: {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Issue ID: {log.issue_id}")
            lines.append(f"Action: {log.action}")

            if log.field_name:
                lines.append(f"Field: {log.field_name}")
                lines.append(f"Old Value: {log.old_value}")
                lines.append(f"New Value: {log.new_value}")
            elif log.action == "CREATE":
                lines.append(f"Created: {log.new_value}")
            elif log.action == "DELETE":
                lines.append(f"Deleted: {log.old_value}")

        return "\n".join(lines)


def get_info(self: CLI, as_json: bool = False) -> str:
    """Get database information.

    Args:
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    info = self.repo.db.get_database_info()
    return self.format_output(info, as_json)


def get_summary(self: CLI, as_json: bool = False) -> str:
    """Get summary statistics of issues.

    Args:
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    summary = self.repo.get_summary()
    return self.format_output(summary, as_json)


def get_report(
    self: CLI,
    group_by: str = "status",
    as_json: bool = False,
) -> str:
    """Get detailed report of issues.

    Args:
        group_by: Group by 'status' or 'priority'.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    report = self.repo.get_report(group_by=group_by)
    return self.format_output(report, as_json)
