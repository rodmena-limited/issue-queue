"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import (
    LessonLearned,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def add_lesson(
    self: IssueRepository, lesson: str, issue_id: int | None = None, category: str = "general"
) -> LessonLearned:
    """Add a lesson learned.

    Args:
        lesson: The lesson text.
        issue_id: Related issue ID (optional).
        category: Category (default: general).

    Returns:
        Created LessonLearned object.
    """
    # Verify issue if provided
    if issue_id:
        issue = self.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

    ll = LessonLearned(issue_id=issue_id, lesson=lesson, category=category)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO lessons_learned (issue_id, lesson, category, created_at)
            VALUES (?, ?, ?, ?)
        """,
            (
                ll.issue_id,
                ll.lesson,
                ll.category,
                ll.created_at.isoformat(),
            ),
        )
        ll.id = cursor.lastrowid

        # Log audit
        self._log_audit(
            conn,
            issue_id if issue_id else 0,
            "LESSON_ADD",
            None,
            None,
            json.dumps(ll.to_dict()),
        )

    return ll


def update_lesson(
    self: IssueRepository, lesson_id: int, lesson: str | None = None, category: str | None = None
) -> LessonLearned | None:
    """Update a lesson learned.

    Args:
        lesson_id: ID of the lesson.
        lesson: New lesson text.
        category: New category.

    Returns:
        Updated LessonLearned object or None.
    """
    current_lesson = self.get_lesson(lesson_id)
    if not current_lesson:
        return None

    updates = []
    values: list[Any] = []
    audit_entries = []

    if lesson is not None and lesson != current_lesson.lesson:
        updates.append("lesson = ?")
        values.append(lesson)
        audit_entries.append(("lesson", current_lesson.lesson, lesson))

    if category is not None and category != current_lesson.category:
        updates.append("category = ?")
        values.append(category)
        audit_entries.append(("category", current_lesson.category, category))

    if not updates:
        return current_lesson

    values.append(lesson_id)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        query = f"UPDATE lessons_learned SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)

        # Log audit
        for field, old_val, new_val in audit_entries:
            self._log_audit(
                conn,
                current_lesson.issue_id if current_lesson.issue_id else 0,
                "LESSON_UPDATE",
                f"lesson:{lesson_id}:{field}",
                old_val,
                new_val,
            )

    return self.get_lesson(lesson_id)


def delete_lesson(self: IssueRepository, lesson_id: int) -> bool:
    """Delete a lesson learned.

    Args:
        lesson_id: ID of the lesson.

    Returns:
        True if deleted.
    """
    current_lesson = self.get_lesson(lesson_id)
    if not current_lesson:
        return False

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lessons_learned WHERE id = ?", (lesson_id,))

        # Log audit
        self._log_audit(
            conn,
            current_lesson.issue_id if current_lesson.issue_id else 0,
            "LESSON_DELETE",
            None,
            json.dumps(current_lesson.to_dict()),
            None,
        )

        return cursor.rowcount > 0


def get_lesson(self: IssueRepository, lesson_id: int) -> LessonLearned | None:
    """Get a lesson learned by ID.

    Args:
        lesson_id: ID of the lesson.

    Returns:
        LessonLearned object or None.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lessons_learned WHERE id = ?", (lesson_id,))
        row = cursor.fetchone()

        if row:
            return LessonLearned(
                id=row["id"],
                issue_id=row["issue_id"],
                lesson=row["lesson"],
                category=row["category"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None


def list_lessons(
    self: IssueRepository, issue_id: int | None = None, category: str | None = None
) -> list[LessonLearned]:
    """List lessons learned.

    Args:
        issue_id: Filter by issue ID.
        category: Filter by category.

    Returns:
        List of LessonLearned objects.
    """
    query = "SELECT * FROM lessons_learned WHERE 1=1"
    params: list[Any] = []

    if issue_id:
        query += " AND issue_id = ?"
        params.append(issue_id)

    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC"

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            LessonLearned(
                id=row["id"],
                issue_id=row["issue_id"],
                lesson=row["lesson"],
                category=row["category"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

# Tag methods
