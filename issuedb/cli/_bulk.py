"""Bulk JSON and pattern-based CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def bulk_create(self: CLI, json_input: str, as_json: bool = False) -> str:
    """Bulk create issues from JSON input.

    Args:
        json_input: JSON string or file path containing list of issue data.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If JSON is invalid or issues cannot be created.
    """
    # Parse JSON input
    try:
        issues_data = json.loads(json_input)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON input: {e}") from e

    if not isinstance(issues_data, list):
        raise ValueError("JSON input must be a list of issue objects")

    # Create issues
    created_issues = self.repo.bulk_create_issues(issues_data)

    result = {
        "message": f"Created {len(created_issues)} issue(s)",
        "count": len(created_issues),
        "issues": [issue.to_dict() for issue in created_issues],
    }
    return self.format_output(result, as_json)


def bulk_update_json(self: CLI, json_input: str, as_json: bool = False) -> str:
    """Bulk update issues from JSON input.

    Args:
        json_input: JSON string or file path containing list of update data.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If JSON is invalid or issues cannot be updated.
    """
    # Parse JSON input
    try:
        updates_data = json.loads(json_input)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON input: {e}") from e

    if not isinstance(updates_data, list):
        raise ValueError("JSON input must be a list of update objects with 'id' field")

    # Update issues
    updated_issues = self.repo.bulk_update_issues_from_json(updates_data)

    result = {
        "message": f"Updated {len(updated_issues)} issue(s)",
        "count": len(updated_issues),
        "issues": [issue.to_dict() for issue in updated_issues],
    }
    return self.format_output(result, as_json)


def bulk_close(self: CLI, json_input: str, as_json: bool = False) -> str:
    """Bulk close issues from JSON input containing issue IDs.

    Args:
        json_input: JSON string or file path containing list of issue IDs.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If JSON is invalid or issues cannot be closed.
    """
    # Parse JSON input
    try:
        issue_ids = json.loads(json_input)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON input: {e}") from e

    if not isinstance(issue_ids, list):
        raise ValueError("JSON input must be a list of issue IDs")

    # Validate all are integers
    if not all(isinstance(id, int) for id in issue_ids):
        raise ValueError("All issue IDs must be integers")

    # Close issues
    closed_issues = self.repo.bulk_close_issues(issue_ids)

    result = {
        "message": f"Closed {len(closed_issues)} issue(s)",
        "count": len(closed_issues),
        "issues": [issue.to_dict() for issue in closed_issues],
    }
    return self.format_output(result, as_json)


def bulk_close_pattern(
    self: CLI,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
) -> str:
    """Close issues matching a pattern.

    Args:
        title_pattern: Pattern to match against title.
        desc_pattern: Pattern to match against description.
        use_regex: If True, patterns are regex; if False, glob patterns.
        dry_run: If True, only show what would be done.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    closed = self.repo.bulk_close_by_pattern(
        title_pattern=title_pattern,
        desc_pattern=desc_pattern,
        use_regex=use_regex,
        dry_run=dry_run,
    )

    count = len(closed)
    if dry_run:  # noqa: SIM108
        message = f"Would close {count} issue(s) (dry-run)"
    else:
        message = f"Closed {count} issue(s)"

    if as_json:
        result = {
            "count": count,
            "message": message,
            "issues": [issue.to_dict() for issue in closed],
        }
        return json.dumps(result, indent=2)
    else:
        lines = [message]
        if closed:
            for issue in closed:
                lines.append(f"  - Issue #{issue.id}: {issue.title}")
        return "\n".join(lines)


def bulk_update_pattern(
    self: CLI,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    new_status: str | None = None,
    new_priority: str | None = None,
    dry_run: bool = False,
    as_json: bool = False,
) -> str:
    """Update issues matching a pattern.

    Args:
        title_pattern: Pattern to match against title.
        desc_pattern: Pattern to match against description.
        use_regex: If True, patterns are regex; if False, glob patterns.
        new_status: New status to set.
        new_priority: New priority to set.
        dry_run: If True, only show what would be done.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    updated = self.repo.bulk_update_by_pattern(
        title_pattern=title_pattern,
        desc_pattern=desc_pattern,
        use_regex=use_regex,
        new_status=new_status,
        new_priority=new_priority,
        dry_run=dry_run,
    )

    count = len(updated)
    if dry_run:  # noqa: SIM108
        message = f"Would update {count} issue(s) (dry-run)"
    else:
        message = f"Updated {count} issue(s)"

    if as_json:
        result = {
            "count": count,
            "message": message,
            "issues": [issue.to_dict() for issue in updated],
        }
        return json.dumps(result, indent=2)
    else:
        lines = [message]
        if updated:
            for issue in updated:
                lines.append(f"  - Issue #{issue.id}: {issue.title}")
        return "\n".join(lines)


def bulk_delete_pattern(
    self: CLI,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    confirm: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
) -> str:
    """Delete issues matching a pattern.

    Args:
        title_pattern: Pattern to match against title.
        desc_pattern: Pattern to match against description.
        use_regex: If True, patterns are regex; if False, glob patterns.
        confirm: Must be True to actually delete (unless dry_run is True).
        dry_run: If True, only show what would be done.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If confirm is False and dry_run is False.
    """
    if not confirm and not dry_run:
        raise ValueError("Must use --confirm flag to delete issues (or use --dry-run)")

    deleted = self.repo.bulk_delete_by_pattern(
        title_pattern=title_pattern,
        desc_pattern=desc_pattern,
        use_regex=use_regex,
        dry_run=dry_run,
    )

    count = len(deleted)
    if dry_run:  # noqa: SIM108
        message = f"Would delete {count} issue(s) (dry-run)"
    else:
        message = f"Deleted {count} issue(s)"

    if as_json:
        result = {
            "count": count,
            "message": message,
            "issues": [issue.to_dict() for issue in deleted],
        }
        return json.dumps(result, indent=2)
    else:
        lines = [message]
        if deleted:
            for issue in deleted:
                lines.append(f"  - Issue #{issue.id}: {issue.title}")
        return "\n".join(lines)
