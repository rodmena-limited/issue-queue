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


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards so user keywords match literally.

    Without this, a keyword containing ``%`` matches everything and ``_``
    matches any single character.
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _populate_tags(self: IssueRepository, issues: list[Issue]) -> list[Issue]:
    """Attach tags to a list of issues with a single batched query."""
    ids = [issue.id for issue in issues if issue.id is not None]
    if ids:
        tag_map = self.get_tags_for_issues(ids)
        for issue in issues:
            if issue.id is not None:
                issue.tags = tag_map.get(issue.id, [])
    return issues


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
        # Bind the normalized enum value: the validator accepts forms like
        # "in_progress" or " open " that would never match the stored value.
        wheres.append("i.status = ?")
        params.append(Status.from_string(status).value)

    if priority:
        wheres.append("i.priority = ?")
        params.append(Priority.from_string(priority).value)

    if due_date:
        wheres.append("date(i.due_date) = date(?)")
        params.append(due_date)

    if keyword:
        wheres.append("(i.title LIKE ? ESCAPE '\\' OR i.description LIKE ? ESCAPE '\\')")
        escaped = f"%{_escape_like(keyword)}%"
        params.extend([escaped, escaped])

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
    keyword: str | None = None,
) -> list[Issue]:
    """List issues with optional filters.

    Args:
        status: Filter by status.
        priority: Filter by priority.
        limit: Maximum number of issues to return.
        offset: Number of issues to skip.
        due_date: Filter by due date (exact match).
        tag: Filter by tag name.
        keyword: Keyword search in title/description (combines with filters,
            mirroring count_issues so listings and counts always agree).

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
        wheres.append("i.status = ?")
        params.append(Status.from_string(status).value)

    if priority:
        wheres.append("i.priority = ?")
        params.append(Priority.from_string(priority).value)

    if due_date:
        wheres.append("date(i.due_date) = date(?)")
        params.append(due_date)

    if keyword:
        wheres.append("(i.title LIKE ? ESCAPE '\\' OR i.description LIKE ? ESCAPE '\\')")
        escaped = f"%{_escape_like(keyword)}%"
        params.extend([escaped, escaped])

    if joins:
        query += " " + " ".join(joins)

    query += " WHERE " + " AND ".join(wheres)
    query += " ORDER BY i.created_at DESC"

    # LIMIT -1 means "no limit" in SQLite, which lets offset work on its own.
    if limit is not None or offset:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit if limit is not None else -1, offset])

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        issues = [self._row_to_issue(row) for row in rows]
        return _populate_tags(self, issues)


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

        issues = [self._row_to_issue(row) for row in rows]
        return _populate_tags(self, issues)


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
        WHERE (title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')
    """
    escaped = f"%{_escape_like(keyword)}%"
    params: list[Any] = [escaped, escaped]

    query += " ORDER BY created_at DESC"

    if limit is not None or offset:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit if limit is not None else -1, offset])

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        issues = [self._row_to_issue(row) for row in rows]
        return _populate_tags(self, issues)


def clear_all_issues(self: IssueRepository) -> int:
    """Clear all issues from the database.

    Returns:
        Number of issues deleted.
    """
    # Snapshot and delete in the same transaction so an issue created by a
    # concurrent process cannot be deleted without an audit entry.
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM issues ORDER BY created_at DESC")
        issues = [self._row_to_issue(row) for row in cursor.fetchall()]

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

        cursor.execute("DELETE FROM issues")
        return cursor.rowcount
