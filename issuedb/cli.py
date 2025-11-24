"""Command-line interface for IssueDB."""

import argparse
import json
import sys
from typing import Any, Optional

from issuedb.models import Issue, Priority, Status
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

        if issue.description:
            lines.append(f"Description: {issue.description}")

        lines.extend(
            [
                f"Created: {issue.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Updated: {issue.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            ]
        )

        return "\n".join(lines)

    def _format_dict(self, data: dict) -> str:
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
        as_json: bool = False,
    ) -> str:
        """Create a new issue.

        Args:
            title: Issue title.
            description: Optional description.
            priority: Priority level.
            status: Initial status.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issue = Issue(
            title=title,
            description=description,
            priority=Priority.from_string(priority),
            status=Status.from_string(status),
        )

        created_issue = self.repo.create_issue(issue)
        return self.format_output(created_issue, as_json)

    def list_issues(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None,
        as_json: bool = False,
    ) -> str:
        """List issues with filters.

        Args:
            status: Filter by status.
            priority: Filter by priority.
            limit: Maximum number of issues.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issues = self.repo.list_issues(
            status=status, priority=priority, limit=limit
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
            **updates: Fields to update.

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

    def get_next_issue(
        self, status: Optional[str] = None, as_json: bool = False
    ) -> str:
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
        "--ollama",
        type=str,
        metavar="REQUEST",
        help="Natural language request to generate and execute issuedb-cli command via Ollama",
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
        choices=["open", "in-progress", "closed"],
        default="open",
        help="Initial status",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List issues")
    list_parser.add_argument("-s", "--status", help="Filter by status (open, in-progress, closed)")
    list_parser.add_argument("--priority", help="Filter by priority (low, medium, high, critical)")
    list_parser.add_argument("-l", "--limit", type=int, help="Maximum number of issues")

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
        choices=["open", "in-progress", "closed"],
        help="New status",
    )

    # Bulk-update command
    bulk_update_parser = subparsers.add_parser(
        "bulk-update", help="Bulk update issues matching filters"
    )
    bulk_update_parser.add_argument(
        "--filter-status",
        choices=["open", "in-progress", "closed"],
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
        choices=["open", "in-progress", "closed"],
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

    args = parser.parse_args()

    # Handle --prompt flag
    if args.prompt:
        from pathlib import Path

        # Get the prompt file path
        package_dir = Path(__file__).parent
        prompt_file = package_dir / "data" / "agents" / "PROMPT.txt"

        if prompt_file.exists():
            print(prompt_file.read_text())
        else:
            print(f"Error: Prompt file not found at {prompt_file}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Handle --ollama flag
    if args.ollama:
        from pathlib import Path

        from issuedb.ollama_client import handle_ollama_request

        # Get the prompt file path
        package_dir = Path(__file__).parent
        prompt_file = package_dir / "data" / "agents" / "PROMPT.txt"

        if not prompt_file.exists():
            print(f"Error: Prompt file not found at {prompt_file}", file=sys.stderr)
            sys.exit(1)

        prompt_text = prompt_file.read_text()

        # Handle Ollama request
        exit_code = handle_ollama_request(
            user_request=args.ollama,
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
                as_json=args.json,
            )
            print(result)

        elif args.command == "list":
            result = cli.list_issues(
                status=args.status,
                priority=args.priority,
                limit=args.limit,
                as_json=args.json,
            )
            print(result)

        elif args.command == "get":
            result = cli.get_issue(args.id, as_json=args.json)
            print(result)

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

            if not updates:
                print("Error: No updates specified", file=sys.stderr)
                sys.exit(1)

            result = cli.update_issue(args.id, as_json=args.json, **updates)
            print(result)

        elif args.command == "bulk-update":
            if not args.status and not args.priority:
                print("Error: No updates specified (use -s or --priority)", file=sys.stderr)
                sys.exit(1)

            result = cli.bulk_update_issues(
                new_status=args.status,
                new_priority=args.priority,
                filter_status=args.filter_status,
                filter_priority=args.filter_priority,
                as_json=args.json,
            )
            print(result)

        elif args.command == "delete":
            result = cli.delete_issue(args.id, as_json=args.json)
            print(result)

        elif args.command == "get-next":
            result = cli.get_next_issue(status=args.status, as_json=args.json)
            print(result)

        elif args.command == "search":
            result = cli.search_issues(
                keyword=args.keyword,
                limit=args.limit,
                as_json=args.json,
            )
            print(result)

        elif args.command == "clear":
            result = cli.clear_all(confirm=args.confirm, as_json=args.json)
            print(result)

        elif args.command == "audit":
            result = cli.get_audit_logs(issue_id=args.issue, as_json=args.json)
            print(result)

        elif args.command == "info":
            result = cli.get_info(as_json=args.json)
            print(result)

        elif args.command == "summary":
            result = cli.get_summary(as_json=args.json)
            print(result)

        elif args.command == "report":
            result = cli.get_report(group_by=args.group_by, as_json=args.json)
            print(result)

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
            print(result)

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
            print(result)

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
            print(result)

        elif args.command == "comment":
            result = cli.add_comment(args.issue_id, args.text, as_json=args.json)
            print(result)

        elif args.command == "list-comments":
            result = cli.list_comments(args.issue_id, as_json=args.json)
            print(result)

        elif args.command == "delete-comment":
            result = cli.delete_comment(args.comment_id, as_json=args.json)
            print(result)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
