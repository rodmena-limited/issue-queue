"""Issue context generation for LLM agents."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from issuedb.models import AuditLog, Comment, Issue, Priority, Status

if TYPE_CHECKING:
    from issuedb.cli import CLI


def get_issue_context(
    self: CLI,
    issue_id: int,
    as_json: bool = False,
    compact: bool = False,
) -> str:
    """Get comprehensive context about an issue for LLM agents.

    Args:
        issue_id: Issue ID.
        as_json: Output as JSON.
        compact: Minimal output (just issue + comments).

    Returns:
        Formatted context output.

    Raises:
        ValueError: If issue not found.
    """
    # Get the issue
    issue = self.repo.get_issue(issue_id)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found")

    # Get comments
    comments = self.repo.get_comments(issue_id)

    # Get audit history (last 10 entries)
    audit_logs = self.repo.get_audit_logs(issue_id=issue_id)
    recent_audit = audit_logs[:10] if not compact else []

    # Get git info if available and not in compact mode
    git_info = None
    if not compact:
        git_info = self._get_git_info(issue_id)

    # Get related issues (similar title/description) if not in compact mode
    related_issues = []
    if not compact and issue.title:
        # Search for similar issues (exclude current issue)
        first_word = issue.title.split()[0] if issue.title.split() else ""
        similar = self.repo.search_issues(keyword=first_word, limit=5)
        related_issues = [iss for iss in similar if iss.id != issue_id][:3]

    # Generate suggested actions
    suggested_actions = self._generate_suggested_actions(issue)

    # Build context object
    context = {
        "issue": issue.to_dict(),
        "comments": [c.to_dict() for c in comments],
        "comments_count": len(comments),
    }

    if not compact:
        context["audit_history"] = [log.to_dict() for log in recent_audit]
        context["audit_history_count"] = len(recent_audit)
        context["related_issues"] = [iss.to_dict() for iss in related_issues]
        context["related_issues_count"] = len(related_issues)
        if git_info:
            context["git_info"] = git_info
        context["suggested_actions"] = suggested_actions

    # Format output
    if as_json:
        return json.dumps(context, indent=2)
    else:
        return self._format_issue_context(
            issue=issue,
            comments=comments,
            audit_logs=recent_audit,
            related_issues=related_issues,
            git_info=git_info,
            suggested_actions=suggested_actions,
            compact=compact,
        )


def _get_git_info(self: CLI, issue_id: int) -> dict[str, Any] | None:
    """Get git information related to an issue.

    Args:
        issue_id: Issue ID.

    Returns:
        Dictionary with git info, or None if not in git repo.
    """
    import subprocess

    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None

        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        # Search for commits mentioning this issue ID
        # Look for patterns like "#ID", "issue ID", "issue #ID", etc.
        patterns = [f"#{issue_id}", f"issue {issue_id}", f"issue #{issue_id}"]
        recent_commits = []

        for pattern in patterns:
            commit_result = subprocess.run(
                ["git", "log", "--all", f"--grep={pattern}", "-i", "--oneline", "-n", "5"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if commit_result.returncode == 0 and commit_result.stdout.strip():
                commits = commit_result.stdout.strip().split("\n")
                for commit in commits:
                    if commit and commit not in recent_commits:
                        recent_commits.append(commit)

        git_info = {
            "current_branch": current_branch,
            "related_commits": recent_commits[:5],  # Limit to 5 commits
            "related_commits_count": len(recent_commits[:5]),
        }

        return git_info

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Git not available or timeout
        return None


def _generate_suggested_actions(self: CLI, issue: Issue) -> list[str]:
    """Generate suggested actions based on issue status.

    Args:
        issue: Issue object.

    Returns:
        List of suggested action strings.
    """
    actions = []

    if issue.status == Status.OPEN:
        actions.append(
            f"Issue is open - start work with: issuedb-cli update {issue.id} -s in-progress"
        )
        if issue.priority == Priority.CRITICAL or issue.priority == Priority.HIGH:
            actions.append("High priority issue - should be addressed soon")
    elif issue.status == Status.IN_PROGRESS:
        actions.append("Issue is in-progress - consider adding a progress update comment")
        actions.append(f"When complete, close with: issuedb-cli update {issue.id} -s closed")
    elif issue.status == Status.CLOSED:
        actions.append("Issue is closed - can be reopened if needed")
    elif issue.status == Status.WONT_DO:
        actions.append("Issue marked as won't do - can be reopened if needed")

    # Check if there are no comments
    comments_count = len(self.repo.get_comments(issue.id)) if issue.id else 0
    if comments_count == 0:
        actions.append(
            f"No comments yet - add notes with: "
            f"issuedb-cli comment {issue.id} -t 'your comment'"
        )

    return actions


def _format_issue_context(
    self: CLI,
    issue: Issue,
    comments: list[Comment],
    audit_logs: list[AuditLog],
    related_issues: list[Issue],
    git_info: dict[str, Any] | None,
    suggested_actions: list[str],
    compact: bool = False,
) -> str:
    """Format issue context for text output.

    Args:
        issue: Issue object.
        comments: List of Comment objects.
        audit_logs: List of AuditLog objects.
        related_issues: List of related Issue objects.
        git_info: Git information dictionary.
        suggested_actions: List of suggested action strings.
        compact: If True, show minimal output.

    Returns:
        Formatted string.
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append("ISSUE CONTEXT")
    lines.append("=" * 60)
    lines.append("")

    # Issue details
    lines.append(f"## Issue #{issue.id}")
    lines.append(f"Title: {issue.title}")
    lines.append(f"Status: {issue.status.value}")
    lines.append(f"Priority: {issue.priority.value}")
    lines.append(f"Created: {issue.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Updated: {issue.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Description
    if issue.description:
        lines.append("## Description")
        lines.append(issue.description)
        lines.append("")

    # Comments
    if comments:
        lines.append(f"## Comments ({len(comments)})")
        for comment in comments:
            timestamp = comment.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{timestamp}] {comment.text}")
        lines.append("")
    else:
        lines.append("## Comments")
        lines.append("No comments yet.")
        lines.append("")

    # Skip the rest if compact mode
    if compact:
        return "\n".join(lines)

    # Recent activity
    if audit_logs:
        lines.append(f"## Recent Activity (Last {len(audit_logs)} changes)")
        for log in audit_logs:
            timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M")
            if log.action in ["CREATE", "BULK_CREATE"]:
                lines.append(f"- {timestamp}: Issue created")
            elif log.action in ["UPDATE", "BULK_UPDATE"]:
                if log.field_name:
                    lines.append(
                        f"- {timestamp}: {log.field_name} changed "
                        f"from '{log.old_value}' to '{log.new_value}'"
                    )
                else:
                    lines.append(f"- {timestamp}: Issue updated")
            elif log.action == "DELETE":
                lines.append(f"- {timestamp}: Issue deleted")
            elif log.action == "FETCH":
                lines.append(f"- {timestamp}: Issue fetched via get-next")
        lines.append("")

    # Related issues
    if related_issues:
        lines.append(f"## Related Issues ({len(related_issues)})")
        for rel_issue in related_issues:
            lines.append(
                f"- #{rel_issue.id}: {rel_issue.title} "
                f"({rel_issue.status.value}, {rel_issue.priority.value})"
            )
        lines.append("")

    # Git information
    if git_info:
        lines.append("## Git Information")
        if git_info.get("current_branch"):
            lines.append(f"Current branch: {git_info['current_branch']}")
        if git_info.get("related_commits"):
            lines.append(f"Related commits ({len(git_info['related_commits'])}):")
            for commit in git_info["related_commits"]:
                lines.append(f"  {commit}")
        elif git_info.get("current_branch"):
            lines.append("No commits found mentioning this issue")
        lines.append("")

    # Suggested actions
    if suggested_actions:
        lines.append("## Suggested Actions")
        for action in suggested_actions:
            lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines)

    return "\n".join(lines)
