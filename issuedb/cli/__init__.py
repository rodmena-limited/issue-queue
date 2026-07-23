"""Command-line interface for IssueDB."""

from __future__ import annotations

from issuedb.cli import (
    _bulk,
    _code_refs,
    _comments,
    _context,
    _dependencies,
    _format,
    _issues,
    _lessons,
    _links,
    _memory,
    _reports,
    _similarity,
    _tags,
    _time_tracking,
    _workspace,
)
from issuedb.repository import IssueRepository


class CLI:
    """Command-line interface handler."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize CLI with repository.

        Args:
            db_path: Optional path to database file.
        """
        self.repo = IssueRepository(db_path)

    # Output formatting
    format_output = _format.format_output
    _format_issue = _format._format_issue
    _format_dict = _format._format_dict

    # Core issue CRUD
    create_issue = _issues.create_issue
    list_templates = _issues.list_templates
    list_issues = _issues.list_issues
    get_issue = _issues.get_issue
    update_issue = _issues.update_issue
    bulk_update_issues = _issues.bulk_update_issues
    delete_issue = _issues.delete_issue
    get_next_issue = _issues.get_next_issue
    search_issues = _issues.search_issues
    clear_all = _issues.clear_all
    get_last_fetched = _issues.get_last_fetched

    # Reports
    get_audit_logs = _reports.get_audit_logs
    get_info = _reports.get_info
    get_summary = _reports.get_summary
    get_report = _reports.get_report

    # Bulk JSON and pattern
    bulk_create = _bulk.bulk_create
    bulk_update_json = _bulk.bulk_update_json
    bulk_close = _bulk.bulk_close
    bulk_close_pattern = _bulk.bulk_close_pattern
    bulk_update_pattern = _bulk.bulk_update_pattern
    bulk_delete_pattern = _bulk.bulk_delete_pattern

    # Comments
    add_comment = _comments.add_comment
    list_comments = _comments.list_comments
    delete_comment = _comments.delete_comment

    # Context
    get_issue_context = _context.get_issue_context
    _get_git_info = _context._get_git_info
    _generate_suggested_actions = _context._generate_suggested_actions
    _format_issue_context = _context._format_issue_context

    # Memory
    memory_add = _memory.memory_add
    memory_list = _memory.memory_list
    memory_update = _memory.memory_update
    memory_delete = _memory.memory_delete

    # Lessons
    lesson_add = _lessons.lesson_add
    lesson_list = _lessons.lesson_list

    # Tags
    tag_issue = _tags.tag_issue
    untag_issue = _tags.untag_issue
    tag_list = _tags.tag_list

    # Links
    link_issues = _links.link_issues
    unlink_issues = _links.unlink_issues

    # Workspace
    workspace_status = _workspace.workspace_status
    start_issue_workspace = _workspace.start_issue_workspace
    stop_issue_workspace = _workspace.stop_issue_workspace
    get_active_issue_workspace = _workspace.get_active_issue_workspace

    # Time tracking
    timer_start = _time_tracking.timer_start
    timer_stop = _time_tracking.timer_stop
    timer_status = _time_tracking.timer_status
    set_estimate = _time_tracking.set_estimate
    time_log = _time_tracking.time_log
    time_report = _time_tracking.time_report

    # Dependencies
    block_issue = _dependencies.block_issue
    unblock_issue = _dependencies.unblock_issue
    show_dependencies = _dependencies.show_dependencies
    list_blocked_issues = _dependencies.list_blocked_issues

    # Code references
    attach_code_reference = _code_refs.attach_code_reference
    detach_code_reference = _code_refs.detach_code_reference
    list_code_references = _code_refs.list_code_references
    list_affected_issues = _code_refs.list_affected_issues

    # Similarity
    find_similar_issues = _similarity.find_similar_issues
    find_duplicates = _similarity.find_duplicates


from issuedb.cli._main import main  # noqa: E402  (imported last to avoid import cycle)

__all__ = ["CLI", "main"]
