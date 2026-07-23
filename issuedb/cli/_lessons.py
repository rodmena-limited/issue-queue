"""Lessons-learned CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def lesson_add(
    self: CLI,
    lesson: str,
    issue_id: int | None = None,
    category: str = "general",
    as_json: bool = False,
) -> str:
    """Add lesson learned.

    Raises:
        ValueError: If the referenced issue does not exist.
    """
    ll = self.repo.add_lesson(lesson, issue_id, category)
    if as_json:
        return json.dumps(ll.to_dict(), indent=2)
    return f"Lesson added: {ll.id}"


def lesson_list(
    self: CLI, issue_id: int | None = None, category: str | None = None, as_json: bool = False
) -> str:
    """List lessons."""
    lessons = self.repo.list_lessons(issue_id, category)
    if as_json:
        return json.dumps([lesson.to_dict() for lesson in lessons], indent=2)

    if not lessons:
        return "No lessons found."

    lines = []
    for lesson in lessons:
        prefix = f"[Issue #{lesson.issue_id}] " if lesson.issue_id else ""
        lines.append(f"{prefix}[{lesson.category}] {lesson.lesson}")
    return "\n".join(lines)
