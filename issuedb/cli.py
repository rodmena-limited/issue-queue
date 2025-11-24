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
            f"Project: {issue.project}",
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
        project: str,
        description: Optional[str] = None,
        priority: str = "medium",
        status: str = "open",
        as_json: bool = False,
    ) -> str:
        """Create a new issue.

        Args:
            title: Issue title.
            project: Project name.
            description: Optional description.
            priority: Priority level.
            status: Initial status.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issue = Issue(
            title=title,
            project=project,
            description=description,
            priority=Priority.from_string(priority),
            status=Status.from_string(status),
        )

        created_issue = self.repo.create_issue(issue)
        return self.format_output(created_issue, as_json)

    def list_issues(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None,
        as_json: bool = False,
    ) -> str:
        """List issues with filters.

        Args:
            project: Filter by project.
            status: Filter by status.
            priority: Filter by priority.
            limit: Maximum number of issues.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issues = self.repo.list_issues(
            project=project, status=status, priority=priority, limit=limit
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

    def update_issue(self, issue_id: int, as_json: bool = False, **updates) -> str:
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
        filter_project: Optional[str] = None,
        filter_status: Optional[str] = None,
        filter_priority: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Bulk update issues matching filters.

        Args:
            new_status: New status to set.
            new_priority: New priority to set.
            filter_project: Filter by project name.
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
            filter_project=filter_project,
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
        self, project: Optional[str] = None, status: Optional[str] = None, as_json: bool = False
    ) -> str:
        """Get next issue to work on.

        Args:
            project: Filter by project.
            status: Filter by status.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issue = self.repo.get_next_issue(project=project, status=status)
        if not issue:
            result = {"message": "No issues found matching criteria"}
            return self.format_output(result, as_json)
        return self.format_output(issue, as_json)

    def search_issues(
        self,
        keyword: str,
        project: Optional[str] = None,
        limit: Optional[int] = None,
        as_json: bool = False,
    ) -> str:
        """Search issues by keyword.

        Args:
            keyword: Search keyword.
            project: Filter by project.
            limit: Maximum results.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        issues = self.repo.search_issues(keyword=keyword, project=project, limit=limit)
        return self.format_output(issues, as_json)

    def clear_project(self, project: str, confirm: bool = False, as_json: bool = False) -> str:
        """Clear all issues for a project.

        Args:
            project: Project name.
            confirm: Safety confirmation.
            as_json: Output as JSON.

        Returns:
            Formatted output.

        Raises:
            ValueError: If not confirmed.
        """
        if not confirm:
            raise ValueError("Must use --confirm flag to clear project")

        count = self.repo.clear_project(project)
        result = {"message": f"Cleared {count} issues from project {project}"}
        return self.format_output(result, as_json)

    def get_audit_logs(
        self,
        issue_id: Optional[int] = None,
        project: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Get audit logs.

        Args:
            issue_id: Filter by issue ID.
            project: Filter by project.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        logs = self.repo.get_audit_logs(issue_id=issue_id, project=project)

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
                lines.append(f"Project: {log.project}")
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

    def get_summary(self, project: Optional[str] = None, as_json: bool = False) -> str:
        """Get summary statistics of issues.

        Args:
            project: Optional project name to filter by.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        summary = self.repo.get_summary(project=project)
        return self.format_output(summary, as_json)

    def get_report(
        self,
        project: Optional[str] = None,
        group_by: str = "status",
        as_json: bool = False,
    ) -> str:
        """Get detailed report of issues.

        Args:
            project: Optional project name to filter by.
            group_by: Group by 'status' or 'priority'.
            as_json: Output as JSON.

        Returns:
            Formatted output.
        """
        report = self.repo.get_report(project=project, group_by=group_by)
        return self.format_output(report, as_json)


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
    create_parser.add_argument("-p", "--project", required=True, help="Project name")
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
    list_parser.add_argument("-p", "--project", help="Filter by project")
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
    update_parser.add_argument("-p", "--project", help="New project")
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
        "-p", "--project", help="Filter by project name"
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
    next_parser.add_argument("-p", "--project", help="Filter by project")
    next_parser.add_argument("-s", "--status", help="Filter by status (defaults to 'open')")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search issues by keyword")
    search_parser.add_argument("-k", "--keyword", required=True, help="Search keyword")
    search_parser.add_argument("-p", "--project", help="Filter by project")
    search_parser.add_argument("-l", "--limit", type=int, help="Maximum results")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all issues for a project")
    clear_parser.add_argument("-p", "--project", required=True, help="Project name")
    clear_parser.add_argument("--confirm", action="store_true", help="Confirm deletion (required)")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="View audit logs")
    audit_parser.add_argument("-i", "--issue", type=int, help="Filter by issue ID")
    audit_parser.add_argument("-p", "--project", help="Filter by project")

    # Info command
    subparsers.add_parser("info", help="Get database information")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Get summary statistics of issues")
    summary_parser.add_argument("-p", "--project", help="Filter by project")

    # Report command
    report_parser = subparsers.add_parser("report", help="Get detailed report of issues")
    report_parser.add_argument("-p", "--project", help="Filter by project")
    report_parser.add_argument(
        "--group-by",
        choices=["status", "priority"],
        default="status",
        help="Group issues by status or priority (default: status)",
    )

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
                project=args.project,
                description=args.description,
                priority=args.priority,
                status=args.status,
                as_json=args.json,
            )
            print(result)

        elif args.command == "list":
            result = cli.list_issues(
                project=args.project,
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
            if args.project:
                updates["project"] = args.project
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
                filter_project=args.project,
                filter_status=args.filter_status,
                filter_priority=args.filter_priority,
                as_json=args.json,
            )
            print(result)

        elif args.command == "delete":
            result = cli.delete_issue(args.id, as_json=args.json)
            print(result)

        elif args.command == "get-next":
            result = cli.get_next_issue(project=args.project, status=args.status, as_json=args.json)
            print(result)

        elif args.command == "search":
            result = cli.search_issues(
                keyword=args.keyword,
                project=args.project,
                limit=args.limit,
                as_json=args.json,
            )
            print(result)

        elif args.command == "clear":
            result = cli.clear_project(
                project=args.project, confirm=args.confirm, as_json=args.json
            )
            print(result)

        elif args.command == "audit":
            result = cli.get_audit_logs(
                issue_id=args.issue, project=args.project, as_json=args.json
            )
            print(result)

        elif args.command == "info":
            result = cli.get_info(as_json=args.json)
            print(result)

        elif args.command == "summary":
            result = cli.get_summary(project=args.project, as_json=args.json)
            print(result)

        elif args.command == "report":
            result = cli.get_report(
                project=args.project, group_by=args.group_by, as_json=args.json
            )
            print(result)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
