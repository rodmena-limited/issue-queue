"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from issuedb.models import (
    Issue,
    Priority,
    Status,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def count_issues(
    self: IssueRepository,
    status: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> int:
    """Count issues matching optional filters.

    Args:
        status: Filter by status.
        priority: Filter by priority.
        due_date: Filter by due date (exact match).
        tag: Filter by tag name.
        keyword: Filter by keyword search in title/description.

    Returns:
        Count of matching issues.
    """
    query = "SELECT COUNT(DISTINCT i.id) as count FROM issues i"
    params: list[Any] = []

    joins = []
    wheres = ["1=1"]

    if tag:
        joins.append("JOIN issue_tags it ON i.id = it.issue_id")
        joins.append("JOIN tags t ON it.tag_id = t.id")
        wheres.append("t.name = ?")
        params.append(tag)

    if status:
        Status.from_string(status)  # Validate status
        wheres.append("i.status = ?")
        params.append(status.lower())

    if priority:
        Priority.from_string(priority)  # Validate priority
        wheres.append("i.priority = ?")
        params.append(priority.lower())

    if due_date:
        wheres.append("date(i.due_date) = date(?)")
        params.append(due_date)

    if keyword:
        wheres.append("(i.title LIKE ? OR i.description LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if joins:
        query += " " + " ".join(joins)

    query += " WHERE " + " AND ".join(wheres)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        return int(result["count"]) if result else 0


def list_issues(
    self: IssueRepository,
    status: str | None = None,
    priority: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    due_date: str | None = None,
    tag: str | None = None,
) -> list[Issue]:
    """List issues with optional filters.

    Args:
        status: Filter by status.
        priority: Filter by priority.
        limit: Maximum number of issues to return.
        offset: Number of issues to skip.
        due_date: Filter by due date (exact match).
        tag: Filter by tag name.

    Returns:
        List of matching issues.
    """
    query = "SELECT DISTINCT i.* FROM issues i"
    params: list[Any] = []

    joins = []
    wheres = ["1=1"]

    if tag:
        joins.append("JOIN issue_tags it ON i.id = it.issue_id")
        joins.append("JOIN tags t ON it.tag_id = t.id")
        wheres.append("t.name = ?")
        params.append(tag)

    if status:
        Status.from_string(status)  # Validate status
        wheres.append("i.status = ?")
        params.append(status.lower())

    if priority:
        Priority.from_string(priority)  # Validate priority
        wheres.append("i.priority = ?")
        params.append(priority.lower())

    if due_date:
        wheres.append("date(i.due_date) = date(?)")
        params.append(due_date)

    if joins:
        query += " " + " ".join(joins)

    query += " WHERE " + " AND ".join(wheres)
    query += " ORDER BY i.created_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)
        if offset:
            query += " OFFSET ?"
            params.append(offset)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_issue(row) for row in rows]


def get_all_issues(self: IssueRepository) -> list[Issue]:
    """Get all issues without any filters or pagination.

    Returns:
        List of all issues in the database.
    """
    query = "SELECT * FROM issues ORDER BY created_at DESC"

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        return [self._row_to_issue(row) for row in rows]


def search_issues(
    self: IssueRepository, keyword: str, limit: int | None = None, offset: int = 0
) -> list[Issue]:
    """Search issues by keyword in title and description.

    Args:
        keyword: Keyword to search for.
        limit: Maximum number of issues to return.
        offset: Number of issues to skip.

    Returns:
        List of matching issues.
    """
    query = """
        SELECT * FROM issues
        WHERE (title LIKE ? OR description LIKE ?)
    """
    params: list[Any] = [f"%{keyword}%", f"%{keyword}%"]

    query += " ORDER BY created_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)
        if offset:
            query += " OFFSET ?"
            params.append(offset)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_issue(row) for row in rows]


def clear_all_issues(self: IssueRepository) -> int:
    """Clear all issues from the database.

    Returns:
        Number of issues deleted.
    """
    # Get all issues for audit logging
    issues = self.list_issues()

    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Log deletion for each issue
        for issue in issues:
            assert issue.id is not None  # Issues from DB always have ID
            self._log_audit(
                conn,
                issue.id,
                "DELETE",
                None,
                json.dumps(issue.to_dict()),
                None,
            )

        # Delete all issues
        cursor.execute("DELETE FROM issues")
        return cursor.rowcount
