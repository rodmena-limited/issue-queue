"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.date_utils import parse_date, validate_date_range
from issuedb.models import (
    Issue,
    Priority,
    Status,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def search_issues_advanced(
    self: IssueRepository,
    keyword: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    priorities: list[str] | None = None,
    statuses: list[str] | None = None,
    sort_by: str = "created",
    order: str = "desc",
    limit: int | None = None,
) -> list[Issue]:
    """Advanced search for issues with multiple filters and sorting.

    Args:
        keyword: Search keyword for title and description.
        created_after: Issues created after this date (supports relative dates).
        created_before: Issues created before this date (supports relative dates).
        updated_after: Issues updated after this date (supports relative dates).
        updated_before: Issues updated before this date (supports relative dates).
        priorities: List of priority values to filter by.
        statuses: List of status values to filter by.
        sort_by: Field to sort by ('created', 'updated', 'priority').
        order: Sort order ('asc' or 'desc').
        limit: Maximum number of results.

    Returns:
        List of matching issues.

    Raises:
        ValueError: If invalid parameters are provided.
    """
    # Parse date strings
    created_after_dt = parse_date(created_after) if created_after else None
    created_before_dt = parse_date(created_before) if created_before else None
    updated_after_dt = parse_date(updated_after) if updated_after else None
    updated_before_dt = parse_date(updated_before) if updated_before else None

    # Validate date ranges
    validate_date_range(created_after_dt, created_before_dt)
    validate_date_range(updated_after_dt, updated_before_dt)

    # Validate priorities and statuses
    if priorities:
        for p in priorities:
            Priority.from_string(p)  # Will raise ValueError if invalid

    if statuses:
        for s in statuses:
            Status.from_string(s)  # Will raise ValueError if invalid

    # Validate sort parameters
    if sort_by not in ["created", "updated", "priority"]:
        raise ValueError(
            f"Invalid sort_by: {sort_by}. Must be 'created', 'updated', or 'priority'"
        )

    if order not in ["asc", "desc"]:
        raise ValueError(f"Invalid order: {order}. Must be 'asc' or 'desc'")

    # Build query
    query = "SELECT * FROM issues WHERE 1=1"
    params: list[Any] = []

    # Keyword search
    if keyword:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    # Date filters
    if created_after_dt:
        query += " AND created_at >= ?"
        params.append(created_after_dt.isoformat())

    if created_before_dt:
        query += " AND created_at <= ?"
        params.append(created_before_dt.isoformat())

    if updated_after_dt:
        query += " AND updated_at >= ?"
        params.append(updated_after_dt.isoformat())

    if updated_before_dt:
        query += " AND updated_at <= ?"
        params.append(updated_before_dt.isoformat())

    # Priority filter
    if priorities:
        placeholders = ",".join(["?"] * len(priorities))
        query += f" AND priority IN ({placeholders})"
        params.extend([p.lower() for p in priorities])

    # Status filter
    if statuses:
        placeholders = ",".join(["?"] * len(statuses))
        query += f" AND status IN ({placeholders})"
        params.extend([s.lower() for s in statuses])

    # Sorting
    if sort_by == "created":
        query += f" ORDER BY created_at {order.upper()}"
    elif sort_by == "updated":
        query += f" ORDER BY updated_at {order.upper()}"
    elif sort_by == "priority":
        # Custom priority ordering
        if order == "desc":
            query += """
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END ASC
            """
        else:
            query += """
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END DESC
            """

    # Limit
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    # Execute query
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_issue(row) for row in rows]


def save_search(self: IssueRepository, name: str, search_params: dict[str, Any]) -> int:
    """Save a search query for later reuse.

    Args:
        name: Unique name for the saved search.
        search_params: Dictionary of search parameters.

    Returns:
        ID of the saved search.

    Raises:
        ValueError: If name already exists or is invalid.
    """
    if not name or not name.strip():
        raise ValueError("Search name cannot be empty")

    # Convert params to JSON
    query_json = json.dumps(search_params)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO saved_searches (name, query_json)
                VALUES (?, ?)
            """,
                (name.strip(), query_json),
            )
            # lastrowid should never be None after successful INSERT
            return cursor.lastrowid or 0
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"A saved search with name '{name}' already exists") from e
            raise


def get_saved_search(self: IssueRepository, name: str) -> dict[str, Any] | None:
    """Get a saved search by name.

    Args:
        name: Name of the saved search.

    Returns:
        Dictionary with saved search details, or None if not found.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM saved_searches WHERE name = ?
        """,
            (name,),
        )
        row = cursor.fetchone()

        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "query_params": json.loads(row["query_json"]),
                "created_at": datetime.fromisoformat(row["created_at"]),
            }
        return None


def list_saved_searches(self: IssueRepository) -> list[dict[str, Any]]:
    """List all saved searches.

    Returns:
        List of saved search dictionaries.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM saved_searches ORDER BY name ASC
        """
        )
        rows = cursor.fetchall()

        searches = []
        for row in rows:
            searches.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "query_params": json.loads(row["query_json"]),
                    "created_at": datetime.fromisoformat(row["created_at"]),
                }
            )

        return searches


def delete_saved_search(self: IssueRepository, name: str) -> bool:
    """Delete a saved search.

    Args:
        name: Name of the saved search to delete.

    Returns:
        True if deleted, False if not found.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_searches WHERE name = ?", (name,))
        return cursor.rowcount > 0


def run_saved_search(self: IssueRepository, name: str) -> list[Issue]:
    """Execute a saved search.

    Args:
        name: Name of the saved search.

    Returns:
        List of matching issues.

    Raises:
        ValueError: If saved search not found.
    """
    saved_search = self.get_saved_search(name)
    if not saved_search:
        raise ValueError(f"Saved search '{name}' not found")

    # Execute the search with saved parameters
    return self.search_issues_advanced(**saved_search["query_params"])

# Workspace methods
