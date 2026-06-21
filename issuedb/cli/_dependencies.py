"""Dependency management CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from issuedb.models import Status

if TYPE_CHECKING:
    from issuedb.cli import CLI


def block_issue(self: CLI, issue_id: int, blocker_id: int, as_json: bool = False) -> str:
    """Mark an issue as blocked by another issue.

    Args:
        issue_id: ID of the issue being blocked.
        blocker_id: ID of the issue that blocks.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If issues don't exist or operation is invalid.
    """
    try:
        added = self.repo.add_dependency(issue_id, blocker_id)
        if added:
            result = {
                "message": f"Issue {issue_id} is now blocked by issue {blocker_id}",
                "blocked_id": issue_id,
                "blocker_id": blocker_id,
            }
        else:
            result = {
                "message": f"Issue {issue_id} is already blocked by issue {blocker_id}",
                "blocked_id": issue_id,
                "blocker_id": blocker_id,
            }
        return self.format_output(result, as_json)
    except ValueError as e:
        raise ValueError(str(e)) from e


def unblock_issue(
    self: CLI, issue_id: int, blocker_id: int | None = None, as_json: bool = False
) -> str:
    """Remove block relationship(s) from an issue.

    Args:
        issue_id: ID of the blocked issue.
        blocker_id: ID of the blocker issue (if None, removes all blockers).
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    count = self.repo.remove_dependency(issue_id, blocker_id)

    if blocker_id:
        if count > 0:
            result = {
                "message": f"Removed blocker {blocker_id} from issue {issue_id}",
                "removed_count": count,
            }
        else:
            result = {
                "message": f"No dependency found between issue {issue_id} "
                f"and blocker {blocker_id}",
                "removed_count": 0,
            }
    else:
        result = {
            "message": f"Removed {count} blocker(s) from issue {issue_id}",
            "removed_count": count,
        }

    return self.format_output(result, as_json)


def show_dependencies(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """Show dependency graph for an issue.

    Args:
        issue_id: ID of the issue.
        as_json: Output as JSON.

    Returns:
        Formatted output showing blockers and blocking issues.

    Raises:
        ValueError: If issue not found.
    """
    issue = self.repo.get_issue(issue_id)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found")

    blockers = self.repo.get_blockers(issue_id)
    blocking = self.repo.get_blocking(issue_id)
    is_blocked = self.repo.is_blocked(issue_id)

    if as_json:
        result = {
            "issue_id": issue_id,
            "title": issue.title,
            "is_blocked": is_blocked,
            "blocked_by": [
                {
                    "id": b.id,
                    "title": b.title,
                    "status": b.status.value,
                    "priority": b.priority.value,
                }
                for b in blockers
            ],
            "blocking": [
                {
                    "id": b.id,
                    "title": b.title,
                    "status": b.status.value,
                    "priority": b.priority.value,
                }
                for b in blocking
            ],
        }
        return json.dumps(result, indent=2)
    else:
        lines = []
        lines.append(f"Dependencies for Issue #{issue_id}: {issue.title}")
        lines.append("=" * 60)
        lines.append("")

        if blockers:
            lines.append(f"Blocked by ({len(blockers)} issue(s)):")
            for blocker in blockers:
                status_marker = "OPEN" if blocker.status != Status.CLOSED else "CLOSED"
                lines.append(
                    f"  - Issue #{blocker.id}: {blocker.title} "
                    f"[{status_marker}, {blocker.priority.value}]"
                )
            if is_blocked:
                lines.append("\nThis issue is BLOCKED (has unresolved blockers)")
        else:
            lines.append("Blocked by: None")

        lines.append("")

        if blocking:
            lines.append(f"Blocking ({len(blocking)} issue(s)):")
            for blocked in blocking:
                status_marker = "OPEN" if blocked.status != Status.CLOSED else "CLOSED"
                lines.append(
                    f"  - Issue #{blocked.id}: {blocked.title} "
                    f"[{status_marker}, {blocked.priority.value}]"
                )
        else:
            lines.append("Blocking: None")

        return "\n".join(lines)


def list_blocked_issues(self: CLI, status: str | None = None, as_json: bool = False) -> str:
    """List all blocked issues.

    Args:
        status: Optional filter by status.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    issues = self.repo.get_all_blocked_issues(status=status)

    if as_json:
        result = []
        for issue in issues:
            if issue.id is None:
                continue
            blockers = self.repo.get_blockers(issue.id)
            issue_dict = issue.to_dict()
            issue_dict["blockers"] = [
                {"id": b.id, "title": b.title, "status": b.status.value} for b in blockers
            ]
            result.append(issue_dict)
        return json.dumps(result, indent=2)
    else:
        if not issues:
            return "No blocked issues found."

        lines = [f"Found {len(issues)} blocked issue(s):\n"]
        for issue in issues:
            if issue.id is None:
                continue
            blockers = self.repo.get_blockers(issue.id)
            blocker_ids = ", ".join([f"#{b.id}" for b in blockers])
            lines.append(
                f"Issue #{issue.id}: {issue.title} "
                f"[{issue.status.value}, {issue.priority.value}]"
            )
            lines.append(f"  Blocked by: {blocker_ids}")
            lines.append("")

        return "\n".join(lines)
