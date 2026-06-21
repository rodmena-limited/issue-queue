"""Workspace (active issue) CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def workspace_status(self: CLI, as_json: bool = False) -> str:
    """Get workspace status.

    Args:
        as_json: Output as JSON.

    Returns:
        Formatted workspace status.
    """
    status = self.repo.get_workspace_status()

    if as_json:
        return json.dumps(status, indent=2)
    else:
        lines = ["=== Workspace Status ==="]

        # Git branch
        if status.get("git_branch"):
            lines.append(f"Git Branch: {status['git_branch']}")
        else:
            lines.append("Git Branch: (not in git repo)")

        # Active issue
        if status.get("active_issue"):
            active = status["active_issue"]
            lines.append(
                f"Active Issue: #{active['id']} - {active['title']} ({active['status']})"
            )
            lines.append(f"Time on Issue: {active['time_spent']}")
        else:
            lines.append("Active Issue: None")

        # Uncommitted files
        if status.get("uncommitted_files") is not None:
            lines.append(f"Uncommitted Files: {status['uncommitted_files']}")

        # Recent activity
        if status.get("recent_activity"):
            lines.append("")
            lines.append("Recent Activity:")
            for activity in status["recent_activity"]:
                action_str = "started" if activity["action"] == "WORKSPACE_START" else "stopped"
                title = activity.get("title", f"Issue #{activity['issue_id']}")
                lines.append(f"- {title} ({action_str} {activity['time_ago']})")

        return "\n".join(lines)


def start_issue_workspace(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """Start working on an issue.

    Args:
        issue_id: Issue ID to start.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If issue not found.
    """
    issue, started_at = self.repo.start_issue(issue_id)

    if as_json:
        return json.dumps(
            {
                "message": f"Started working on issue {issue_id}",
                "issue": issue.to_dict(),
                "started_at": started_at.isoformat(),
            },
            indent=2,
        )
    else:
        lines = [
            f"Started working on issue #{issue_id}",
            f"Title: {issue.title}",
            f"Status: {issue.status.value}",
            f"Started at: {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        return "\n".join(lines)


def stop_issue_workspace(self: CLI, close: bool = False, as_json: bool = False) -> str:
    """Stop working on the active issue.

    Args:
        close: If True, also close the issue.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """

    result = self.repo.stop_issue(close=close)

    if not result:
        msg = {"message": "No active issue to stop"}
        return json.dumps(msg, indent=2) if as_json else msg["message"]

    issue, started_at, stopped_at = result
    time_spent = stopped_at - started_at
    hours = int(time_spent.total_seconds() // 3600)
    minutes = int((time_spent.total_seconds() % 3600) // 60)

    if as_json:
        return json.dumps(
            {
                "message": f"Stopped working on issue {issue.id}",
                "issue": issue.to_dict(),
                "started_at": started_at.isoformat(),
                "stopped_at": stopped_at.isoformat(),
                "time_spent": f"{hours}h {minutes}m",
                "time_spent_seconds": int(time_spent.total_seconds()),
            },
            indent=2,
        )
    else:
        lines = [
            f"Stopped working on issue #{issue.id}",
            f"Title: {issue.title}",
            f"Time spent: {hours}h {minutes}m",
        ]
        if close:
            lines.append(f"Status: {issue.status.value}")
        return "\n".join(lines)


def get_active_issue_workspace(self: CLI, as_json: bool = False) -> str:
    """Get the currently active issue.

    Args:
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    from datetime import datetime

    active = self.repo.get_active_issue()

    if not active:
        msg = {"message": "No active issue"}
        return json.dumps(msg, indent=2) if as_json else msg["message"]

    issue, started_at = active
    time_spent = datetime.now() - started_at
    hours = int(time_spent.total_seconds() // 3600)
    minutes = int((time_spent.total_seconds() % 3600) // 60)

    if as_json:
        return json.dumps(
            {
                "issue": issue.to_dict(),
                "started_at": started_at.isoformat(),
                "time_spent": f"{hours}h {minutes}m",
                "time_spent_seconds": int(time_spent.total_seconds()),
            },
            indent=2,
        )
    else:
        lines = [
            f"Active Issue: #{issue.id}",
            f"Title: {issue.title}",
            f"Status: {issue.status.value}",
            f"Priority: {issue.priority.value}",
            f"Started at: {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Time spent: {hours}h {minutes}m",
        ]
        return "\n".join(lines)
