"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import fnmatch
import json
import re
from typing import TYPE_CHECKING, Any

from issuedb.models import Issue

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def bulk_create_issues(self: IssueRepository, issues_data: list[dict[str, Any]]) -> list[Issue]:
    """Bulk create multiple issues from JSON data.

    Args:
        issues_data: List of dictionaries containing issue data.

    Returns:
        List of created Issue objects.

    Raises:
        ValueError: If any issue data is invalid.
    """
    created_issues = []

    with self.db.get_connection() as conn:
        for issue_data in issues_data:
            # Validate required fields
            if "title" not in issue_data or not issue_data["title"]:
                raise ValueError(f"Title is required for all issues: {issue_data}")

            # Create Issue object from dict
            issue = Issue.from_dict(issue_data)

            # Insert into database
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO issues (title, description, priority, status,
                                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    issue.title,
                    issue.description,
                    issue.priority.value,
                    issue.status.value,
                    issue.created_at.isoformat(),
                    issue.updated_at.isoformat(),
                ),
            )

            issue.id = cursor.lastrowid
            assert issue.id is not None  # Guaranteed by successful insert

            # Log creation in audit log
            self._log_audit(
                conn,
                issue.id,
                "BULK_CREATE",
                None,
                None,
                json.dumps(issue.to_dict()),
            )

            created_issues.append(issue)

    return created_issues


def bulk_update_issues_from_json(
    self: IssueRepository, updates_data: list[dict[str, Any]]
) -> list[Issue]:
    """Bulk update multiple specific issues from JSON data.

    Args:
        updates_data: List of dictionaries with 'id' and fields to update.

    Returns:
        List of updated Issue objects.

    Raises:
        ValueError: If any update data is invalid or issue not found.
    """
    updated_issues = []

    for update_data in updates_data:
        # Validate required id field
        if "id" not in update_data:
            raise ValueError(f"Issue ID is required for all updates: {update_data}")

        issue_id = update_data["id"]

        # Extract update fields (exclude id)
        updates = {k: v for k, v in update_data.items() if k != "id"}

        if not updates:
            raise ValueError(f"No update fields provided for issue {issue_id}")

        # Update the issue
        updated_issue = self.update_issue(issue_id, **updates)

        if not updated_issue:
            raise ValueError(f"Issue {issue_id} not found")

        updated_issues.append(updated_issue)

    return updated_issues


def bulk_close_issues(self: IssueRepository, issue_ids: list[int]) -> list[Issue]:
    """Bulk close multiple issues by their IDs.

    Args:
        issue_ids: List of issue IDs to close.

    Returns:
        List of closed Issue objects.

    Raises:
        ValueError: If any issue not found.
    """
    closed_issues = []

    for issue_id in issue_ids:
        # Update status to closed
        updated_issue = self.update_issue(issue_id, status="closed")

        if not updated_issue:
            raise ValueError(f"Issue {issue_id} not found")

        closed_issues.append(updated_issue)

    return closed_issues


def find_by_pattern(
    self: IssueRepository,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    case_sensitive: bool = False,
) -> list[Issue]:
    """Find issues matching title and/or description patterns.

    Args:
        title_pattern: Pattern to match against title (glob or regex).
        desc_pattern: Pattern to match against description (glob or regex).
        use_regex: If True, patterns are regex; if False, glob patterns.
        case_sensitive: If True, matching is case-sensitive.

    Returns:
        List of matching issues.
    """
    all_issues = self.get_all_issues()
    matching_issues = []

    for issue in all_issues:
        title_match = True
        desc_match = True

        # Match title if pattern provided
        if title_pattern:
            title_text = issue.title if case_sensitive else issue.title.lower()
            pattern = title_pattern if case_sensitive else title_pattern.lower()

            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                title_match = bool(re.search(pattern, issue.title, flags=flags))
            else:
                title_match = fnmatch.fnmatch(title_text, pattern)

        # Match description if pattern provided
        if desc_pattern and issue.description:
            desc_text = issue.description if case_sensitive else issue.description.lower()
            pattern = desc_pattern if case_sensitive else desc_pattern.lower()

            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                desc_match = bool(re.search(pattern, issue.description, flags=flags))
            else:
                desc_match = fnmatch.fnmatch(desc_text, pattern)
        elif desc_pattern and not issue.description:
            desc_match = False

        # Include issue if both patterns match (or pattern not provided)
        if title_match and desc_match:
            matching_issues.append(issue)

    return matching_issues


