"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import (
    Issue,
    Priority,
    Status,
    Tag,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def _log_audit(
    self: IssueRepository,
    conn: Any,
    issue_id: int,
    action: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    """Log an audit entry for an issue change.

    Args:
        conn: Database connection to use
        issue_id: ID of the affected issue
        action: Action type (CREATE, UPDATE, DELETE)
        field_name: Name of the field that changed
        old_value: Previous value
        new_value: New value
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO audit_logs (issue_id, action, field_name, old_value, new_value)
        VALUES (?, ?, ?, ?, ?)
    """,
        (issue_id, action, field_name, old_value, new_value),
    )


def _row_to_issue(self: IssueRepository, row: Any) -> Issue:
    """Convert a database row to an Issue object.

    Args:
        row: SQLite row object.

    Returns:
        Issue object.
    """
    issue = Issue(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=Priority.from_string(row["priority"]),
        status=Status.from_string(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )

    # NOTE: use row.keys(), not ``"col" in row`` — sqlite3.Row.__contains__ tests
    # values, not column names, so the membership form silently never matched and
    # due_date / estimated_hours were never read back onto the Issue.
    row_keys = row.keys()
    if "estimated_hours" in row_keys and row["estimated_hours"] is not None:
        issue.estimated_hours = row["estimated_hours"]

    if "due_date" in row_keys and row["due_date"] is not None:
        issue.due_date = datetime.fromisoformat(row["due_date"])

    return issue


def get_issue(self: IssueRepository, issue_id: int) -> Issue | None:
    """Get an issue by ID.

    Args:
        issue_id: ID of the issue to retrieve.

    Returns:
        Issue if found, None otherwise.
    """
    with self.db.get_connection() as conn:
        return self._get_issue_with_conn(conn, issue_id)


def _get_issue_with_conn(self: IssueRepository, conn: Any, issue_id: int) -> Issue | None:
    """Get an issue by ID using an existing connection.

    Args:
        conn: Database connection to use.
        issue_id: ID of the issue to retrieve.

    Returns:
        Issue if found, None otherwise.

    Note:
        Internal method to avoid nested connections.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM issues WHERE id = ?
    """,
        (issue_id,),
    )
    row = cursor.fetchone()

    if row:
        issue = self._row_to_issue(row)
        # Populate tags using the same connection
        issue.tags = self._get_issue_tags_with_conn(conn, issue_id)
        return issue
    return None


def _get_issue_tags_with_conn(self: IssueRepository, conn: Any, issue_id: int) -> list[Tag]:
    """Get tags for an issue using an existing connection.

    Args:
        conn: Database connection to use.
        issue_id: Issue ID.

    Returns:
        List of Tag objects.

    Note:
        Internal method to avoid nested connections.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.* FROM tags t
        JOIN issue_tags it ON t.id = it.tag_id
        WHERE it.issue_id = ?
        ORDER BY t.name ASC
    """,
        (issue_id,),
    )
    rows = cursor.fetchall()
    return [
        Tag(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]
