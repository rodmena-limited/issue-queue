"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from issuedb.models import Issue

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def start_timer(self: IssueRepository, issue_id: int, note: str | None = None) -> dict[str, Any]:
    """Start a timer for an issue.

    Args:
        issue_id: ID of the issue to track time for.
        note: Optional note about what work is being done.

    Returns:
        Dictionary with timer information.

    Raises:
        ValueError: If issue not found or timer already running for this issue.
    """
    # Verify issue exists
    issue = self.get_issue(issue_id)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found")

    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Check if there's already a running timer for this issue
        cursor.execute(
            """
            SELECT id FROM time_entries
            WHERE issue_id = ? AND ended_at IS NULL
        """,
            (issue_id,),
        )
        if cursor.fetchone():
            raise ValueError(f"Timer already running for issue {issue_id}")

        # Create new time entry
        started_at = datetime.now()
        cursor.execute(
            """
            INSERT INTO time_entries (issue_id, started_at, note)
            VALUES (?, ?, ?)
        """,
            (issue_id, started_at.isoformat(), note),
        )

        entry_id = cursor.lastrowid

        return {
            "id": entry_id,
            "issue_id": issue_id,
            "started_at": started_at.isoformat(),
            "note": note,
        }


def stop_timer(self: IssueRepository, issue_id: int | None = None) -> dict[str, Any]:
    """Stop a running timer.

    Args:
        issue_id: Optional issue ID. If not provided, stops the most recent running timer.

    Returns:
        Dictionary with completed timer information including duration.

    Raises:
        ValueError: If no running timer found.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Find running timer
        if issue_id:
            cursor.execute(
                """
                SELECT * FROM time_entries
                WHERE issue_id = ? AND ended_at IS NULL
                ORDER BY started_at DESC
                LIMIT 1
            """,
                (issue_id,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM time_entries
                WHERE ended_at IS NULL
                ORDER BY started_at DESC
                LIMIT 1
            """
            )

        row = cursor.fetchone()
        if not row:
            if issue_id:
                raise ValueError(f"No running timer found for issue {issue_id}")
            else:
                raise ValueError("No running timer found")

        # Stop the timer
        ended_at = datetime.now()
        started_at = datetime.fromisoformat(row["started_at"])
        duration_seconds = int((ended_at - started_at).total_seconds())

        cursor.execute(
            """
            UPDATE time_entries
            SET ended_at = ?, duration_seconds = ?
            WHERE id = ?
        """,
            (ended_at.isoformat(), duration_seconds, row["id"]),
        )

        return {
            "id": row["id"],
            "issue_id": row["issue_id"],
            "started_at": row["started_at"],
            "ended_at": ended_at.isoformat(),
            "duration_seconds": duration_seconds,
            "note": row["note"],
        }


def get_running_timers(self: IssueRepository) -> list[dict[str, Any]]:
    """Get all currently running timers.

    Returns:
        List of dictionaries with running timer information.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT te.*, i.title
            FROM time_entries te
            JOIN issues i ON te.issue_id = i.id
            WHERE te.ended_at IS NULL
            ORDER BY te.started_at DESC
        """
        )
        rows = cursor.fetchall()

        timers = []
        for row in rows:
            started_at = datetime.fromisoformat(row["started_at"])
            elapsed_seconds = int((datetime.now() - started_at).total_seconds())

            timers.append(
                {
                    "id": row["id"],
                    "issue_id": row["issue_id"],
                    "issue_title": row["title"],
                    "started_at": row["started_at"],
                    "elapsed_seconds": elapsed_seconds,
                    "note": row["note"],
                }
            )

        return timers


