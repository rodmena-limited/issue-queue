"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import (
    Issue,
    Priority,
    Status,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def create_issue(self: IssueRepository, issue: Issue) -> Issue:
    """Create a new issue.

    Args:
        issue: Issue object to create.

    Returns:
        Issue: Created issue with assigned ID.

    Raises:
        ValueError: If required fields are missing.
    """
    if not issue.title:
        raise ValueError("Title is required")

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO issues (title, description, priority, status,
                               created_at, updated_at, estimated_hours, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                issue.title,
                issue.description,
                issue.priority.value,
                issue.status.value,
                issue.created_at.isoformat(),
                issue.updated_at.isoformat(),
                issue.estimated_hours,
                issue.due_date.isoformat() if issue.due_date else None,
            ),
        )

        issue.id = cursor.lastrowid
        assert issue.id is not None  # Guaranteed by successful insert

        # Log creation in audit log
        self._log_audit(
            conn,
            issue.id,
            "CREATE",
            None,
            None,
            json.dumps(issue.to_dict()),
        )

    return issue


def update_issue(self: IssueRepository, issue_id: int, **updates: Any) -> Issue | None:
    """Update an issue.

    Args:
        issue_id: ID of the issue to update.
        **updates: Fields to update (title, description, priority, status).

    Returns:
        Updated Issue if found, None otherwise.

    Raises:
        ValueError: If invalid field names or values are provided.
    """
    # Use a single connection for the entire operation to avoid deadlocks
    with self.db.get_connection() as conn:
        # Get current issue for audit logging
        current_issue = self._get_issue_with_conn(conn, issue_id)
        if not current_issue:
            return None

        # Validate and prepare updates
        allowed_fields = {"title", "description", "priority", "status", "due_date"}
        update_fields: list[str] = []
        update_values: list[Any] = []
        audit_entries: list[tuple[str, str, str]] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                raise ValueError(f"Cannot update field: {field}")

            if field == "title" and (value is None or not str(value).strip()):
                raise ValueError("Title is required")

            # Validate and convert enums
            old_value: Any
            if field == "priority":
                value = Priority.from_string(value).value
                old_value = current_issue.priority.value
            elif field == "status":
                value = Status.from_string(value).value
                old_value = current_issue.status.value
            elif field == "due_date":
                # Empty/None clears the due date; otherwise normalise to a canonical
                # ISO string so re-setting the same date is a no-op (avoids spurious
                # writes and audit-log entries).
                if value is None or (isinstance(value, str) and not value.strip()):
                    value = None
                else:
                    try:
                        value = datetime.fromisoformat(value).isoformat()
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid date format for {field}: {value}") from None
                due_date = current_issue.due_date
                old_value = due_date.isoformat() if due_date else None
            else:
                old_value = getattr(current_issue, field)

            # Only update if value changed
            if str(old_value) != str(value):
                update_fields.append(f"{field} = ?")
                update_values.append(value)
                audit_entries.append((field, str(old_value), str(value)))

        if not update_fields:
            return current_issue  # No changes

        # Always update the updated_at timestamp
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat())

        # Add issue_id for WHERE clause
        update_values.append(issue_id)

        cursor = conn.cursor()
        query = f"UPDATE issues SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, update_values)

        # Log each field change in audit log
        for field, old_val, new_val in audit_entries:
            assert issue_id is not None  # Already validated above
            self._log_audit(
                conn,
                issue_id,
                "UPDATE",
                field,
                old_val,
                new_val,
            )

        # Return updated issue using the same connection
        return self._get_issue_with_conn(conn, issue_id)


