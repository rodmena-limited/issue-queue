"""Core issue CRUD CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from issuedb.models import Issue, Priority, Status

if TYPE_CHECKING:
    from issuedb.cli import CLI


def create_issue(
    self: CLI,
    title: str,
    description: str | None = None,
    priority: str = "medium",
    status: str = "open",
    due_date: str | None = None,
    as_json: bool = False,
    force: bool = False,
    check_duplicates: bool = False,
    tags: list[str] | None = None,
    template: str | None = None,
) -> str:
    """Create a new issue.

    Args:
        title: Issue title.
        description: Optional description.
        priority: Priority level.
        status: Initial status.
        due_date: Optional due date (YYYY-MM-DD).
        as_json: Output as JSON.
        force: Create issue even if similar issues found (with check_duplicates).
        check_duplicates: Enable duplicate checking (opt-in, disabled by default).
        tags: Optional list of tag names to attach to the new issue.
        template: Optional template name; applies its title prefix, default
            priority/status (unless explicitly overridden) and required-field
            validation.

    Returns:
        Formatted output.
    """
    from datetime import datetime

    from issuedb.similarity import find_similar_issues

    if template:
        tmpl = self.repo.get_template(template)
        if not tmpl:
            available = ", ".join(t.name for t in self.repo.list_templates()) or "(none)"
            raise ValueError(f"Template '{template}' not found. Available: {available}")
        errors = self.repo.validate_against_template(
            tmpl, {"title": title, "description": description}
        )
        if errors:
            raise ValueError(f"Template '{template}': " + "; ".join(errors))
        if tmpl.title_prefix and not title.startswith(tmpl.title_prefix):
            title = f"{tmpl.title_prefix} {title}"
        # Template defaults fill in when the caller left the parser defaults.
        if tmpl.default_priority and priority == "medium":
            priority = tmpl.default_priority
        if tmpl.default_status and status == "open":
            status = tmpl.default_status

    due_date_obj = None
    if due_date:
        try:
            due_date_obj = datetime.fromisoformat(due_date)
        except ValueError:
            # Propagate so the CLI error handler reports it on stderr with
            # exit code 1 — returning the error as output would look like a
            # successful create to scripts and agents.
            raise ValueError("Invalid date format (use YYYY-MM-DD)") from None

    issue = Issue(
        title=title,
        description=description,
        priority=Priority.from_string(priority),
        status=Status.from_string(status),
        due_date=due_date_obj,
    )

    # Check for duplicates only if explicitly enabled
    if check_duplicates:
        # Combine title and description for similarity check
        query_text = title
        if description:
            query_text = f"{title} {description}"

        # Get all existing issues
        all_issues = self.repo.get_all_issues()

        # Find similar issues
        similar_issues = find_similar_issues(query_text, all_issues, threshold=0.7)

        # If similar issues found and not forced, refuse with an error so the
        # caller's exit code reflects that nothing was created.
        if similar_issues and not force:
            details = "; ".join(
                f"#{similar_issue.id} {similar_issue.title!r}"
                f" ({round(similarity * 100, 1)}% similar)"
                for similar_issue, similarity in similar_issues[:3]
            )
            raise ValueError(
                f"Similar issues found: {details}. Use --force to create anyway"
            )

    created_issue = self.repo.create_issue(issue)

    # Attach any tags, then re-fetch so they appear in the output.
    if tags and created_issue.id is not None:
        for tag in tags:
            tag_name = tag.strip()
            if tag_name:
                self.repo.add_issue_tag(created_issue.id, tag_name)
        refreshed = self.repo.get_issue(created_issue.id)
        if refreshed is not None:
            created_issue = refreshed

    return self.format_output(created_issue, as_json)


def list_templates(self: CLI, as_json: bool = False) -> str:
    """List available issue templates.

    Args:
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    templates = self.repo.list_templates()
    if as_json:
        return json.dumps([t.to_dict() for t in templates], indent=2)
    if not templates:
        return "No templates found."
    lines = []
    for t in templates:
        details = []
        if t.title_prefix:
            details.append(f"prefix: {t.title_prefix}")
        if t.default_priority:
            details.append(f"priority: {t.default_priority}")
        if t.default_status:
            details.append(f"status: {t.default_status}")
        if t.required_fields:
            details.append(f"requires: {', '.join(t.required_fields)}")
        lines.append(t.name + (f" ({'; '.join(details)})" if details else ""))
    return "\n".join(lines)


