"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from issuedb.models import (
    Issue,
    Status,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def add_dependency(self: IssueRepository, blocked_id: int, blocker_id: int) -> bool:
    """Add a dependency relationship between issues.

    Args:
        blocked_id: ID of the issue being blocked.
        blocker_id: ID of the issue that blocks.

    Returns:
        True if dependency was added, False if it already exists.

    Raises:
        ValueError: If either issue doesn't exist or if adding would create a cycle.
    """
    # Do existence checks, the cycle check and the insert in a single
    # transaction so the operation is atomic. The cycle check runs AFTER the
    # INSERT (which takes the write lock), so two concurrent reciprocal inserts
    # cannot both pass it — the second one sees the first's row and rolls back.
    with self.db.get_connection() as conn:
        if not self._get_issue_with_conn(conn, blocked_id):
            raise ValueError(f"Blocked issue {blocked_id} not found")
        if not self._get_issue_with_conn(conn, blocker_id):
            raise ValueError(f"Blocker issue {blocker_id} not found")

        # Prevent self-blocking
        if blocked_id == blocker_id:
            raise ValueError("Issue cannot block itself")

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO issue_dependencies (blocker_id, blocked_id)
                VALUES (?, ?)
            """,
                (blocker_id, blocked_id),
            )
        except Exception as e:
            # Check if it's a unique constraint violation
            if "UNIQUE constraint failed" in str(e):
                return False
            raise

        # Check for cycles (would blocker_id be blocked by blocked_id?). Raising
        # here makes the surrounding context manager roll the INSERT back.
        if self._would_create_cycle_with_conn(conn, blocked_id, blocker_id):
            raise ValueError(
                f"Adding this dependency would create a cycle: "
                f"issue {blocker_id} is already transitively blocked by issue {blocked_id}"
            )

        return True


def remove_dependency(self: IssueRepository, blocked_id: int, blocker_id: int | None = None) -> int:
    """Remove dependency relationship(s) for an issue.

    Args:
        blocked_id: ID of the blocked issue.
        blocker_id: ID of the blocker issue. If None, removes all blockers.

    Returns:
        Number of dependencies removed.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        if blocker_id is not None:
            cursor.execute(
                """
                DELETE FROM issue_dependencies
                WHERE blocked_id = ? AND blocker_id = ?
            """,
                (blocked_id, blocker_id),
            )
        else:
            cursor.execute(
                """
                DELETE FROM issue_dependencies
                WHERE blocked_id = ?
            """,
                (blocked_id,),
            )

        return cursor.rowcount


def get_blockers(self: IssueRepository, issue_id: int) -> list[Issue]:
    """Get all issues blocking this issue.

    Args:
        issue_id: ID of the issue.

    Returns:
        List of Issue objects that are blocking this issue.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT i.* FROM issues i
            INNER JOIN issue_dependencies d ON i.id = d.blocker_id
            WHERE d.blocked_id = ?
            ORDER BY
                CASE i.priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                i.created_at ASC
        """,
            (issue_id,),
        )
        rows = cursor.fetchall()
        return [self._row_to_issue(row) for row in rows]


def get_blocking(self: IssueRepository, issue_id: int) -> list[Issue]:
    """Get all issues that this issue is blocking.

    Args:
        issue_id: ID of the issue.

    Returns:
        List of Issue objects that are blocked by this issue.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT i.* FROM issues i
            INNER JOIN issue_dependencies d ON i.id = d.blocked_id
            WHERE d.blocker_id = ?
            ORDER BY
                CASE i.priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                i.created_at ASC
        """,
            (issue_id,),
        )
        rows = cursor.fetchall()
        return [self._row_to_issue(row) for row in rows]


def is_blocked(self: IssueRepository, issue_id: int) -> bool:
    """Check if an issue has unresolved blockers.

    Args:
        issue_id: ID of the issue.

    Returns:
        True if the issue has at least one open/in-progress blocker.
    """
    blockers = self.get_blockers(issue_id)
    # Issue is blocked if it has any unresolved blocker; closed and wont-do
    # blockers are both resolved.
    return any(
        blocker.status not in (Status.CLOSED, Status.WONT_DO) for blocker in blockers
    )


def get_all_blocked_issues(self: IssueRepository, status: str | None = None) -> list[Issue]:
    """Get all issues that are currently blocked.

    Args:
        status: Optional filter by status.

    Returns:
        List of Issue objects that have unresolved blockers.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        # Get all issues with dependencies
        query = """
            SELECT DISTINCT i.* FROM issues i
            INNER JOIN issue_dependencies d ON i.id = d.blocked_id
            INNER JOIN issues blocker ON blocker.id = d.blocker_id
            WHERE blocker.status NOT IN ('closed', 'wont-do')
        """
        params: list[Any] = []

        if status:
            query += " AND i.status = ?"
            params.append(Status.from_string(status).value)

        query += """
            ORDER BY
                CASE i.priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                i.created_at ASC
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_issue(row) for row in rows]


def _would_create_cycle(self: IssueRepository, blocked_id: int, blocker_id: int) -> bool:
    """Check if adding a dependency would create a cycle.

    A cycle would be created if blocker_id is already (transitively)
    blocked by blocked_id.

    Args:
        blocked_id: ID of the issue to be blocked.
        blocker_id: ID of the potential blocker.

    Returns:
        True if adding this dependency would create a cycle.
    """
    with self.db.get_connection() as conn:
        return self._would_create_cycle_with_conn(conn, blocked_id, blocker_id)


def _would_create_cycle_with_conn(
    self: IssueRepository, conn: Any, blocked_id: int, blocker_id: int
) -> bool:
    """Connection-scoped cycle check (see :meth:`_would_create_cycle`).

    Walks the blocker chain using the supplied connection so it can run inside
    an open transaction without spawning nested connections.
    """
    cursor = conn.cursor()
    visited: set[int] = set()
    to_check = [blocker_id]

    while to_check:
        current = to_check.pop()
        if current in visited:
            continue
        visited.add(current)

        # If we find blocked_id in the blocker chain, we have a cycle
        if current == blocked_id:
            return True

        # Add all blockers of the current issue to check
        cursor.execute(
            "SELECT blocker_id FROM issue_dependencies WHERE blocked_id = ?",
            (current,),
        )
        for row in cursor.fetchall():
            bid = row["blocker_id"]
            if bid is not None and bid not in visited:
                to_check.append(bid)

    return False