def bulk_update_issues(
    self: IssueRepository,
    new_status: str | None = None,
    new_priority: str | None = None,
    filter_status: str | None = None,
    filter_priority: str | None = None,
) -> int:
    """Bulk update issues matching filters.

    Args:
        new_status: New status to set.
        new_priority: New priority to set.
        filter_status: Filter by current status.
        filter_priority: Filter by current priority.

    Returns:
        Number of issues updated.

    Raises:
        ValueError: If invalid field names or values are provided.
    """
    update_fields: list[str] = []
    update_values: list[Any] = []

    # Prepare updates
    if new_status:
        status_value = Status.from_string(new_status).value
        update_fields.append("status = ?")
        update_values.append(status_value)

    if new_priority:
        priority_value = Priority.from_string(new_priority).value
        update_fields.append("priority = ?")
        update_values.append(priority_value)

    if not update_fields:
        return 0  # No changes

    # Always update the updated_at timestamp
    update_fields.append("updated_at = ?")
    update_values.append(datetime.now().isoformat())

    # Build WHERE clause for filters
    where_conditions = []
    where_values = []
    if filter_status:
        filter_status_enum = Status.from_string(filter_status)
        where_conditions.append("status = ?")
        where_values.append(filter_status_enum.value)
    if filter_priority:
        filter_priority_enum = Priority.from_string(filter_priority)
        where_conditions.append("priority = ?")
        where_values.append(filter_priority_enum.value)

    # Only touch rows that would actually change so updated_at is not rewritten
    # (and the row not counted) for issues already at the target values.
    change_checks = []
    change_values = []
    if new_status:
        change_checks.append("status != ?")
        change_values.append(Status.from_string(new_status).value)
    if new_priority:
        change_checks.append("priority != ?")
        change_values.append(Priority.from_string(new_priority).value)
    where_conditions.append("(" + " OR ".join(change_checks) + ")")
    where_values.extend(change_values)

    where_clause = f" WHERE {' AND '.join(where_conditions)}"

    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Get affected issues for audit logging
        select_query = f"SELECT * FROM issues{where_clause}"
        cursor.execute(select_query, where_values)
        affected_issues = [self._row_to_issue(row) for row in cursor.fetchall()]

        if not affected_issues:
            return 0

        # Perform bulk update
        query = f"UPDATE issues SET {', '.join(update_fields)}{where_clause}"
        cursor.execute(query, update_values + where_values)

        # Log audit entries for each affected issue
        for issue in affected_issues:
            assert issue.id is not None  # Issues from DB always have ID
            if new_status:
                old_value = issue.status.value
                new_value = Status.from_string(new_status).value
                if old_value != new_value:
                    self._log_audit(
                        conn,
                        issue.id,
                        "BULK_UPDATE",
                        "status",
                        old_value,
                        new_value,
                    )

            if new_priority:
                old_value = issue.priority.value
                new_value = Priority.from_string(new_priority).value
                if old_value != new_value:
                    self._log_audit(
                        conn,
                        issue.id,
                        "BULK_UPDATE",
                        "priority",
                        old_value,
                        new_value,
                    )

        return len(affected_issues)


def delete_issue(self: IssueRepository, issue_id: int) -> bool:
    """Delete an issue.

    Args:
        issue_id: ID of the issue to delete.

    Returns:
        True if issue was deleted, False if not found.
    """
    # Use a single connection for the entire operation to avoid deadlocks
    with self.db.get_connection() as conn:
        # Get issue details for audit log before deletion
        issue = self._get_issue_with_conn(conn, issue_id)
        if not issue:
            return False

        cursor = conn.cursor()
        cursor.execute("DELETE FROM issues WHERE id = ?", (issue_id,))

        # Log deletion in audit log (with full issue data)
        self._log_audit(
            conn,
            issue_id,
            "DELETE",
            None,
            json.dumps(issue.to_dict()),
            None,
        )

        return cursor.rowcount > 0


def get_next_issue(
    self: IssueRepository, status: str | None = None, log_fetch: bool = True
) -> Issue | None:
    """Get the next issue based on priority and creation date (FIFO within priority).

    Skips issues that are blocked by unresolved (open/in-progress) issues.

    Args:
        status: Filter by status (defaults to 'open' if not specified).
        log_fetch: If True, log this fetch in the audit log (default: True).

    Returns:
        Next Issue to work on, or None if no issues match.
    """
    query = """
        SELECT * FROM issues
        WHERE 1=1
    """
    params: list[Any] = []

    # Default to open issues if status not specified
    if status:
        # Bind the normalized enum value so accepted forms like "in_progress"
        # actually match the stored value.
        query += " AND status = ?"
        params.append(Status.from_string(status).value)
    else:
        query += " AND status = ?"
        params.append(Status.OPEN.value)

    # Exclude blocked issues (issues with unresolved blockers). A blocker that
    # is closed or wont-do is resolved — treating wont-do as unresolved would
    # hide its dependents forever.
    query += """
        AND id NOT IN (
            SELECT DISTINCT d.blocked_id
            FROM issue_dependencies d
            INNER JOIN issues blocker ON blocker.id = d.blocker_id
            WHERE blocker.status NOT IN ('closed', 'wont-do')
        )
    """

    # Order by priority (critical first) then by creation date (FIFO)
    query += """
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END,
            created_at ASC
        LIMIT 1
    """

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()

        if row:
            issue = self._row_to_issue(row)
            assert issue.id is not None  # Issues from DB always have ID
            issue.tags = self._get_issue_tags_with_conn(conn, issue.id)
            # Log the fetch in audit log
            if log_fetch and issue.id is not None:
                self._log_audit(
                    conn,
                    issue.id,
                    "FETCH",
                    None,
                    None,
                    json.dumps(issue.to_dict()),
                )
            return issue
        return None
