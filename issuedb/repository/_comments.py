"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from issuedb.models import (
    Comment,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def add_comment(self: IssueRepository, issue_id: int, text: str) -> Comment:
    """Add a comment to an issue.

    Args:
        issue_id: ID of the issue to comment on.
        text: Comment text.

    Returns:
        Created Comment object.

    Raises:
        ValueError: If issue not found or text is empty.
    """
    if not text or not text.strip():
        raise ValueError("Comment text cannot be empty")

    # Verify issue exists
    issue = self.get_issue(issue_id)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found")

    comment = Comment(
        issue_id=issue_id,
        text=text.strip(),
    )

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO comments (issue_id, text, created_at)
            VALUES (?, ?, ?)
        """,
            (
                comment.issue_id,
                comment.text,
                comment.created_at.isoformat(),
            ),
        )

        comment.id = cursor.lastrowid

    return comment


def get_comments(self: IssueRepository, issue_id: int) -> list[Comment]:
    """Get all comments for an issue.

    Args:
        issue_id: ID of the issue.

    Returns:
        List of Comment objects, ordered by creation time.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM comments
            WHERE issue_id = ?
            ORDER BY created_at ASC
        """,
            (issue_id,),
        )
        rows = cursor.fetchall()

        comments = []
        for row in rows:
            comment = Comment(
                id=row["id"],
                issue_id=row["issue_id"],
                text=row["text"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            comments.append(comment)

        return comments


def delete_comment(self: IssueRepository, comment_id: int) -> bool:
    """Delete a comment.

    Args:
        comment_id: ID of the comment to delete.

    Returns:
        True if comment was deleted, False if not found.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        return cursor.rowcount > 0
