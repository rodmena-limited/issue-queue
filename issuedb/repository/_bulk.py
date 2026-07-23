"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import fnmatch
import json
import re
from typing import TYPE_CHECKING, Any

from issuedb.models import Issue, Priority, Status

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
    # Parse and validate everything up front so a bad entry fails the whole
    # batch before any row is written.
    issues = []
    for issue_data in issues_data:
        if "title" not in issue_data or not issue_data["title"]:
            raise ValueError(f"Title is required for all issues: {issue_data}")
        issues.append(Issue.from_dict(issue_data))

    created_issues = []

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        for issue in issues:
            # Insert all fields Issue.from_dict accepts — due_date and
            # estimated_hours included, matching create_issue.
            cursor.execute(
                """
                INSERT INTO issues (title, description, priority, status,
                                   created_at, updated_at, estimated_hours, due_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    issue.title,
                    issue.description,
                    issue.priority.value,
                    issue.status.value,
                    issue.created_at.isoformat(),
                    issue.updated_at.isoformat(),
                    issue.estimated_hours,
                    issue.due_date.isoformat() if issue.due_date else None,
                ),
            )

            issue.id = cursor.lastrowid
            assert issue.id is not None  # Guaranteed by successful insert

            # Persist tags inline (same transaction) instead of dropping them.
            for tag in issue.tags:
                if not tag.name:
                    continue
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name, color, created_at) VALUES (?, ?, ?)",
                    (tag.name, tag.color, issue.created_at.isoformat()),
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO issue_tags (issue_id, tag_id, created_at)
                    SELECT ?, id, ? FROM tags WHERE name = ?
                """,
                    (issue.id, issue.created_at.isoformat(), tag.name),
                )

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
    # Validate the whole batch before applying anything, so a bad entry midway
    # through the list cannot leave earlier updates committed (partial apply).
    allowed_fields = {"title", "description", "priority", "status", "due_date"}
    parsed: list[tuple[int, dict[str, Any]]] = []
    for update_data in updates_data:
        if "id" not in update_data:
            raise ValueError(f"Issue ID is required for all updates: {update_data}")

        issue_id = update_data["id"]
        updates = {k: v for k, v in update_data.items() if k != "id"}

        if not updates:
            raise ValueError(f"No update fields provided for issue {issue_id}")

        for field_name, value in updates.items():
            if field_name not in allowed_fields:
                raise ValueError(f"Cannot update field: {field_name}")
            if field_name == "priority":
                Priority.from_string(value)
            elif field_name == "status":
                Status.from_string(value)

        parsed.append((issue_id, updates))

    # Verify all target issues exist up front.
    ids = [issue_id for issue_id, _ in parsed]
    if ids:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(ids))
            cursor.execute(f"SELECT id FROM issues WHERE id IN ({placeholders})", ids)
            existing = {row["id"] for row in cursor.fetchall()}
        missing = [issue_id for issue_id in ids if issue_id not in existing]
        if missing:
            raise ValueError(f"Issue {missing[0]} not found")

    updated_issues = []
    for issue_id, updates in parsed:
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
    # Verify all issues exist before closing any, so a bad ID midway through
    # the list cannot leave the batch half-applied.
    if issue_ids:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(issue_ids))
            cursor.execute(f"SELECT id FROM issues WHERE id IN ({placeholders})", issue_ids)
            existing = {row["id"] for row in cursor.fetchall()}
        missing = [issue_id for issue_id in issue_ids if issue_id not in existing]
        if missing:
            raise ValueError(f"Issue {missing[0]} not found")

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

        # Match title if pattern provided. For regex, never lowercase the
        # pattern itself — that inverts escape classes like \D or \S —
        # re.IGNORECASE alone handles case-insensitivity.
        if title_pattern:
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                title_match = bool(re.search(title_pattern, issue.title, flags=flags))
            else:
                title_text = issue.title if case_sensitive else issue.title.lower()
                pattern = title_pattern if case_sensitive else title_pattern.lower()
                title_match = fnmatch.fnmatch(title_text, pattern)

        # Match description if pattern provided
        if desc_pattern and issue.description:
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                desc_match = bool(re.search(desc_pattern, issue.description, flags=flags))
            else:
                desc_text = issue.description if case_sensitive else issue.description.lower()
                pattern = desc_pattern if case_sensitive else desc_pattern.lower()
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
