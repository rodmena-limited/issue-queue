"""Advanced subcommand registration for the CLI argument parser."""

from __future__ import annotations

import argparse


def register_advanced(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register bulk-JSON/comment/context/workspace/time/refs/pattern/similarity subcommands."""
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
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1; use 0.0.0.0 to expose on the network)",
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

    # Time tracking commands
    timer_start_parser = subparsers.add_parser("timer-start", help="Start a timer for an issue")
    timer_start_parser.add_argument("issue_id", type=int, help="Issue ID")
    timer_start_parser.add_argument("-n", "--note", help="Optional note for this time entry")

    timer_stop_parser = subparsers.add_parser("timer-stop", help="Stop a running timer")
    timer_stop_parser.add_argument(
        "issue_id",
        type=int,
        nargs="?",
        help="Issue ID (stops all running timers if omitted)",
    )

    subparsers.add_parser("timer-status", help="Show running timers")

    estimate_parser = subparsers.add_parser("estimate", help="Set time estimate for an issue")
    estimate_parser.add_argument("issue_id", type=int, help="Issue ID")
    estimate_parser.add_argument("hours", type=float, help="Estimated hours")

    time_log_parser = subparsers.add_parser("time-log", help="Show time entries for an issue")
    time_log_parser.add_argument("issue_id", type=int, help="Issue ID")

    time_report_parser = subparsers.add_parser("time-report", help="Generate a time report")
    time_report_parser.add_argument(
        "--period",
        choices=["all", "week", "month"],
        default="all",
        help="Time period (default: all)",
    )
    time_report_parser.add_argument(
        "-i", "--issue", type=int, dest="issue_id", help="Filter by issue ID"
    )

    # Code reference commands
    attach_parser = subparsers.add_parser("attach", help="Attach a code reference to an issue")
    attach_parser.add_argument("issue_id", type=int, help="Issue ID")
    attach_parser.add_argument(
        "--file",
        required=True,
        dest="file_spec",
        help="File path with optional line(s), e.g. 'src/main.py:42' or 'src/main.py:10-20'",
    )
    attach_parser.add_argument("-n", "--note", help="Optional note about the reference")

    detach_parser = subparsers.add_parser("detach", help="Detach a code reference from an issue")
    detach_parser.add_argument("issue_id", type=int, help="Issue ID")
    detach_parser.add_argument(
        "--file", dest="file_path", help="File path to remove references for"
    )
    detach_parser.add_argument(
        "--reference-id", type=int, dest="reference_id", help="Specific reference ID to remove"
    )

    refs_parser = subparsers.add_parser("refs", help="List code references for an issue")
    refs_parser.add_argument("issue_id", type=int, help="Issue ID")

    affected_parser = subparsers.add_parser("affected", help="List issues referencing a file")
    affected_parser.add_argument("file_path", help="File path to search for")

    # Bulk pattern commands
    bulk_close_pattern_parser = subparsers.add_parser(
        "bulk-close-pattern", help="Close issues matching a title/description pattern"
    )
    bulk_close_pattern_parser.add_argument(
        "--title", dest="title_pattern", help="Pattern to match against title"
    )
    bulk_close_pattern_parser.add_argument(
        "--desc", dest="desc_pattern", help="Pattern to match against description"
    )
    bulk_close_pattern_parser.add_argument(
        "--regex", action="store_true", dest="use_regex", help="Use regex (default: glob)"
    )
    bulk_close_pattern_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without changing anything"
    )

    bulk_update_pattern_parser = subparsers.add_parser(
        "bulk-update-pattern", help="Update issues matching a title/description pattern"
    )
    bulk_update_pattern_parser.add_argument(
        "--title", dest="title_pattern", help="Pattern to match against title"
    )
    bulk_update_pattern_parser.add_argument(
        "--desc", dest="desc_pattern", help="Pattern to match against description"
    )
    bulk_update_pattern_parser.add_argument(
        "--regex", action="store_true", dest="use_regex", help="Use regex (default: glob)"
    )
    bulk_update_pattern_parser.add_argument(
        "-s", "--status", dest="new_status", help="New status to set"
    )
    bulk_update_pattern_parser.add_argument(
        "--priority", dest="new_priority", help="New priority to set"
    )
    bulk_update_pattern_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without changing anything"
    )

    bulk_delete_pattern_parser = subparsers.add_parser(
        "bulk-delete-pattern", help="Delete issues matching a title/description pattern"
    )
    bulk_delete_pattern_parser.add_argument(
        "--title", dest="title_pattern", help="Pattern to match against title"
    )
    bulk_delete_pattern_parser.add_argument(
        "--desc", dest="desc_pattern", help="Pattern to match against description"
    )
    bulk_delete_pattern_parser.add_argument(
        "--regex", action="store_true", dest="use_regex", help="Use regex (default: glob)"
    )
    bulk_delete_pattern_parser.add_argument(
        "--confirm", action="store_true", help="Confirm deletion (required unless --dry-run)"
    )
    bulk_delete_pattern_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without deleting"
    )

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

    # Dedupe command (find-duplicates is kept as an alias for the documented name)
    dedupe_parser = subparsers.add_parser(
        "dedupe", aliases=["find-duplicates"], help="Find potential duplicate issues"
    )
    dedupe_parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Similarity threshold for duplicates (0.0 to 1.0, default: 0.7)",
    )

    # Git integration commands ("git-" prefixed: plain `link` is taken by
    # issue-to-issue relations)
    git_link_parser = subparsers.add_parser(
        "git-link", help="Link an issue to a git commit or branch"
    )
    git_link_parser.add_argument("issue_id", type=int, help="Issue ID")
    git_link_group = git_link_parser.add_mutually_exclusive_group(required=True)
    git_link_group.add_argument("-c", "--commit", help="Commit hash to link")
    git_link_group.add_argument("-b", "--branch", help="Branch name to link")

    git_unlink_parser = subparsers.add_parser(
        "git-unlink", help="Remove git link(s) from an issue"
    )
    git_unlink_parser.add_argument("issue_id", type=int, help="Issue ID")
    git_unlink_group = git_unlink_parser.add_mutually_exclusive_group(required=True)
    git_unlink_group.add_argument("-c", "--commit", help="Commit hash to unlink")
    git_unlink_group.add_argument("-b", "--branch", help="Branch name to unlink")

    git_links_parser = subparsers.add_parser(
        "git-links", help="Show all git links for an issue"
    )
    git_links_parser.add_argument("issue_id", type=int, help="Issue ID")

    git_linked_parser = subparsers.add_parser(
        "git-linked", help="Show issues linked to a commit or branch"
    )
    git_linked_group = git_linked_parser.add_mutually_exclusive_group(required=True)
    git_linked_group.add_argument("-c", "--commit", help="Commit hash")
    git_linked_group.add_argument("-b", "--branch", help="Branch name")

    git_scan_parser = subparsers.add_parser(
        "git-scan",
        help="Scan recent git commits for issue references and link them",
    )
    git_scan_parser.add_argument(
        "-n",
        "--num-commits",
        type=int,
        default=10,
        help="Number of recent commits to scan (default: 10)",
    )
    git_scan_parser.add_argument(
        "--auto-close",
        action="store_true",
        help="Auto-close issues with 'fixes #N' or 'closes #N' patterns",
    )

    subparsers.add_parser("git-status", help="Show git repository status")
