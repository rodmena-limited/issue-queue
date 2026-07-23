"""IssueRepository assembled from feature submodules (mechanical split)."""
from __future__ import annotations

from issuedb.database import get_database
from issuedb.repository import (
    _base,
    _bulk,
    _code_refs,
    _comments,
    _dependencies,
    _issues,
    _lessons,
    _links,
    _memory,
    _query,
    _reports,
    _search,
    _tags,
    _templates,
    _time_tracking,
    _workspace,
)


class IssueRepository:
    """Handles all issue-related database operations."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize repository with database connection.

        Args:
            db_path: Optional path to database file.
        """
        self.db = get_database(db_path)

    # _base
    _log_audit = _base._log_audit
    _row_to_issue = _base._row_to_issue
    get_issue = _base.get_issue
    _get_issue_with_conn = _base._get_issue_with_conn
    _get_issue_tags_with_conn = _base._get_issue_tags_with_conn

    # _issues
    create_issue = _issues.create_issue
    update_issue = _issues.update_issue
    bulk_update_issues = _issues.bulk_update_issues
    delete_issue = _issues.delete_issue
    get_next_issue = _issues.get_next_issue

    # _query
    count_issues = _query.count_issues
    list_issues = _query.list_issues
    get_all_issues = _query.get_all_issues
    search_issues = _query.search_issues
    clear_all_issues = _query.clear_all_issues

    # _reports
    get_audit_logs = _reports.get_audit_logs
    get_last_fetched = _reports.get_last_fetched
    get_summary = _reports.get_summary
    get_report = _reports.get_report

    # _bulk
    bulk_create_issues = _bulk.bulk_create_issues
    bulk_update_issues_from_json = _bulk.bulk_update_issues_from_json
    bulk_close_issues = _bulk.bulk_close_issues
    find_by_pattern = _bulk.find_by_pattern
    bulk_close_by_pattern = _bulk.bulk_close_by_pattern
    bulk_update_by_pattern = _bulk.bulk_update_by_pattern
    bulk_delete_by_pattern = _bulk.bulk_delete_by_pattern

    # _comments
    add_comment = _comments.add_comment
    get_comments = _comments.get_comments
    delete_comment = _comments.delete_comment

    # _code_refs
    parse_file_spec = _code_refs.parse_file_spec
    add_code_reference = _code_refs.add_code_reference
    remove_code_reference = _code_refs.remove_code_reference
    get_code_references = _code_refs.get_code_references
    get_issues_by_file = _code_refs.get_issues_by_file

    # _dependencies
    add_dependency = _dependencies.add_dependency
    remove_dependency = _dependencies.remove_dependency
    get_blockers = _dependencies.get_blockers
    get_blocking = _dependencies.get_blocking
    is_blocked = _dependencies.is_blocked
    get_all_blocked_issues = _dependencies.get_all_blocked_issues
    _would_create_cycle = _dependencies._would_create_cycle
    _would_create_cycle_with_conn = _dependencies._would_create_cycle_with_conn

    # _search
    search_issues_advanced = _search.search_issues_advanced
    save_search = _search.save_search
    get_saved_search = _search.get_saved_search
    list_saved_searches = _search.list_saved_searches
    delete_saved_search = _search.delete_saved_search
    run_saved_search = _search.run_saved_search

    # _workspace
    get_active_issue = _workspace.get_active_issue
    _set_status_with_conn = _workspace._set_status_with_conn
    start_issue = _workspace.start_issue
    stop_issue = _workspace.stop_issue
    get_workspace_status = _workspace.get_workspace_status

    # _time_tracking
    start_timer = _time_tracking.start_timer
    stop_timer = _time_tracking.stop_timer
    stop_all_timers = _time_tracking.stop_all_timers
    get_running_timers = _time_tracking.get_running_timers
    get_time_entries = _time_tracking.get_time_entries
    set_estimate = _time_tracking.set_estimate
    get_time_report = _time_tracking.get_time_report

    # _templates
    create_template = _templates.create_template
    get_template = _templates.get_template
    list_templates = _templates.list_templates
    delete_template = _templates.delete_template
    validate_against_template = _templates.validate_against_template
    _row_to_template = _templates._row_to_template

    # _memory
    add_memory = _memory.add_memory
    update_memory = _memory.update_memory
    delete_memory = _memory.delete_memory
    get_memory = _memory.get_memory
    list_memory = _memory.list_memory

    # _lessons
    add_lesson = _lessons.add_lesson
    update_lesson = _lessons.update_lesson
    delete_lesson = _lessons.delete_lesson
    get_lesson = _lessons.get_lesson
    list_lessons = _lessons.list_lessons

    # _tags
    create_tag = _tags.create_tag
    list_tags = _tags.list_tags
    add_issue_tag = _tags.add_issue_tag
    remove_issue_tag = _tags.remove_issue_tag
    get_issue_tags = _tags.get_issue_tags
    get_tags_for_issues = _tags.get_tags_for_issues

    # _links
    link_issues = _links.link_issues
    unlink_issues = _links.unlink_issues
    get_issue_relations = _links.get_issue_relations

__all__ = ["IssueRepository"]
