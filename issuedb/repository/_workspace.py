"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import Issue

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def get_active_issue(self: IssueRepository) -> tuple[Issue, datetime] | None:
    """Get the currently active issue and when it was started.

    Returns:
        Tuple of (Issue, started_at) if there's an active issue, None otherwise.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT active_issue_id, started_at
            FROM workspace_state
            WHERE id = 1
        """
        )
        row = cursor.fetchone()

        if row and row["active_issue_id"]:
            issue = self.get_issue(row["active_issue_id"])
            if issue:
                started_at = datetime.fromisoformat(row["started_at"])
                return (issue, started_at)

        return None


def _set_status_with_conn(
    self: IssueRepository, conn: Any, issue_id: int, new_status: str, current_status: str
) -> None:
    """Set an issue's status within an existing transaction (with audit logging).

    Used so a workspace change and the issue's status change commit together.
    """
    if current_status == new_status:
        return
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE issues SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, datetime.now().isoformat(), issue_id),
    )
    self._log_audit(conn, issue_id, "UPDATE", "status", current_status, new_status)


def start_issue(self: IssueRepository, issue_id: int) -> tuple[Issue, datetime]:
    """Set an issue as the active issue and update its status to in-progress.

    Args:
        issue_id: ID of the issue to start.

    Returns:
        Tuple of (Issue, started_at).

    Raises:
        ValueError: If issue not found.
    """
    started_at = datetime.now()

    # Do the workspace write and the status change in one transaction so the
    # issue can never end up "active" without also being marked in-progress.
    with self.db.get_connection() as conn:
        current = self._get_issue_with_conn(conn, issue_id)
        if not current:
            raise ValueError(f"Issue {issue_id} not found")

        cursor = conn.cursor()

        # Initialize workspace_state if not exists
        cursor.execute(
            """
            INSERT OR IGNORE INTO workspace_state (id, active_issue_id, started_at)
            VALUES (1, NULL, NULL)
        """
        )

        # Update workspace_state
        cursor.execute(
            """
            UPDATE workspace_state
            SET active_issue_id = ?, started_at = ?
            WHERE id = 1
        """,
            (issue_id, started_at.isoformat()),
        )

        # Log workspace action in audit log
        self._log_audit(
            conn,
            issue_id,
            "WORKSPACE_START",
            None,
            None,
            started_at.isoformat(),
        )

        # Auto-update issue status to in-progress (same transaction)
        self._set_status_with_conn(conn, issue_id, "in-progress", current.status.value)
        updated_issue = self._get_issue_with_conn(conn, issue_id)
        assert updated_issue is not None

    return (updated_issue, started_at)


def stop_issue(
    self: IssueRepository, close: bool = False
) -> tuple[Issue, datetime, datetime] | None:
    """Clear the active issue and optionally close it.

    Args:
        close: If True, also set the issue status to closed.

    Returns:
        Tuple of (Issue, started_at, stopped_at) if there was an active issue,
        None otherwise.
    """
    active = self.get_active_issue()
    if not active:
        return None

    issue, started_at = active
    stopped_at = datetime.now()

    # Clear the workspace and (optionally) close the issue in one transaction.
    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Clear workspace_state
        cursor.execute(
            """
            UPDATE workspace_state
            SET active_issue_id = NULL, started_at = NULL
            WHERE id = 1
        """
        )

        # Log workspace action in audit log
        assert issue.id is not None
        self._log_audit(
            conn,
            issue.id,
            "WORKSPACE_STOP",
            None,
            started_at.isoformat(),
            stopped_at.isoformat(),
        )

        # Optionally close the issue (same transaction)
        if close and issue.id:
            current = self._get_issue_with_conn(conn, issue.id)
            if current:
                self._set_status_with_conn(conn, issue.id, "closed", current.status.value)
                refreshed = self._get_issue_with_conn(conn, issue.id)
                if refreshed:
                    issue = refreshed

    return (issue, started_at, stopped_at)


def get_workspace_status(self: IssueRepository) -> dict[str, Any]:
    """Get comprehensive workspace status including git info and recent activity.

    Returns:
        Dictionary with workspace status information.
    """
    import subprocess
    from pathlib import Path

    status: dict[str, Any] = {}

    # Get active issue
    active = self.get_active_issue()
    if active:
        issue, started_at = active
        time_spent = datetime.now() - started_at
        hours = int(time_spent.total_seconds() // 3600)
        minutes = int((time_spent.total_seconds() % 3600) // 60)

        status["active_issue"] = {
            "id": issue.id,
            "title": issue.title,
            "status": issue.status.value,
            "priority": issue.priority.value,
            "started_at": started_at.isoformat(),
            "time_spent": f"{hours}h {minutes}m",
            "time_spent_seconds": int(time_spent.total_seconds()),
        }
    else:
        status["active_issue"] = None

    # Get git branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path.cwd(),
        )
        if result.returncode == 0:
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=Path.cwd(),
            )
            if branch_result.returncode == 0:
                status["git_branch"] = branch_result.stdout.strip()

            # Get uncommitted files count
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=Path.cwd(),
            )
            if status_result.returncode == 0:
                uncommitted = [
                    line for line in status_result.stdout.split("\n") if line.strip()
                ]
                status["uncommitted_files"] = len(uncommitted)
        else:
            status["git_branch"] = None
            status["uncommitted_files"] = None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        status["git_branch"] = None
        status["uncommitted_files"] = None

    # Get recent workspace activity (last 5 start/stop events)
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT al.issue_id, al.action, al.new_value, al.timestamp, i.title
            FROM audit_logs al
            LEFT JOIN issues i ON al.issue_id = i.id
            WHERE al.action IN ('WORKSPACE_START', 'WORKSPACE_STOP')
            ORDER BY al.timestamp DESC
            LIMIT 5
        """
        )
        rows = cursor.fetchall()

        recent_activity = []
        for row in rows:
            activity: dict[str, Any] = {
                "issue_id": row["issue_id"],
                "action": row["action"],
                "timestamp": row["timestamp"],
            }
            if row["title"]:
                activity["title"] = row["title"]

            # Calculate time ago
            timestamp = datetime.fromisoformat(row["timestamp"])
            time_diff = datetime.now() - timestamp
            if time_diff.days > 0:
                activity["time_ago"] = f"{time_diff.days}d ago"
            elif time_diff.seconds >= 3600:
                activity["time_ago"] = f"{time_diff.seconds // 3600}h ago"
            elif time_diff.seconds >= 60:
                activity["time_ago"] = f"{time_diff.seconds // 60}m ago"
            else:
                activity["time_ago"] = "just now"

            recent_activity.append(activity)

        status["recent_activity"] = recent_activity

    return status

# Time Tracking Methods
