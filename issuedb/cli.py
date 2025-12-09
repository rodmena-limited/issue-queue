"""Command-line interface for IssueDB."""

import argparse
import json
import sys
from typing import Any, Optional

from issuedb.models import AuditLog, Comment, Issue, Priority, Status
from issuedb.repository import IssueRepository


class CLI:
    """Command-line interface handler."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize CLI with repository.

        Args:
            db_path: Optional path to database file.
        """
        self.repo = IssueRepository(db_path)

    def format_output(self, data: Any, as_json: bool = False) -> str:
        """Format output for display.

        Args:
            data: Data to format (Issue, list of Issues, dict, etc).
            as_json: If True, output as JSON.

        Returns:
            Formatted string output.
        """
        if as_json:
            if isinstance(data, Issue):
                return json.dumps(data.to_dict(), indent=2)
            elif isinstance(data, list) and all(isinstance(i, Issue) for i in data):
                return json.dumps([i.to_dict() for i in data], indent=2)
            elif isinstance(data, dict):
                return json.dumps(data, indent=2)
            else:
                return json.dumps(data, indent=2)
        else:
            if isinstance(data, Issue):
                return self._format_issue(data)
            elif isinstance(data, list) and all(isinstance(i, Issue) for i in data):
                if not data:
                    return "No issues found."
                return "\n\n".join(self._format_issue(i) for i in data)
            elif isinstance(data, dict):
                return self._format_dict(data)
            else:
                return str(data)

    def _format_issue(self, issue: Issue) -> str:
        """Format a single issue for display.

        Args:
            issue: Issue to format.

        Returns:
            Formatted string.
        """
        lines = [
            f"ID: {issue.id}",
            f"Title: {issue.title}",
            f"Status: {issue.status.value}",
            f"Priority: {issue.priority.value}",
        ]

        if issue.due_date:
            lines.append(f"Due Date: {issue.due_date.strftime('%Y-%m-%d')}")

        if issue.tags:
            tag_names = [t.name for t in issue.tags]
            lines.append(f"Tags: {', '.join(tag_names)}")

        if issue.description:
            lines.append(f"Description: {issue.description}")

        lines.extend(
            [
                f"Created: {issue.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Updated: {issue.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            ]
        )

        # Add code references if any
        if issue.id is not None:
            refs = self.repo.get_code_references(issue.id)
            if refs:
                lines.append("")
                lines.append("Code References:")
                for ref in refs:
                    ref_str = f"  - {ref.file_path}"
                    if ref.start_line and ref.end_line:
                        ref_str += f":{ref.start_line}-{ref.end_line}"
                    elif ref.start_line:
                        ref_str += f":{ref.start_line}"
                    if ref.note:
                        ref_str += f" ({ref.note})"
                    lines.append(ref_str)

        return "\n".join(lines)

    def _format_dict(self, data: dict[str, Any]) -> str:
        """Format a dictionary for display.

        Args:
            data: Dictionary to format.

        Returns:
            Formatted string.
        """
        lines = []
        for key, value in data.items():
            formatted_key = key.replace("_", " ").title()
            lines.append(f"{formatted_key}: {value}")
        return "\n".join(lines)

    def create_issue(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        status: str = "open",
        due_date: Optional[str] = None,
        as_json: bool = False,
        force: bool = False,
        check_duplicates: bool = False,
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

        Returns:
            Formatted output.
        """
        from datetime import datetime

        from issuedb.similarity import find_similar_issues

        due_date_obj = None
        if due_date:
            try:
                due_date_obj = datetime.fromisoformat(due_date)
            except ValueError:
                if as_json:
                    return json.dumps({"error": "Invalid date format"}, indent=2)
                return "Error: Invalid date format (use YYYY-MM-DD)"

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

            # If similar issues found and not forced, show warning
            if similar_issues and not force:
                if as_json:
                    warnings = []
                    for similar_issue, similarity in similar_issues[:3]:  # Show top 3
                        warnings.append(
                            {
                                "id": similar_issue.id,
                                "title": similar_issue.title,
                                "similarity": round(similarity * 100, 1),
                            }
                        )
                    return json.dumps(
                        {
                            "error": "Similar issues found",
                            "message": "Use --force to create anyway",
                            "similar_issues": warnings,
                        },
                        indent=2,
                    )
                else:
                    lines = ["Warning: Similar issues found:"]
                    for similar_issue, similarity in similar_issues[:3]:  # Show top 3
                        lines.append(
                            f"  - Issue #{similar_issue.id}: {similar_issue.title} "
                            f"({round(similarity * 100, 1)}% similar)"
                        )
                    lines.append("\nUse --force to create anyway")
                    return "\n".join(lines)

        created_issue = self.repo.create_issue(issue)
        return self.format_output(created_issue, as_json)

    def list_issues(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None,
        due_date: Optional[str] = None,
        tag: Optional[str] = None,
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

    def get_issue(self, issue_id: int, as_json: bool = False) -> str:
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

    def update_issue(self, issue_id: int, as_json: bool = False, **updates: Any) -> str:
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
        # Validate due_date if present
        if "due_date" in updates and updates["due_date"]:
            import contextlib

            with contextlib.suppress(ValueError):
                # Just check format, value is passed as string to repo which handles conversion
                # Actually repo update_issue expects string for due_date based on my update?
                # Let's check repo.update_issue again.
                # My update to repo.update_issue handles string conversion.
                # "elif field == "due_date": if value: try: datetime.fromisoformat(value) ..."
                # So we just pass the string.
                pass

        issue = self.repo.update_issue(issue_id, **updates)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        return self.format_output(issue, as_json)

    def bulk_update_issues(
        self,
        new_status: Optional[str] = None,
        new_priority: Optional[str] = None,
        filter_status: Optional[str] = None,
        filter_priority: Optional[str] = None,
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

    def delete_issue(self, issue_id: int, as_json: bool = False) -> str:
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

    def get_next_issue(self, status: Optional[str] = None, as_json: bool = False) -> str:
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
        self,
        keyword: str,
        limit: Optional[int] = None,
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

    def clear_all(self, confirm: bool = False, as_json: bool = False) -> str:
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

    def get_audit_logs(
        self,
        issue_id: Optional[int] = None,
        as_json: bool = False,
    ) -> str:
        """Get audit logs.

        Args:
            issue_id: Filter by issue ID.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        logs = self.repo.get_audit_logs(issue_id=issue_id)

        if as_json:
            return json.dumps([log.to_dict() for log in logs], indent=2)
        else:
            if not logs:
                return "No audit logs found."

            lines = []
            for log in logs:
                lines.append("-" * 50)
                lines.append(f"Timestamp: {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append(f"Issue ID: {log.issue_id}")
                lines.append(f"Action: {log.action}")

                if log.field_name:
                    lines.append(f"Field: {log.field_name}")
                    lines.append(f"Old Value: {log.old_value}")
                    lines.append(f"New Value: {log.new_value}")
                elif log.action == "CREATE":
                    lines.append(f"Created: {log.new_value}")
                elif log.action == "DELETE":
                    lines.append(f"Deleted: {log.old_value}")

            return "\n".join(lines)

    def get_info(self, as_json: bool = False) -> str:
        """Get database information.

        Args:
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        info = self.repo.db.get_database_info()
        return self.format_output(info, as_json)

    def get_summary(self, as_json: bool = False) -> str:
        """Get summary statistics of issues.

        Args:
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        summary = self.repo.get_summary()
        return self.format_output(summary, as_json)

    def get_report(
        self,
        group_by: str = "status",
        as_json: bool = False,
    ) -> str:
        """Get detailed report of issues.

        Args:
            group_by: Group by 'status' or 'priority'.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        report = self.repo.get_report(group_by=group_by)
        return self.format_output(report, as_json)

    def bulk_create(self, json_input: str, as_json: bool = False) -> str:
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

    def bulk_update_json(self, json_input: str, as_json: bool = False) -> str:
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

    def bulk_close(self, json_input: str, as_json: bool = False) -> str:
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

    def add_comment(self, issue_id: int, text: str, as_json: bool = False) -> str:
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

    def list_comments(self, issue_id: int, as_json: bool = False) -> str:
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

    def delete_comment(self, comment_id: int, as_json: bool = False) -> str:
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

    def get_last_fetched(self, limit: int = 1, as_json: bool = False) -> str:
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

    def find_similar_issues(
        self,
        query: str,
        threshold: float = 0.6,
        limit: Optional[int] = 10,
        as_json: bool = False,
    ) -> str:
        """Find issues similar to given text.

        Args:
            query: Text to find similar issues for.
            threshold: Similarity threshold (0.0 to 1.0).
            limit: Maximum number of results.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        from issuedb.similarity import find_similar_issues

        # Get all issues
        all_issues = self.repo.get_all_issues()

        # Find similar issues
        similar_issues = find_similar_issues(query, all_issues, threshold=threshold)

        # Limit results
        if limit:
            similar_issues = similar_issues[:limit]

        if as_json:
            results = []
            for issue, similarity in similar_issues:
                issue_dict = issue.to_dict()
                issue_dict["similarity"] = round(similarity * 100, 1)
                results.append(issue_dict)
            return json.dumps(results, indent=2)
        else:
            if not similar_issues:
                return "No similar issues found."

            lines = [f"Found {len(similar_issues)} similar issue(s):\n"]
            for issue, similarity in similar_issues:
                lines.append(f"Issue #{issue.id} ({round(similarity * 100, 1)}% similar)")
                lines.append(f"  Title: {issue.title}")
                lines.append(f"  Status: {issue.status.value}")
                lines.append(f"  Priority: {issue.priority.value}")
                lines.append("")

            return "\n".join(lines)

    def find_duplicates(
        self,
        threshold: float = 0.7,
        as_json: bool = False,
    ) -> str:
        """Find potential duplicate issues.

        Args:
            threshold: Similarity threshold for considering duplicates.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        from issuedb.similarity import find_duplicate_groups

        # Get all issues
        all_issues = self.repo.get_all_issues()

        # Find duplicate groups
        duplicate_groups = find_duplicate_groups(all_issues, threshold=threshold)

        if as_json:
            groups_data = []
            for group in duplicate_groups:
                duplicates_list: list[dict[str, Any]] = []
                for issue, similarity in group[1:]:
                    dup_dict = issue.to_dict()
                    dup_dict["similarity"] = round(similarity * 100, 1)
                    duplicates_list.append(dup_dict)
                group_data = {"primary": group[0][0].to_dict(), "duplicates": duplicates_list}
                groups_data.append(group_data)

            return json.dumps(
                {"total_groups": len(duplicate_groups), "groups": groups_data}, indent=2
            )
        else:
            if not duplicate_groups:
                return "No potential duplicates found."

            lines = [f"Found {len(duplicate_groups)} group(s) of potential duplicates:\n"]

            for i, group in enumerate(duplicate_groups, 1):
                primary_issue, _ = group[0]
                lines.append(f"Group {i}:")
                lines.append(f"  Primary: Issue #{primary_issue.id} - {primary_issue.title}")
                lines.append("  Potential duplicates:")

                for issue, similarity in group[1:]:
                    lines.append(
                        f"    - Issue #{issue.id}: {issue.title} "
                        f"({round(similarity * 100, 1)}% similar)"
                    )
                lines.append("")

            return "\n".join(lines)

    def get_issue_context(
        self,
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

    def _get_git_info(self, issue_id: int) -> Optional[dict[str, Any]]:
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

    def _generate_suggested_actions(self, issue: Issue) -> list[str]:
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
        self,
        issue: Issue,
        comments: list[Comment],
        audit_logs: list[AuditLog],
        related_issues: list[Issue],
        git_info: Optional[dict[str, Any]],
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

    # Memory CLI methods

    def memory_add(
        self, key: str, value: str, category: str = "general", as_json: bool = False
    ) -> str:
        """Add memory item."""
        try:
            memory = self.repo.add_memory(key, value, category)
            if as_json:
                return json.dumps(memory.to_dict(), indent=2)
            return f"Memory added: {key} ({category})"
        except ValueError as e:
            return json.dumps({"error": str(e)}) if as_json else str(e)

    def memory_list(
        self, category: Optional[str] = None, search: Optional[str] = None, as_json: bool = False
    ) -> str:
        """List memory items."""
        memories = self.repo.list_memory(category, search)
        if as_json:
            return json.dumps([m.to_dict() for m in memories], indent=2)

        if not memories:
            return "No memory items found."

        lines = []
        for m in memories:
            lines.append(f"[{m.category}] {m.key}: {m.value}")
        return "\n".join(lines)

    def memory_update(
        self,
        key: str,
        value: Optional[str] = None,
        category: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Update memory item."""
        memory = self.repo.update_memory(key, value, category)
        if not memory:
            msg = f"Memory '{key}' not found"
            return json.dumps({"error": msg}) if as_json else msg

        if as_json:
            return json.dumps(memory.to_dict(), indent=2)
        return f"Memory updated: {key}"

    def memory_delete(self, key: str, as_json: bool = False) -> str:
        """Delete memory item."""
        if self.repo.delete_memory(key):
            msg = f"Memory '{key}' deleted"
            return json.dumps({"message": msg}) if as_json else msg
        msg = f"Memory '{key}' not found"
        return json.dumps({"error": msg}) if as_json else msg

    # Lesson CLI methods

    def lesson_add(
        self,
        lesson: str,
        issue_id: Optional[int] = None,
        category: str = "general",
        as_json: bool = False,
    ) -> str:
        """Add lesson learned."""
        try:
            ll = self.repo.add_lesson(lesson, issue_id, category)
            if as_json:
                return json.dumps(ll.to_dict(), indent=2)
            return f"Lesson added: {ll.id}"
        except ValueError as e:
            return json.dumps({"error": str(e)}) if as_json else str(e)

    def lesson_list(
        self, issue_id: Optional[int] = None, category: Optional[str] = None, as_json: bool = False
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

    # Tag CLI methods

    def tag_issue(self, issue_id: int, tags: list[str], as_json: bool = False) -> str:
        """Add tags to issue."""
        added = []
        for tag in tags:
            if self.repo.add_issue_tag(issue_id, tag):
                added.append(tag)

        if as_json:
            return json.dumps({"added": added}, indent=2)
        return f"Added tags to issue #{issue_id}: {', '.join(added)}"

    def untag_issue(self, issue_id: int, tags: list[str], as_json: bool = False) -> str:
        """Remove tags from issue."""
        removed = []
        for tag in tags:
            if self.repo.remove_issue_tag(issue_id, tag):
                removed.append(tag)

        if as_json:
            return json.dumps({"removed": removed}, indent=2)
        return f"Removed tags from issue #{issue_id}: {', '.join(removed)}"

    def tag_list(self, as_json: bool = False) -> str:
        """List all available tags."""
        tags = self.repo.list_tags()
        if as_json:
            return json.dumps([t.to_dict() for t in tags], indent=2)
        return ", ".join([t.name for t in tags])

    # Link CLI methods

    def link_issues(self, source: int, target: int, type: str, as_json: bool = False) -> str:
        """Link issues."""
        try:
            rel = self.repo.link_issues(source, target, type)
            if as_json:
                return json.dumps(rel.to_dict(), indent=2)
            return f"Linked #{source} to #{target} ({type})"
        except ValueError as e:
            return json.dumps({"error": str(e)}) if as_json else str(e)

    def unlink_issues(
        self, source: int, target: int, type: Optional[str] = None, as_json: bool = False
    ) -> str:
        """Unlink issues."""
        if self.repo.unlink_issues(source, target, type):
            msg = f"Unlinked #{source} and #{target}"
            return json.dumps({"message": msg}) if as_json else msg
        msg = "Link not found"
        return json.dumps({"error": msg}) if as_json else msg

    def workspace_status(self, as_json: bool = False) -> str:
        """Get workspace status.

        Args:
            as_json: Output as JSON.

        Returns:
            Formatted workspace status.
        """
        status = self.repo.get_workspace_status()

        if as_json:
            return json.dumps(status, indent=2)
        else:
            lines = ["=== Workspace Status ==="]

            # Git branch
            if status.get("git_branch"):
                lines.append(f"Git Branch: {status['git_branch']}")
            else:
                lines.append("Git Branch: (not in git repo)")

            # Active issue
            if status.get("active_issue"):
                active = status["active_issue"]
                lines.append(
                    f"Active Issue: #{active['id']} - {active['title']} ({active['status']})"
                )
                lines.append(f"Time on Issue: {active['time_spent']}")
            else:
                lines.append("Active Issue: None")

            # Uncommitted files
            if status.get("uncommitted_files") is not None:
                lines.append(f"Uncommitted Files: {status['uncommitted_files']}")

            # Recent activity
            if status.get("recent_activity"):
                lines.append("")
                lines.append("Recent Activity:")
                for activity in status["recent_activity"]:
                    action_str = "started" if activity["action"] == "WORKSPACE_START" else "stopped"
                    title = activity.get("title", f"Issue #{activity['issue_id']}")
                    lines.append(f"- {title} ({action_str} {activity['time_ago']})")

            return "\n".join(lines)

    def start_issue_workspace(self, issue_id: int, as_json: bool = False) -> str:
        """Start working on an issue.

        Args:
            issue_id: Issue ID to start.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If issue not found.
        """
        issue, started_at = self.repo.start_issue(issue_id)

        if as_json:
            return json.dumps(
                {
                    "message": f"Started working on issue {issue_id}",
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                },
                indent=2,
            )
        else:
            lines = [
                f"Started working on issue #{issue_id}",
                f"Title: {issue.title}",
                f"Status: {issue.status.value}",
                f"Started at: {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            ]
            return "\n".join(lines)

    def stop_issue_workspace(self, close: bool = False, as_json: bool = False) -> str:
        """Stop working on the active issue.

        Args:
            close: If True, also close the issue.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """

        result = self.repo.stop_issue(close=close)

        if not result:
            msg = {"message": "No active issue to stop"}
            return json.dumps(msg, indent=2) if as_json else msg["message"]

        issue, started_at, stopped_at = result
        time_spent = stopped_at - started_at
        hours = int(time_spent.total_seconds() // 3600)
        minutes = int((time_spent.total_seconds() % 3600) // 60)

        if as_json:
            return json.dumps(
                {
                    "message": f"Stopped working on issue {issue.id}",
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                    "stopped_at": stopped_at.isoformat(),
                    "time_spent": f"{hours}h {minutes}m",
                    "time_spent_seconds": int(time_spent.total_seconds()),
                },
                indent=2,
            )
        else:
            lines = [
                f"Stopped working on issue #{issue.id}",
                f"Title: {issue.title}",
                f"Time spent: {hours}h {minutes}m",
            ]
            if close:
                lines.append(f"Status: {issue.status.value}")
            return "\n".join(lines)

    def get_active_issue_workspace(self, as_json: bool = False) -> str:
        """Get the currently active issue.

        Args:
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        from datetime import datetime

        active = self.repo.get_active_issue()

        if not active:
            msg = {"message": "No active issue"}
            return json.dumps(msg, indent=2) if as_json else msg["message"]

        issue, started_at = active
        time_spent = datetime.now() - started_at
        hours = int(time_spent.total_seconds() // 3600)
        minutes = int((time_spent.total_seconds() % 3600) // 60)

        if as_json:
            return json.dumps(
                {
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                    "time_spent": f"{hours}h {minutes}m",
                    "time_spent_seconds": int(time_spent.total_seconds()),
                },
                indent=2,
            )
        else:
            lines = [
                f"Active Issue: #{issue.id}",
                f"Title: {issue.title}",
                f"Status: {issue.status.value}",
                f"Priority: {issue.priority.value}",
                f"Started at: {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Time spent: {hours}h {minutes}m",
            ]
            return "\n".join(lines)

    # Time tracking methods

    def timer_start(self, issue_id: int, note: Optional[str] = None, as_json: bool = False) -> str:
        """Start a timer for an issue.

        Args:
            issue_id: Issue ID to start timer for.
            note: Optional note for this time entry.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        entry = self.repo.start_timer(issue_id, note)
        result = {
            "message": f"Timer started for issue #{issue_id}",
            "entry_id": entry.get("id"),
            "issue_id": issue_id,
        }
        if note:
            result["note"] = note
        return self.format_output(result, as_json)

    def timer_stop(self, issue_id: Optional[int] = None, as_json: bool = False) -> str:
        """Stop a timer for an issue.

        Args:
            issue_id: Issue ID (stops all running timers for this issue if None).
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        try:
            entry = self.repo.stop_timer(issue_id)
            duration = entry.get("duration_seconds", 0)
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            result = {
                "message": "Timer stopped",
                "entry_id": entry.get("id"),
                "issue_id": entry.get("issue_id"),
                "duration_seconds": duration,
                "duration_formatted": f"{hours}h {minutes}m {seconds}s",
            }
            return self.format_output(result, as_json)
        except ValueError:
            result = {"message": "No running timer found"}
            return self.format_output(result, as_json)

    def timer_status(self, as_json: bool = False) -> str:
        """Show running timers.

        Args:
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        running = self.repo.get_running_timers()
        if not running:
            result = {"message": "No running timers", "timers": []}
            return self.format_output(result, as_json)

        timers = []
        for entry in running:
            # Repo already calculates elapsed_seconds
            elapsed = entry.get("elapsed_seconds", 0)
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            timers.append(
                {
                    "entry_id": entry["id"],
                    "issue_id": entry["issue_id"],
                    "issue_title": entry.get("issue_title", ""),
                    "started_at": entry["started_at"],
                    "elapsed": f"{hours}h {minutes}m",
                    "elapsed_seconds": elapsed,
                    "note": entry.get("note"),
                }
            )

        if as_json:
            return json.dumps({"timers": timers}, indent=2)
        else:
            lines = ["Running Timers:"]
            for t in timers:
                note_str = f" - {t['note']}" if t.get("note") else ""
                lines.append(f"  #{t['issue_id']} {t['issue_title']}: {t['elapsed']}{note_str}")
            return "\n".join(lines)

    def set_estimate(self, issue_id: int, hours: float, as_json: bool = False) -> str:
        """Set time estimate for an issue.

        Args:
            issue_id: Issue ID.
            hours: Estimated hours.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        self.repo.set_estimate(issue_id, hours)
        result = {
            "message": f"Estimate set for issue {issue_id}",
            "issue_id": issue_id,
            "estimated_hours": hours,
        }
        return self.format_output(result, as_json)

    def time_log(self, issue_id: int, as_json: bool = False) -> str:
        """Show time entries for an issue.

        Args:
            issue_id: Issue ID.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        entries = self.repo.get_time_entries(issue_id)

        if not entries:
            result = {"message": f"No time entries for issue {issue_id}", "entries": []}
            return self.format_output(result, as_json)

        formatted = []
        total_seconds = 0
        for entry in entries:
            duration = entry.get("duration_seconds", 0) or 0
            total_seconds += duration
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            formatted.append(
                {
                    "id": entry["id"],
                    "started_at": entry.get("started_at"),  # Already a string from SQLite
                    "ended_at": entry.get("ended_at"),
                    "duration": f"{hours}h {minutes}m",
                    "duration_seconds": duration,
                    "note": entry.get("note"),
                    "running": entry.get("ended_at") is None,
                }
            )

        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60

        if as_json:
            return json.dumps(
                {
                    "issue_id": issue_id,
                    "entries": formatted,
                    "total_seconds": total_seconds,
                    "total_formatted": f"{total_hours}h {total_minutes}m",
                },
                indent=2,
            )
        else:
            lines = [f"Time Log for Issue #{issue_id}:", ""]
            for e in formatted:
                status = "[RUNNING]" if e["running"] else ""
                note_str = f" - {e['note']}" if e.get("note") else ""
                lines.append(f"  {e['started_at']}: {e['duration']}{note_str} {status}")
            lines.append("")
            lines.append(f"Total: {total_hours}h {total_minutes}m")
            return "\n".join(lines)

    def time_report(
        self, period: str = "all", issue_id: Optional[int] = None, as_json: bool = False
    ) -> str:
        """Generate time report.

        Args:
            period: Time period (all, week, month).
            issue_id: Optional issue ID to filter by.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        report = self.repo.get_time_report(period, issue_id)

        if as_json:
            return json.dumps(report, indent=2)
        else:
            period_labels = {"all": "All Time", "week": "This Week", "month": "This Month"}
            period_label = period_labels.get(period, period)
            lines = [f"Time Report ({period_label})", "=" * 30]

            total_hours = report["total_seconds"] // 3600
            total_minutes = (report["total_seconds"] % 3600) // 60
            lines.append(f"Total: {total_hours}h {total_minutes}m")
            lines.append("")

            if report.get("issues"):
                lines.append("By Issue:")
                for item in report["issues"]:
                    seconds = item.get("total_seconds", 0)
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    estimate_str = ""
                    if item.get("estimated_hours"):
                        est_h = item["estimated_hours"]
                        if item.get("over_estimate"):
                            estimate_str = f" (est: {est_h}h) [OVER]"
                        else:
                            estimate_str = f" (est: {est_h}h)"
                    issue_id = item["issue_id"]
                    title = item["title"]
                    lines.append(f"  #{issue_id} {title}: {hours}h {minutes}m{estimate_str}")

            return "\n".join(lines)

    # Dependency management commands

    def block_issue(self, issue_id: int, blocker_id: int, as_json: bool = False) -> str:
        """Mark an issue as blocked by another issue.

        Args:
            issue_id: ID of the issue being blocked.
            blocker_id: ID of the issue that blocks.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If issues don't exist or operation is invalid.
        """
        try:
            added = self.repo.add_dependency(issue_id, blocker_id)
            if added:
                result = {
                    "message": f"Issue {issue_id} is now blocked by issue {blocker_id}",
                    "blocked_id": issue_id,
                    "blocker_id": blocker_id,
                }
            else:
                result = {
                    "message": f"Issue {issue_id} is already blocked by issue {blocker_id}",
                    "blocked_id": issue_id,
                    "blocker_id": blocker_id,
                }
            return self.format_output(result, as_json)
        except ValueError as e:
            raise ValueError(str(e)) from e

    def unblock_issue(
        self, issue_id: int, blocker_id: Optional[int] = None, as_json: bool = False
    ) -> str:
        """Remove block relationship(s) from an issue.

        Args:
            issue_id: ID of the blocked issue.
            blocker_id: ID of the blocker issue (if None, removes all blockers).
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        count = self.repo.remove_dependency(issue_id, blocker_id)

        if blocker_id:
            if count > 0:
                result = {
                    "message": f"Removed blocker {blocker_id} from issue {issue_id}",
                    "removed_count": count,
                }
            else:
                result = {
                    "message": f"No dependency found between issue {issue_id} "
                    f"and blocker {blocker_id}",
                    "removed_count": 0,
                }
        else:
            result = {
                "message": f"Removed {count} blocker(s) from issue {issue_id}",
                "removed_count": count,
            }

        return self.format_output(result, as_json)

    def show_dependencies(self, issue_id: int, as_json: bool = False) -> str:
        """Show dependency graph for an issue.

        Args:
            issue_id: ID of the issue.
            as_json: Output as JSON.

        Returns:
            Formatted output showing blockers and blocking issues.

        Raises:
            ValueError: If issue not found.
        """
        issue = self.repo.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        blockers = self.repo.get_blockers(issue_id)
        blocking = self.repo.get_blocking(issue_id)
        is_blocked = self.repo.is_blocked(issue_id)

        if as_json:
            result = {
                "issue_id": issue_id,
                "title": issue.title,
                "is_blocked": is_blocked,
                "blocked_by": [
                    {
                        "id": b.id,
                        "title": b.title,
                        "status": b.status.value,
                        "priority": b.priority.value,
                    }
                    for b in blockers
                ],
                "blocking": [
                    {
                        "id": b.id,
                        "title": b.title,
                        "status": b.status.value,
                        "priority": b.priority.value,
                    }
                    for b in blocking
                ],
            }
            return json.dumps(result, indent=2)
        else:
            lines = []
            lines.append(f"Dependencies for Issue #{issue_id}: {issue.title}")
            lines.append("=" * 60)
            lines.append("")

            if blockers:
                lines.append(f"Blocked by ({len(blockers)} issue(s)):")
                for blocker in blockers:
                    status_marker = "OPEN" if blocker.status != Status.CLOSED else "CLOSED"
                    lines.append(
                        f"  - Issue #{blocker.id}: {blocker.title} "
                        f"[{status_marker}, {blocker.priority.value}]"
                    )
                if is_blocked:
                    lines.append("\nThis issue is BLOCKED (has unresolved blockers)")
            else:
                lines.append("Blocked by: None")

            lines.append("")

            if blocking:
                lines.append(f"Blocking ({len(blocking)} issue(s)):")
                for blocked in blocking:
                    status_marker = "OPEN" if blocked.status != Status.CLOSED else "CLOSED"
                    lines.append(
                        f"  - Issue #{blocked.id}: {blocked.title} "
                        f"[{status_marker}, {blocked.priority.value}]"
                    )
            else:
                lines.append("Blocking: None")

            return "\n".join(lines)

    def list_blocked_issues(self, status: Optional[str] = None, as_json: bool = False) -> str:
        """List all blocked issues.

        Args:
            status: Optional filter by status.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issues = self.repo.get_all_blocked_issues(status=status)

        if as_json:
            result = []
            for issue in issues:
                if issue.id is None:
                    continue
                blockers = self.repo.get_blockers(issue.id)
                issue_dict = issue.to_dict()
                issue_dict["blockers"] = [
                    {"id": b.id, "title": b.title, "status": b.status.value} for b in blockers
                ]
                result.append(issue_dict)
            return json.dumps(result, indent=2)
        else:
            if not issues:
                return "No blocked issues found."

            lines = [f"Found {len(issues)} blocked issue(s):\n"]
            for issue in issues:
                if issue.id is None:
                    continue
                blockers = self.repo.get_blockers(issue.id)
                blocker_ids = ", ".join([f"#{b.id}" for b in blockers])
                lines.append(
                    f"Issue #{issue.id}: {issue.title} "
                    f"[{issue.status.value}, {issue.priority.value}]"
                )
                lines.append(f"  Blocked by: {blocker_ids}")
                lines.append("")

            return "\n".join(lines)

    # Code Reference Methods
    def attach_code_reference(
        self,
        issue_id: int,
        file_spec: str,
        note: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Attach a code reference to an issue.

        Args:
            issue_id: ID of the issue.
            file_spec: File path with optional line number (e.g., "file.py:10" or "file.py:10-20").
            note: Optional note about the reference.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        # Parse file spec
        file_path, start_line, end_line = self.repo.parse_file_spec(file_spec)

        ref = self.repo.add_code_reference(
            issue_id=issue_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            note=note,
        )

        if as_json:
            return json.dumps(ref.to_dict(), indent=2)
        else:
            lines = ["Code reference added:"]
            lines.append(f"  Issue: #{issue_id}")
            lines.append(f"  File: {ref.file_path}")
            if ref.start_line and ref.end_line:
                lines.append(f"  Lines: {ref.start_line}-{ref.end_line}")
            elif ref.start_line:
                lines.append(f"  Line: {ref.start_line}")
            if ref.note:
                lines.append(f"  Note: {ref.note}")
            return "\n".join(lines)

    def detach_code_reference(
        self,
        issue_id: int,
        file_path: Optional[str] = None,
        reference_id: Optional[int] = None,
        as_json: bool = False,
    ) -> str:
        """Detach a code reference from an issue.

        Args:
            issue_id: ID of the issue.
            file_path: File path to remove references for.
            reference_id: Specific reference ID to remove.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If neither file_path nor reference_id provided.
        """
        if not file_path and not reference_id:
            raise ValueError("Must provide --file or --reference-id")

        count = self.repo.remove_code_reference(
            issue_id=issue_id,
            file_path=file_path,
            reference_id=reference_id,
        )

        if as_json:
            return json.dumps({"removed_count": count}, indent=2)
        else:
            return f"Removed {count} code reference(s) from issue #{issue_id}"

    def list_code_references(self, issue_id: int, as_json: bool = False) -> str:
        """List all code references for an issue.

        Args:
            issue_id: ID of the issue.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        refs = self.repo.get_code_references(issue_id)

        if as_json:
            return json.dumps([ref.to_dict() for ref in refs], indent=2)
        else:
            if not refs:
                return "No code references found."

            lines = [f"Code references for issue #{issue_id}:"]
            for ref in refs:
                lines.append(f"\n  File: {ref.file_path}")
                if ref.start_line and ref.end_line:
                    lines.append(f"  Lines: {ref.start_line}-{ref.end_line}")
                elif ref.start_line:
                    lines.append(f"  Line: {ref.start_line}")
                if ref.note:
                    lines.append(f"  Note: {ref.note}")
            return "\n".join(lines)

    def list_affected_issues(self, file_path: str, as_json: bool = False) -> str:
        """List issues that reference a specific file.

        Args:
            file_path: File path to search for.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issues = self.repo.get_issues_by_file(file_path)

        if as_json:
            return json.dumps([issue.to_dict() for issue in issues], indent=2)
        else:
            if not issues:
                return f"No issues found referencing {file_path}"

            lines = [f"Issues referencing {file_path}:"]
            for issue in issues:
                lines.append(
                    f"  - Issue #{issue.id}: {issue.title} "
                    f"[{issue.status.value}, {issue.priority.value}]"
                )
            return "\n".join(lines)

    # Bulk Pattern Methods
    def bulk_close_pattern(
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
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
        if dry_run:
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
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
        use_regex: bool = False,
        new_status: Optional[str] = None,
        new_priority: Optional[str] = None,
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
        if dry_run:
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
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
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
        if dry_run:
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


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="issuedb-cli",
        description="Command-line issue tracking system for software development projects",
    )

    parser.add_argument(
        "--db",
        help="Path to database file (default: ~/.issuedb/issuedb.sqlite)",
        default=None,
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Output LLM agent prompt for using issuedb-cli",
    )

    parser.add_argument(
        "--ollama-model",
        type=str,
        default=None,
        help="Ollama model to use (default: from OLLAMA_MODEL env or 'llama3')",
    )

    parser.add_argument(
        "--ollama-host",
        type=str,
        default=None,
        help="Ollama server host (default: from OLLAMA_HOST env or 'localhost')",
    )

    parser.add_argument(
        "--ollama-port",
        type=int,
        default=None,
        help="Ollama server port (default: from OLLAMA_PORT env or 11434)",
    )

    parser.add_argument(
        "--ollama",
        nargs=argparse.REMAINDER,
        metavar="REQUEST",
        help="Natural language request (no quotes needed). Must be last flag. "
        "Example: issuedb-cli --ollama-model llama3 --ollama create a high priority bug",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new issue")
    create_parser.add_argument("-t", "--title", required=True, help="Issue title")
    create_parser.add_argument("-d", "--description", help="Issue description")
    create_parser.add_argument(
        "--priority",
        choices=["low", "medium", "high", "critical"],
        default="medium",
        help="Priority level",
    )
    create_parser.add_argument(
        "--status",
        choices=["open", "in-progress", "closed", "wont-do"],
        default="open",
        help="Initial status",
    )
    create_parser.add_argument("--due-date", help="Due date (YYYY-MM-DD)")

    # List command
    list_parser = subparsers.add_parser("list", help="List issues")
    list_parser.add_argument(
        "-s", "--status", help="Filter by status (open, in-progress, closed, wont-do)"
    )
    list_parser.add_argument("--priority", help="Filter by priority (low, medium, high, critical)")
    list_parser.add_argument("-l", "--limit", type=int, help="Maximum number of issues")
    list_parser.add_argument("--due-date", help="Filter by due date")
    list_parser.add_argument("--tag", help="Filter by tag")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get issue details")
    get_parser.add_argument("id", type=int, help="Issue ID")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update an issue")
    update_parser.add_argument("id", type=int, help="Issue ID")
    update_parser.add_argument("-t", "--title", help="New title")
    update_parser.add_argument("-d", "--description", help="New description")
    update_parser.add_argument(
        "--priority",
        choices=["low", "medium", "high", "critical"],
        help="New priority",
    )
    update_parser.add_argument(
        "-s",
        "--status",
        choices=["open", "in-progress", "closed", "wont-do"],
        help="New status",
    )
    update_parser.add_argument("--due-date", help="New due date")

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Manage memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", help="Memory commands")

    mem_add = memory_subparsers.add_parser("add", help="Add memory item")
    mem_add.add_argument("key", help="Memory key")
    mem_add.add_argument("value", help="Memory value")
    mem_add.add_argument("-c", "--category", default="general", help="Category")

    mem_list = memory_subparsers.add_parser("list", help="List memory items")
    mem_list.add_argument("-c", "--category", help="Filter by category")
    mem_list.add_argument("-q", "--search", help="Search term")

    mem_update = memory_subparsers.add_parser("update", help="Update memory item")
    mem_update.add_argument("key", help="Memory key")
    mem_update.add_argument("-v", "--value", help="New value")
    mem_update.add_argument("-c", "--category", help="New category")

    mem_del = memory_subparsers.add_parser("delete", help="Delete memory item")
    mem_del.add_argument("key", help="Memory key")

    # Lesson commands
    lesson_parser = subparsers.add_parser("lesson", help="Manage lessons learned")
    lesson_subparsers = lesson_parser.add_subparsers(dest="lesson_command", help="Lesson commands")

    les_add = lesson_subparsers.add_parser("add", help="Add lesson")
    les_add.add_argument("lesson", help="Lesson text")
    les_add.add_argument("-i", "--issue-id", type=int, help="Related issue ID")
    les_add.add_argument("-c", "--category", default="general", help="Category")

    les_list = lesson_subparsers.add_parser("list", help="List lessons")
    les_list.add_argument("-i", "--issue-id", type=int, help="Filter by issue ID")
    les_list.add_argument("-c", "--category", help="Filter by category")

    # Tag commands
    tag_parser = subparsers.add_parser("tag", help="Manage tags")
    tag_subparsers = tag_parser.add_subparsers(dest="tag_command", help="Tag commands")

    tag_subparsers.add_parser("list", help="List tags")

    tag_add = tag_subparsers.add_parser("add", help="Add tags to issue")
    tag_add.add_argument("issue_id", type=int, help="Issue ID")
    tag_add.add_argument("tags", nargs="+", help="Tags to add")

    tag_remove = tag_subparsers.add_parser("remove", help="Remove tags from issue")
    tag_remove.add_argument("issue_id", type=int, help="Issue ID")
    tag_remove.add_argument("tags", nargs="+", help="Tags to remove")

    # Link commands
    link_parser = subparsers.add_parser("link", help="Manage issue links")
    link_subparsers = link_parser.add_subparsers(dest="link_command", help="Link commands")

    link_add = link_subparsers.add_parser("add", help="Link issues")
    link_add.add_argument("source", type=int, help="Source Issue ID")
    link_add.add_argument("target", type=int, help="Target Issue ID")
    link_add.add_argument("type", help="Relation type (e.g. related, duplicates)")

    link_remove = link_subparsers.add_parser("remove", help="Unlink issues")
    link_remove.add_argument("source", type=int, help="Source Issue ID")
    link_remove.add_argument("target", type=int, help="Target Issue ID")
    link_remove.add_argument("--type", help="Specific relation type")

    # Bulk-update command
    bulk_update_parser = subparsers.add_parser(
        "bulk-update", help="Bulk update issues matching filters"
    )
    bulk_update_parser.add_argument(
        "--filter-status",
        choices=["open", "in-progress", "closed", "wont-do"],
        help="Filter by current status",
    )
    bulk_update_parser.add_argument(
        "--filter-priority",
        choices=["low", "medium", "high", "critical"],
        help="Filter by current priority",
    )
    bulk_update_parser.add_argument(
        "-s",
        "--status",
        choices=["open", "in-progress", "closed", "wont-do"],
        help="New status to set",
    )
    bulk_update_parser.add_argument(
        "--priority",
        choices=["low", "medium", "high", "critical"],
        help="New priority to set",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an issue")
    delete_parser.add_argument("id", type=int, help="Issue ID")

    # Get-next command
    next_parser = subparsers.add_parser(
        "get-next", help="Get next issue to work on (FIFO by priority)"
    )
    next_parser.add_argument("-s", "--status", help="Filter by status (defaults to 'open')")

    # Get-last command
    last_parser = subparsers.add_parser(
        "get-last", help="Get the last fetched issue(s) from get-next history"
    )
    last_parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=1,
        help="Number of last fetched issues to return (default: 1)",
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search issues by keyword")
    search_parser.add_argument("-k", "--keyword", required=True, help="Search keyword")
    search_parser.add_argument("-l", "--limit", type=int, help="Maximum results")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all issues from database")
    clear_parser.add_argument("--confirm", action="store_true", help="Confirm deletion (required)")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="View audit logs")
    audit_parser.add_argument("-i", "--issue", type=int, help="Filter by issue ID")

    # Info command
    subparsers.add_parser("info", help="Get database information")

    # Summary command
    subparsers.add_parser("summary", help="Get summary statistics of issues")

    # Report command
    report_parser = subparsers.add_parser("report", help="Get detailed report of issues")
    report_parser.add_argument(
        "--group-by",
        choices=["status", "priority"],
        default="status",
        help="Group issues by status or priority (default: status)",
    )

    # Bulk-create command
    bulk_create_parser = subparsers.add_parser(
        "bulk-create", help="Bulk create issues from JSON input"
    )
    bulk_create_parser.add_argument(
        "-f",
        "--file",
        help="JSON file path (if not provided, reads from stdin)",
    )
    bulk_create_parser.add_argument(
        "-d",
        "--data",
        help="JSON data as string",
    )

    # Bulk-update-json command
    bulk_update_json_parser = subparsers.add_parser(
        "bulk-update-json", help="Bulk update issues from JSON input"
    )
    bulk_update_json_parser.add_argument(
        "-f",
        "--file",
        help="JSON file path (if not provided, reads from stdin)",
    )
    bulk_update_json_parser.add_argument(
        "-d",
        "--data",
        help="JSON data as string",
    )

    # Bulk-close command
    bulk_close_parser = subparsers.add_parser(
        "bulk-close", help="Bulk close issues from JSON input (list of issue IDs)"
    )
    bulk_close_parser.add_argument(
        "-f",
        "--file",
        help="JSON file path (if not provided, reads from stdin)",
    )
    bulk_close_parser.add_argument(
        "-d",
        "--data",
        help="JSON data as string",
    )

    # Comment command
    comment_parser = subparsers.add_parser("comment", help="Add a comment to an issue")
    comment_parser.add_argument("issue_id", type=int, help="Issue ID")
    comment_parser.add_argument("-t", "--text", required=True, help="Comment text")

    # List-comments command
    list_comments_parser = subparsers.add_parser(
        "list-comments", help="List all comments for an issue"
    )
    list_comments_parser.add_argument("issue_id", type=int, help="Issue ID")

    # Delete-comment command
    delete_comment_parser = subparsers.add_parser("delete-comment", help="Delete a comment")
    delete_comment_parser.add_argument("comment_id", type=int, help="Comment ID")

    # Context command
    context_parser = subparsers.add_parser(
        "context", help="Get comprehensive context about an issue for LLM agents"
    )
    context_parser.add_argument("issue_id", type=int, help="Issue ID")
    context_parser.add_argument(
        "--compact",
        action="store_true",
        help="Minimal output (just issue + comments)",
    )

    # Workspace command
    subparsers.add_parser("workspace", help="Show current workspace status")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start working on an issue")
    start_parser.add_argument("issue_id", type=int, help="Issue ID to start working on")

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop working on active issue")
    stop_parser.add_argument(
        "--close",
        action="store_true",
        help="Also close the issue when stopping",
    )

    # Active command
    subparsers.add_parser("active", help="Show currently active issue")

    # Block command
    block_parser = subparsers.add_parser("block", help="Mark an issue as blocked by another issue")
    block_parser.add_argument("issue_id", type=int, help="ID of the issue being blocked")
    block_parser.add_argument(
        "--by",
        type=int,
        required=True,
        dest="blocker_id",
        help="ID of the issue that blocks",
    )

    # Unblock command
    unblock_parser = subparsers.add_parser(
        "unblock", help="Remove block relationship(s) from an issue"
    )
    unblock_parser.add_argument("issue_id", type=int, help="ID of the blocked issue")
    unblock_parser.add_argument(
        "--by",
        type=int,
        dest="blocker_id",
        help="ID of the blocker issue (if not specified, removes all blockers)",
    )

    # Deps command
    deps_parser = subparsers.add_parser("deps", help="Show dependency graph for an issue")
    deps_parser.add_argument("issue_id", type=int, help="Issue ID")

    # Blocked command
    blocked_parser = subparsers.add_parser("blocked", help="List all blocked issues")
    blocked_parser.add_argument(
        "-s", "--status", help="Filter by status (open, in-progress, closed, wont-do)"
    )

    # Web command
    web_parser = subparsers.add_parser("web", help="Start the web UI server")
    web_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    web_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=7760,
        help="Port to bind to (default: 7760)",
    )
    web_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )

    args = parser.parse_args()

    # Find-similar command
    find_similar_parser = subparsers.add_parser(
        "find-similar", help="Find issues similar to given text"
    )
    find_similar_parser.add_argument(
        "query",
        help="Text to find similar issues for",
    )
    find_similar_parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Similarity threshold (0.0 to 1.0, default: 0.6)",
    )
    find_similar_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )

    # Dedupe command
    dedupe_parser = subparsers.add_parser("dedupe", help="Find potential duplicate issues")
    dedupe_parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Similarity threshold for duplicates (0.0 to 1.0, default: 0.7)",
    )

    # Handle --prompt flag
    if args.prompt:
        from pathlib import Path

        # Get the prompt file path
        package_dir = Path(__file__).parent
        prompt_file = package_dir / "data" / "agents" / "PROMPT.txt"

        if prompt_file.exists():
            print(prompt_file.read_text(), file=sys.stdout, flush=True)
        else:
            print(f"Error: Prompt file not found at {prompt_file}", file=sys.stderr, flush=True)
            sys.exit(1)
        sys.exit(0)

    # Handle --ollama flag
    if args.ollama:
        from pathlib import Path

        from issuedb.ollama_client import handle_ollama_request

        # Join the list of words into a single request string
        user_request = " ".join(args.ollama)

        if not user_request.strip():
            print("Error: No request provided for --ollama", file=sys.stderr)
            sys.exit(1)

        # Get the prompt file path
        package_dir = Path(__file__).parent
        prompt_file = package_dir / "data" / "agents" / "PROMPT.txt"

        if not prompt_file.exists():
            print(f"Error: Prompt file not found at {prompt_file}", file=sys.stderr)
            sys.exit(1)

        prompt_text = prompt_file.read_text()

        # Handle Ollama request
        exit_code = handle_ollama_request(
            user_request=user_request,
            prompt_text=prompt_text,
            host=args.ollama_host,
            port=args.ollama_port,
            model=args.ollama_model,
        )
        sys.exit(exit_code)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        cli = CLI(args.db)

        if args.command == "create":
            result = cli.create_issue(
                title=args.title,
                description=args.description,
                priority=args.priority,
                status=args.status,
                due_date=args.due_date,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "list":
            result = cli.list_issues(
                status=args.status,
                priority=args.priority,
                limit=args.limit,
                due_date=args.due_date,
                tag=args.tag,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "get":
            result = cli.get_issue(args.id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "update":
            updates = {}
            if args.title:
                updates["title"] = args.title
            if args.description:
                updates["description"] = args.description
            if args.priority:
                updates["priority"] = args.priority
            if args.status:
                updates["status"] = args.status
            if args.due_date:
                updates["due_date"] = args.due_date

            if not updates:
                print("Error: No updates specified", file=sys.stderr, flush=True)
                sys.exit(1)

            result = cli.update_issue(args.id, as_json=args.json, **updates)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "memory":
            if not args.memory_command:
                parser.parse_args(["memory", "--help"])

            if args.memory_command == "add":
                result = cli.memory_add(args.key, args.value, args.category, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.memory_command == "list":
                result = cli.memory_list(args.category, args.search, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.memory_command == "update":
                result = cli.memory_update(args.key, args.value, args.category, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.memory_command == "delete":
                print(cli.memory_delete(args.key, args.json), file=sys.stdout, flush=True)

        elif args.command == "lesson":
            if not args.lesson_command:
                parser.parse_args(["lesson", "--help"])

            if args.lesson_command == "add":
                result = cli.lesson_add(args.lesson, args.issue_id, args.category, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.lesson_command == "list":
                result = cli.lesson_list(args.issue_id, args.category, args.json)
                print(result, file=sys.stdout, flush=True)

        elif args.command == "tag":
            if not args.tag_command:
                parser.parse_args(["tag", "--help"])

            if args.tag_command == "list":
                print(cli.tag_list(args.json), file=sys.stdout, flush=True)
            elif args.tag_command == "add":
                result = cli.tag_issue(args.issue_id, args.tags, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.tag_command == "remove":
                result = cli.untag_issue(args.issue_id, args.tags, args.json)
                print(result, file=sys.stdout, flush=True)

        elif args.command == "link":
            if not args.link_command:
                parser.parse_args(["link", "--help"])

            if args.link_command == "add":
                result = cli.link_issues(args.source, args.target, args.type, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.link_command == "remove":
                result = cli.unlink_issues(args.source, args.target, args.type, args.json)
                print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-update":
            if not args.status and not args.priority:
                msg = "Error: No updates specified (use -s or --priority)"
                print(msg, file=sys.stderr, flush=True)
                sys.exit(1)

            result = cli.bulk_update_issues(
                new_status=args.status,
                new_priority=args.priority,
                filter_status=args.filter_status,
                filter_priority=args.filter_priority,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "delete":
            result = cli.delete_issue(args.id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "get-next":
            result = cli.get_next_issue(status=args.status, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "get-last":
            result = cli.get_last_fetched(limit=args.number, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "search":
            result = cli.search_issues(
                keyword=args.keyword,
                limit=args.limit,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "clear":
            result = cli.clear_all(confirm=args.confirm, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "audit":
            result = cli.get_audit_logs(issue_id=args.issue, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "info":
            result = cli.get_info(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "summary":
            result = cli.get_summary(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "report":
            result = cli.get_report(group_by=args.group_by, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-create":
            # Get JSON input from file, data arg, or stdin
            json_input = None
            if args.data:
                json_input = args.data
            elif args.file:
                with open(args.file) as f:
                    json_input = f.read()
            else:
                # Read from stdin
                json_input = sys.stdin.read()

            result = cli.bulk_create(json_input, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-update-json":
            # Get JSON input from file, data arg, or stdin
            json_input = None
            if args.data:
                json_input = args.data
            elif args.file:
                with open(args.file) as f:
                    json_input = f.read()
            else:
                # Read from stdin
                json_input = sys.stdin.read()

            result = cli.bulk_update_json(json_input, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-close":
            # Get JSON input from file, data arg, or stdin
            json_input = None
            if args.data:
                json_input = args.data
            elif args.file:
                with open(args.file) as f:
                    json_input = f.read()
            else:
                # Read from stdin
                json_input = sys.stdin.read()

            result = cli.bulk_close(json_input, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "comment":
            result = cli.add_comment(args.issue_id, args.text, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "list-comments":
            result = cli.list_comments(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "delete-comment":
            result = cli.delete_comment(args.comment_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "context":
            result = cli.get_issue_context(
                args.issue_id,
                as_json=args.json,
                compact=args.compact,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "block":
            result = cli.block_issue(
                issue_id=args.issue_id,
                blocker_id=args.blocker_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "unblock":
            result = cli.unblock_issue(
                issue_id=args.issue_id,
                blocker_id=args.blocker_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "deps":
            result = cli.show_dependencies(
                issue_id=args.issue_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "blocked":
            result = cli.list_blocked_issues(
                status=args.status,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "workspace":
            result = cli.workspace_status(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "start":
            result = cli.start_issue_workspace(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "stop":
            result = cli.stop_issue_workspace(close=args.close, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "active":
            result = cli.get_active_issue_workspace(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "web":
            from issuedb.web import run_server

            run_server(host=args.host, port=args.port, debug=args.debug)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
