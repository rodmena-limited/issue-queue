"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import contextlib
import json
from datetime import datetime
from typing import TYPE_CHECKING

from issuedb.models import (
    Tag,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def create_tag(self: IssueRepository, name: str, color: str | None = None) -> Tag:
    """Create a new tag.

    Args:
        name: Tag name.
        color: Hex color (optional).

    Returns:
        Created Tag object.
    """
    tag = Tag(name=name, color=color)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tags (name, color, created_at) VALUES (?, ?, ?)",
                (tag.name, tag.color, tag.created_at.isoformat()),
            )
            tag.id = cursor.lastrowid

            # Log audit (global)
            self._log_audit(
                conn,
                0,
                "TAG_CREATE",
                None,
                None,
                json.dumps(tag.to_dict()),
            )
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Tag '{name}' already exists") from e
            raise

    return tag


def list_tags(self: IssueRepository) -> list[Tag]:
    """List all tags.

    Returns:
        List of Tag objects.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tags ORDER BY name ASC")
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


def add_issue_tag(self: IssueRepository, issue_id: int, tag_name: str) -> bool:
    """Add a tag to an issue. Creates the tag if it doesn't exist.

    Args:
        issue_id: Issue ID.
        tag_name: Tag name.

    Returns:
        True if tag was added, False if already present.
    """
    # Verify the issue exists BEFORE creating the tag, so a bad issue ID
    # cannot leave an orphan tag behind or surface a raw FK error.
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM issues WHERE id = ?", (issue_id,))
        if not cursor.fetchone():
            raise ValueError(f"Issue {issue_id} not found")

    # Ensure tag exists
    with contextlib.suppress(ValueError):
        self.create_tag(tag_name)

    # Get tag ID
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_row = cursor.fetchone()
        if not tag_row:
            raise ValueError(f"Tag {tag_name} not found")
        tag_id = tag_row["id"]

        try:
            cursor.execute(
                "INSERT INTO issue_tags (issue_id, tag_id, created_at) VALUES (?, ?, ?)",
                (issue_id, tag_id, datetime.now().isoformat()),
            )

            # Log audit
            self._log_audit(
                conn,
                issue_id,
                "TAG_ADD",
                "tag",
                None,
                tag_name,
            )
            return True
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return False
            if "FOREIGN KEY constraint failed" in str(e):
                raise ValueError(f"Issue {issue_id} not found") from e
            raise


def remove_issue_tag(self: IssueRepository, issue_id: int, tag_name: str) -> bool:
    """Remove a tag from an issue.

    Args:
        issue_id: Issue ID.
        tag_name: Tag name.

    Returns:
        True if removed.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM issue_tags
            WHERE issue_id = ? AND tag_id IN (SELECT id FROM tags WHERE name = ?)
        """,
            (issue_id, tag_name),
        )

        if cursor.rowcount > 0:
            # Log audit
            self._log_audit(
                conn,
                issue_id,
                "TAG_REMOVE",
                "tag",
                tag_name,
                None,
            )
            return True
        return False


def get_issue_tags(self: IssueRepository, issue_id: int) -> list[Tag]:
    """Get tags for an issue.

    Args:
        issue_id: Issue ID.

    Returns:
        List of Tag objects.
    """
    with self.db.get_connection() as conn:
        return self._get_issue_tags_with_conn(conn, issue_id)


def get_tags_for_issues(self: IssueRepository, issue_ids: list[int]) -> dict[int, list[Tag]]:
    """Get tags for multiple issues in a single query.

    Args:
        issue_ids: List of issue IDs.

    Returns:
        Dictionary mapping issue_id to list of Tag objects.
    """
    if not issue_ids:
        return {}

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(issue_ids))
        cursor.execute(
            f"""
            SELECT it.issue_id, t.id, t.name, t.color, t.created_at
            FROM tags t
            JOIN issue_tags it ON t.id = it.tag_id
            WHERE it.issue_id IN ({placeholders})
            ORDER BY it.issue_id, t.name ASC
            """,
            issue_ids,
        )
        rows = cursor.fetchall()

        result: dict[int, list[Tag]] = {issue_id: [] for issue_id in issue_ids}
        for row in rows:
            tag = Tag(
                id=row["id"],
                name=row["name"],
                color=row["color"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            result[row["issue_id"]].append(tag)

        return result

# Issue Relation methods