def bulk_close_by_pattern(
    self: IssueRepository,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    case_sensitive: bool = False,
    dry_run: bool = False,
) -> list[Issue]:
    """Close issues matching the pattern.

    Args:
        title_pattern: Pattern to match against title.
        desc_pattern: Pattern to match against description.
        use_regex: If True, patterns are regex; if False, glob patterns.
        case_sensitive: If True, matching is case-sensitive.
        dry_run: If True, return matches without making changes.

    Returns:
        List of issues that were (or would be) closed.
    """
    matching_issues = self.find_by_pattern(
        title_pattern=title_pattern,
        desc_pattern=desc_pattern,
        use_regex=use_regex,
        case_sensitive=case_sensitive,
    )

    if dry_run:
        return matching_issues

    # Close all matching issues
    closed_issues = []
    for issue in matching_issues:
        assert issue.id is not None  # Issues from DB always have ID
        updated_issue = self.update_issue(issue.id, status="closed")
        if updated_issue:
            closed_issues.append(updated_issue)

    return closed_issues


def bulk_update_by_pattern(
    self: IssueRepository,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    case_sensitive: bool = False,
    new_status: str | None = None,
    new_priority: str | None = None,
    dry_run: bool = False,
) -> list[Issue]:
    """Update issues matching the pattern.

    Args:
        title_pattern: Pattern to match against title.
        desc_pattern: Pattern to match against description.
        use_regex: If True, patterns are regex; if False, glob patterns.
        case_sensitive: If True, matching is case-sensitive.
        new_status: New status to set.
        new_priority: New priority to set.
        dry_run: If True, return matches without making changes.

    Returns:
        List of issues that were (or would be) updated.
    """
    matching_issues = self.find_by_pattern(
        title_pattern=title_pattern,
        desc_pattern=desc_pattern,
        use_regex=use_regex,
        case_sensitive=case_sensitive,
    )

    if dry_run:
        return matching_issues

    # Update all matching issues
    updated_issues = []
    updates = {}
    if new_status:
        updates["status"] = new_status
    if new_priority:
        updates["priority"] = new_priority

    if not updates:
        return []  # No updates to apply

    for issue in matching_issues:
        assert issue.id is not None  # Issues from DB always have ID
        updated_issue = self.update_issue(issue.id, **updates)
        if updated_issue:
            updated_issues.append(updated_issue)

    return updated_issues


def bulk_delete_by_pattern(
    self: IssueRepository,
    title_pattern: str | None = None,
    desc_pattern: str | None = None,
    use_regex: bool = False,
    case_sensitive: bool = False,
    dry_run: bool = False,
) -> list[Issue]:
    """Delete issues matching the pattern.

    Args:
        title_pattern: Pattern to match against title.
        desc_pattern: Pattern to match against description.
        use_regex: If True, patterns are regex; if False, glob patterns.
        case_sensitive: If True, matching is case-sensitive.
        dry_run: If True, return matches without making changes.

    Returns:
        List of issues that were (or would be) deleted.
    """
    matching_issues = self.find_by_pattern(
        title_pattern=title_pattern,
        desc_pattern=desc_pattern,
        use_regex=use_regex,
        case_sensitive=case_sensitive,
    )

    if dry_run:
        return matching_issues

    # Delete all matching issues
    deleted_issues = []
    for issue in matching_issues:
        assert issue.id is not None  # Issues from DB always have ID
        # Store issue before deletion
        deleted_issues.append(issue)
        self.delete_issue(issue.id)

    return deleted_issues