def list_issues(
    self: CLI,
    status: str | None = None,
    priority: str | None = None,
    limit: int | None = None,
    due_date: str | None = None,
    tag: str | None = None,
    as_json: bool = False,
) -> str:
    """List issues with filters.

    Args:
        status: Filter by status.
        priority: Filter by priority.
        limit: Maximum number of issues.
        due_date: Filter by due date.
        tag: Filter by tag.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    issues = self.repo.list_issues(
        status=status, priority=priority, limit=limit, due_date=due_date, tag=tag
    )
    return self.format_output(issues, as_json)


def get_issue(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """Get a specific issue.

    Args:
        issue_id: Issue ID.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If issue not found.
    """
    issue = self.repo.get_issue(issue_id)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found")
    return self.format_output(issue, as_json)


def update_issue(self: CLI, issue_id: int, as_json: bool = False, **updates: Any) -> str:
    """Update an issue.

    Args:
        issue_id: Issue ID.
        as_json: Output as JSON.
        **updates: Fields to update (including due_date).

    Returns:
        Formatted output.

    Raises:
        ValueError: If issue not found.
    """
    issue = self.repo.update_issue(issue_id, **updates)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found")
    return self.format_output(issue, as_json)


def bulk_update_issues(
    self: CLI,
    new_status: str | None = None,
    new_priority: str | None = None,
    filter_status: str | None = None,
    filter_priority: str | None = None,
    as_json: bool = False,
) -> str:
    """Bulk update issues matching filters.

    Args:
        new_status: New status to set.
        new_priority: New priority to set.
        filter_status: Filter by current status.
        filter_priority: Filter by current priority.
        as_json: Output as JSON.

    Returns:
        Formatted output with count of updated issues.

    Raises:
        ValueError: If invalid parameters provided.
    """
    count = self.repo.bulk_update_issues(
        new_status=new_status,
        new_priority=new_priority,
        filter_status=filter_status,
        filter_priority=filter_priority,
    )

    result = {
        "message": f"Updated {count} issue(s)",
        "count": count,
    }
    return self.format_output(result, as_json)


def delete_issue(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """Delete an issue.

    Args:
        issue_id: Issue ID.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If issue not found.
    """
    if not self.repo.delete_issue(issue_id):
        raise ValueError(f"Issue {issue_id} not found")

    result = {"message": f"Issue {issue_id} deleted successfully"}
    return self.format_output(result, as_json)


def get_next_issue(self: CLI, status: str | None = None, as_json: bool = False) -> str:
    """Get next issue to work on.

    Args:
        status: Filter by status.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    issue = self.repo.get_next_issue(status=status)
    if not issue:
        result = {"message": "No issues found matching criteria"}
        return self.format_output(result, as_json)
    return self.format_output(issue, as_json)


def search_issues(
    self: CLI,
    keyword: str,
    limit: int | None = None,
    as_json: bool = False,
) -> str:
    """Search issues by keyword.

    Args:
        keyword: Search keyword.
        limit: Maximum results.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    issues = self.repo.search_issues(keyword=keyword, limit=limit)
    return self.format_output(issues, as_json)


def clear_all(self: CLI, confirm: bool = False, as_json: bool = False) -> str:
    """Clear all issues from database.

    Args:
        confirm: Safety confirmation.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If not confirmed.
    """
    if not confirm:
        raise ValueError("Must use --confirm flag to clear all issues")

    count = self.repo.clear_all_issues()
    result = {"message": f"Cleared {count} issues from database"}
    return self.format_output(result, as_json)


def get_last_fetched(self: CLI, limit: int = 1, as_json: bool = False) -> str:
    """Get the last fetched issue(s).

    Args:
        limit: Maximum number of issues to return.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    issues = self.repo.get_last_fetched(limit=limit)
    if not issues:
        result = {"message": "No fetched issues found in history"}
        return self.format_output(result, as_json)
    return self.format_output(issues, as_json)
