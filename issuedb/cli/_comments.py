"""Comment-related CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def add_comment(self: CLI, issue_id: int, text: str, as_json: bool = False) -> str:
    """Add a comment to an issue.

    Args:
        issue_id: Issue ID.
        text: Comment text.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If issue not found or text is empty.
    """
    comment = self.repo.add_comment(issue_id, text)

    if as_json:
        return json.dumps(comment.to_dict(), indent=2)
    else:
        return f"Comment added to issue {issue_id}"


def list_comments(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """List all comments for an issue.

    Args:
        issue_id: Issue ID.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    comments = self.repo.get_comments(issue_id)

    if as_json:
        return json.dumps([c.to_dict() for c in comments], indent=2)
    else:
        if not comments:
            return f"No comments found for issue {issue_id}."

        lines = []
        for comment in comments:
            lines.append("-" * 50)
            lines.append(f"Comment ID: {comment.id}")
            lines.append(f"Created: {comment.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Text: {comment.text}")

        return "\n".join(lines)


def delete_comment(self: CLI, comment_id: int, as_json: bool = False) -> str:
    """Delete a comment.

    Args:
        comment_id: Comment ID.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If comment not found.
    """
    if not self.repo.delete_comment(comment_id):
        raise ValueError(f"Comment {comment_id} not found")

    result = {"message": f"Comment {comment_id} deleted successfully"}
    return self.format_output(result, as_json)