def get_time_entries(self: IssueRepository, issue_id: int) -> list[dict[str, Any]]:
    """Get all time entries for an issue.

    Args:
        issue_id: ID of the issue.

    Returns:
        List of time entry dictionaries.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM time_entries
            WHERE issue_id = ?
            ORDER BY started_at DESC
        """,
            (issue_id,),
        )
        rows = cursor.fetchall()

        entries = []
        for row in rows:
            entry = {
                "id": row["id"],
                "issue_id": row["issue_id"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "duration_seconds": row["duration_seconds"],
                "note": row["note"],
            }
            entries.append(entry)

        return entries


def set_estimate(self: IssueRepository, issue_id: int, hours: float) -> Issue | None:
    """Set time estimate for an issue.

    Args:
        issue_id: ID of the issue.
        hours: Estimated hours to complete the issue.

    Returns:
        Updated Issue object, or None if issue not found.

    Raises:
        ValueError: If hours is negative.
    """
    if hours < 0:
        raise ValueError("Estimated hours must be non-negative")

    # Use a single connection for the entire operation
    with self.db.get_connection() as conn:
        # Get current issue for audit logging
        current_issue = self._get_issue_with_conn(conn, issue_id)
        if not current_issue:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE issues
            SET estimated_hours = ?, updated_at = ?
            WHERE id = ?
        """,
            (hours, datetime.now().isoformat(), issue_id),
        )

        # Log the change in audit log
        old_value = getattr(current_issue, "estimated_hours", None)
        self._log_audit(
            conn,
            issue_id,
            "UPDATE",
            "estimated_hours",
            str(old_value) if old_value is not None else None,
            str(hours),
        )

        return self._get_issue_with_conn(conn, issue_id)


def get_time_report(
    self: IssueRepository, period: str = "all", issue_id: int | None = None
) -> dict[str, Any]:
    """Generate a time report for specified period.

    Args:
        period: Report period - 'week', 'month', or 'all'.
        issue_id: Optional issue ID to filter by specific issue.

    Returns:
        Dictionary with time report data.

    Raises:
        ValueError: If invalid period specified.
    """
    if period not in ["week", "month", "all"]:
        raise ValueError("Period must be 'week', 'month', or 'all'")

    # Calculate date range
    now = datetime.now()
    if period == "week":
        start_date = now - timedelta(days=7)
        period_label = "This Week"
    elif period == "month":
        start_date = now - timedelta(days=30)
        period_label = "This Month"
    else:
        start_date = datetime(1970, 1, 1)
        period_label = "All Time"

    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Build query based on filters
        query = """
            SELECT
                i.id,
                i.title,
                i.estimated_hours,
                SUM(te.duration_seconds) as total_seconds,
                COUNT(te.id) as entry_count
            FROM issues i
            LEFT JOIN time_entries te
                ON i.id = te.issue_id
                AND te.ended_at IS NOT NULL
                AND te.started_at >= ?
        """
        params: list[Any] = [start_date.isoformat()]

        if issue_id:
            query += " WHERE i.id = ?"
            params.append(issue_id)

        query += " GROUP BY i.id"

        # Keeping the time predicates in the JOIN (not WHERE) preserves the LEFT
        # JOIN semantics, so an issue with an estimate but no logged time this
        # period is no longer silently dropped. When not filtering to a single
        # issue, hide issues that have neither tracked time nor an estimate so the
        # report isn't flooded with untouched issues.
        if not issue_id:
            query += (
                " HAVING SUM(te.duration_seconds) IS NOT NULL"
                " OR i.estimated_hours IS NOT NULL"
            )

        query += " ORDER BY total_seconds DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Process results
        issues = []
        total_seconds = 0

        for row in rows:
            seconds = row["total_seconds"] or 0
            total_seconds += seconds
            hours = seconds / 3600
            estimated_hours = row["estimated_hours"]

            issue_data = {
                "issue_id": row["id"],
                "title": row["title"],
                "total_seconds": seconds,
                "total_hours": round(hours, 2),
                "estimated_hours": estimated_hours,
                "entry_count": row["entry_count"],
            }

            # Calculate if over/under estimate
            if estimated_hours:
                issue_data["over_estimate"] = hours > estimated_hours
                issue_data["difference_hours"] = round(hours - estimated_hours, 2)
            else:
                issue_data["over_estimate"] = None
                issue_data["difference_hours"] = None

            issues.append(issue_data)

        return {
            "period": period,
            "period_label": period_label,
            "total_seconds": total_seconds,
            "total_hours": round(total_seconds / 3600, 2),
            "issues": issues,
            "issue_count": len(issues),
        }

# Template management methods
