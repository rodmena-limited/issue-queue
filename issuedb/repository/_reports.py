"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import (
    AuditLog,
    Issue,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def get_audit_logs(self: IssueRepository, issue_id: int | None = None) -> list[AuditLog]:
    """Get audit logs for issues.

    Args:
        issue_id: Filter by issue ID.

    Returns:
        List of audit log entries.
    """
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []

    if issue_id:
        query += " AND issue_id = ?"
        params.append(issue_id)

    query += " ORDER BY id DESC"

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        logs = []
        for row in rows:
            log = AuditLog(
                id=row["id"],
                issue_id=row["issue_id"],
                action=row["action"],
                field_name=row["field_name"],
                old_value=row["old_value"],
                new_value=row["new_value"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            logs.append(log)

        return logs


def get_last_fetched(self: IssueRepository, limit: int = 1) -> list[Issue]:
    """Get the last fetched issue(s) from the audit log.

    Args:
        limit: Maximum number of fetched issues to return (default: 1).

    Returns:
        List of Issue objects that were last fetched via get-next.
        Issues are returned in reverse chronological order (most recent first).
        If an issue has been deleted, it will not be included.
    """
    query = """
        SELECT DISTINCT al.issue_id, al.new_value, al.timestamp, i.id as current_id
        FROM audit_logs al
        LEFT JOIN issues i ON al.issue_id = i.id
        WHERE al.action = 'FETCH'
        ORDER BY al.id DESC
    """

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        issues = []
        seen_ids: set[int] = set()

        for row in rows:
            issue_id = row["issue_id"]

            # Skip duplicates (same issue fetched multiple times)
            if issue_id in seen_ids:
                continue

            # If issue still exists, get current state (reuse this connection to
            # avoid a nested get_connection() that would commit mid-iteration).
            if row["current_id"] is not None:
                issue = self._get_issue_with_conn(conn, issue_id)
                if issue:
                    issues.append(issue)
                    seen_ids.add(issue_id)
            else:
                # Issue was deleted, reconstruct from audit log
                if row["new_value"]:
                    try:
                        issue_data = json.loads(row["new_value"])
                        issue = Issue.from_dict(issue_data)
                        issue.id = issue_id
                        issues.append(issue)
                        seen_ids.add(issue_id)
                    except (json.JSONDecodeError, KeyError):
                        # Skip if we can't reconstruct
                        continue

            if len(issues) >= limit:
                break

        return issues


def get_summary(self: IssueRepository) -> dict[str, Any]:
    """Get summary statistics of issues.

    Returns:
        Dictionary with issue statistics including counts by status and priority.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Get total count
        query = "SELECT COUNT(*) as count FROM issues"
        cursor.execute(query)
        total_count = cursor.fetchone()["count"]

        # Get count by status
        query = """
            SELECT status, COUNT(*) as count
            FROM issues
            GROUP BY status
        """
        cursor.execute(query)
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        # Get count by priority
        query = """
            SELECT priority, COUNT(*) as count
            FROM issues
            GROUP BY priority
        """
        cursor.execute(query)
        priority_counts = {row["priority"]: row["count"] for row in cursor.fetchall()}

        # Calculate percentages
        status_percentages = {}
        if total_count > 0:
            for status in ["open", "in-progress", "closed", "wont-do"]:
                count = status_counts.get(status, 0)
                status_percentages[status] = round((count / total_count) * 100, 1)

        priority_percentages = {}
        if total_count > 0:
            for priority in ["low", "medium", "high", "critical"]:
                count = priority_counts.get(priority, 0)
                priority_percentages[priority] = round((count / total_count) * 100, 1)

        return {
            "total_issues": total_count,
            "by_status": {
                "open": status_counts.get("open", 0),
                "in_progress": status_counts.get("in-progress", 0),
                "closed": status_counts.get("closed", 0),
                "wont_do": status_counts.get("wont-do", 0),
            },
            "by_priority": {
                "low": priority_counts.get("low", 0),
                "medium": priority_counts.get("medium", 0),
                "high": priority_counts.get("high", 0),
                "critical": priority_counts.get("critical", 0),
            },
            "status_percentages": status_percentages,
            "priority_percentages": priority_percentages,
        }


def get_report(self: IssueRepository, group_by: str = "status") -> dict[str, Any]:
    """Get detailed report of issues grouped by status or priority.

    Args:
        group_by: Group issues by 'status' or 'priority' (default: 'status').

    Returns:
        Dictionary with grouped issue lists.
    """
    if group_by not in ["status", "priority"]:
        raise ValueError("group_by must be 'status' or 'priority'")

    # Get all issues
    issues = self.list_issues()

    # Group issues
    grouped: dict[str, list[Issue]]
    if group_by == "status":
        grouped = {
            "open": [],
            "in_progress": [],
            "closed": [],
            "wont_do": [],
        }
        # Map hyphenated status values to the underscored group keys.
        status_key_map = {
            "open": "open",
            "in-progress": "in_progress",
            "closed": "closed",
            "wont-do": "wont_do",
        }
        for issue in issues:
            key = status_key_map.get(issue.status.value, issue.status.value)
            grouped.setdefault(key, []).append(issue)
    else:  # group by priority
        grouped = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }
        for issue in issues:
            grouped[issue.priority.value].append(issue)

    # Convert to dict format
    result: dict[str, Any] = {
        "group_by": group_by,
        "total_issues": len(issues),
        "groups": {},
    }

    for key, issue_list in grouped.items():
        result["groups"][key] = {
            "count": len(issue_list),
            "issues": [issue.to_dict() for issue in issue_list],
        }

    return result
