"""Argument parser construction for the CLI."""

from __future__ import annotations

import argparse

from issuedb.cli._parser_extra import register_advanced


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all subcommands."""
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

    register_core(subparsers)
    register_advanced(subparsers)

    return parser


def register_core(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register core issue/memory/lesson/tag/link subcommands."""
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
    create_parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        metavar="TAG",
        help="Tag to attach to the issue (repeatable, e.g. --tag bug --tag v1.0)",
    )

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
    bulk_update_parser.add_argument(
        "--all",
        action="store_true",
        help="Required to update ALL issues when no filter is given (safety guard)",
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
