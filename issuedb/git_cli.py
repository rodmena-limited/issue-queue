"""Git integration CLI methods for IssueDB."""

import json
from typing import Any, Optional

from issuedb.git_repository import GitLinkRepository
from issuedb.git_utils import (
    GitError,
    get_current_branch,
    get_recent_commits,
    is_git_repo,
)


class GitCLI:
    """Git integration CLI handler."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize Git CLI with repository.

        Args:
            db_path: Optional path to database file.
        """
        self.repo = GitLinkRepository(db_path)

    def format_output(self, data: Any, as_json: bool = False) -> str:
        """Format output for display.

        Args:
            data: Data to format.
            as_json: If True, output as JSON.

        Returns:
            Formatted string output.
        """
        if as_json:
            if isinstance(data, dict):
                return json.dumps(data, indent=2)
            elif isinstance(data, list):
                if all(hasattr(item, "to_dict") for item in data):
                    return json.dumps([item.to_dict() for item in data], indent=2)
                return json.dumps(data, indent=2)
            return json.dumps(data, indent=2)
        else:
            if isinstance(data, dict):
                lines = []
                for key, value in data.items():
                    formatted_key = key.replace("_", " ").title()
                    if isinstance(value, (list, dict)):
                        lines.append(f"{formatted_key}:")
                        lines.append(json.dumps(value, indent=2))
                    else:
                        lines.append(f"{formatted_key}: {value}")
                return "\n".join(lines)
            return str(data)

    def link_commit(self, issue_id: int, commit_hash: str, as_json: bool = False) -> str:
        """Link an issue to a git commit.

        Args:
            issue_id: Issue ID.
            commit_hash: Git commit hash.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If issue not found or link already exists.
        """
        link = self.repo.add_link(issue_id, "commit", commit_hash)
        if not link:
            raise ValueError(f"Issue {issue_id} not found")

        result = {
            "message": f"Linked issue {issue_id} to commit {commit_hash}",
            "link": link.to_dict(),
        }
        return self.format_output(result, as_json)

    def link_branch(self, issue_id: int, branch_name: str, as_json: bool = False) -> str:
        """Link an issue to a git branch.

        Args:
            issue_id: Issue ID.
            branch_name: Git branch name.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If issue not found or link already exists.
        """
        link = self.repo.add_link(issue_id, "branch", branch_name)
        if not link:
            raise ValueError(f"Issue {issue_id} not found")

        result = {
            "message": f"Linked issue {issue_id} to branch {branch_name}",
            "link": link.to_dict(),
        }
        return self.format_output(result, as_json)

    def unlink(
        self,
        issue_id: int,
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Remove git links from an issue.

        Args:
            issue_id: Issue ID.
            commit_hash: Optional commit hash to unlink.
            branch_name: Optional branch name to unlink.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If neither commit nor branch is specified.
        """
        if commit_hash:
            count = self.repo.remove_link(issue_id, link_type="commit", reference=commit_hash)
        elif branch_name:
            count = self.repo.remove_link(issue_id, link_type="branch", reference=branch_name)
        else:
            raise ValueError("Must specify either --commit or --branch")

        result = {
            "message": f"Removed {count} link(s) from issue {issue_id}",
            "count": count,
        }
        return self.format_output(result, as_json)

    def list_links(self, issue_id: int, as_json: bool = False) -> str:
        """List all git links for an issue.

        Args:
            issue_id: Issue ID.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        links = self.repo.get_links(issue_id)

        if as_json:
            return json.dumps([link.to_dict() for link in links], indent=2)
        else:
            if not links:
                return f"No git links found for issue {issue_id}."

            lines = []
            for link in links:
                lines.append("-" * 50)
                lines.append(f"Link ID: {link.id}")
                lines.append(f"Type: {link.link_type}")
                lines.append(f"Reference: {link.reference}")
                lines.append(f"Created: {link.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            return "\n".join(lines)

    def find_linked_issues(
        self,
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Find issues linked to a commit or branch.

        Args:
            commit_hash: Optional commit hash.
            branch_name: Optional branch name.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If neither commit nor branch is specified.
        """
        if commit_hash:
            issues = self.repo.get_issues_by_link(link_type="commit", reference=commit_hash)
        elif branch_name:
            issues = self.repo.get_issues_by_link(link_type="branch", reference=branch_name)
        else:
            raise ValueError("Must specify either --commit or --branch")

        if as_json:
            return json.dumps([issue.to_dict() for issue in issues], indent=2)
        else:
            if not issues:
                return "No issues found."

            lines = []
            for issue in issues:
                lines.append("-" * 50)
                lines.append(f"ID: {issue.id}")
                lines.append(f"Title: {issue.title}")
                lines.append(f"Status: {issue.status.value}")
                lines.append(f"Priority: {issue.priority.value}")

            return "\n".join(lines)

    def git_scan(
        self, num_commits: int = 10, auto_close: bool = False, as_json: bool = False
    ) -> str:
        """Scan recent git commits for issue references and link them.

        Args:
            num_commits: Number of recent commits to scan (default: 10).
            auto_close: If True, auto-close issues with 'fixes #N' or 'closes #N' patterns.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            GitError: If not in a git repository.
        """
        if not is_git_repo():
            raise GitError("Not in a git repository. Run this command from a git repository.")

        # Get recent commits
        commits = get_recent_commits(num_commits)

        # Scan commits and create links
        result = self.repo.scan_commits_and_close_issues(commits, auto_close=auto_close)

        if as_json:
            return json.dumps(result, indent=2)
        else:
            lines = [
                f"Scanned {result['scanned']} commit(s)",
                f"Created {result['links_created']} link(s)",
            ]
            if auto_close:
                lines.append(f"Closed {result['issues_closed']} issue(s)")

            if result["details"]:
                lines.append("\nDetails:")
                for detail in result["details"]:
                    commit = detail.get("commit", "")[:8]  # Short hash
                    issue_id = detail.get("issue_id", "")
                    action = detail.get("action", "")
                    reason = detail.get("reason", "")

                    line = f"  - Commit {commit}, Issue #{issue_id}: {action}"
                    if reason:
                        line += f" ({reason})"
                    lines.append(line)

            return "\n".join(lines)

    def git_status(self, as_json: bool = False) -> str:
        """Show git repository status (current branch, repo check).

        Args:
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        result: dict[str, Any] = {
            "is_git_repo": is_git_repo(),
            "current_branch": None,
        }

        if result["is_git_repo"]:
            try:
                result["current_branch"] = get_current_branch()
            except GitError as e:
                result["error"] = str(e)

        return self.format_output(result, as_json)
