"""HTML page and form-post routes."""

import contextlib
import os
from typing import Any, Optional, Union

from flask import redirect, render_template_string, request, url_for
from werkzeug.wrappers import Response

from issuedb.models import Issue, Priority, Status
from issuedb.web._app import app, get_repo
from issuedb.web._detail import ISSUE_DETAIL_TEMPLATE
from issuedb.web._pages import DASHBOARD_TEMPLATE, LESSONS_TEMPLATE, MEMORY_TEMPLATE
from issuedb.web._pages2 import (
    AUDIT_LOG_TEMPLATE,
    ISSUE_FORM_TEMPLATE,
    ISSUES_LIST_TEMPLATE,
)


@app.route("/")
def dashboard() -> str:
    """Dashboard page with summary statistics."""
    repo = get_repo()
    summary = repo.get_summary()
    next_issue = repo.get_next_issue(log_fetch=False)
    recent_issues = repo.list_issues(limit=5)

    active = repo.get_active_issue()
    active_issue = None
    active_started = None
    if active:
        active_issue, started_at = active
        active_started = started_at.strftime("%Y-%m-%d %H:%M")

    return render_template_string(
        DASHBOARD_TEMPLATE,
        active_page="dashboard",
        summary=summary,
        next_issue=next_issue,
        active_issue=active_issue,
        active_started=active_started,
        recent_issues=recent_issues,
    )


@app.route("/issues")
def issues_list() -> str:
    """Issues list page."""
    repo = get_repo()
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    search_query = request.args.get("q")
    tag_filter = request.args.get("tag")
    due_date_filter = request.args.get("due_date")

    # Pagination
    page = request.args.get("page", 1, type=int)
    limit = 20
    offset = (page - 1) * limit

    # Keyword search combines with the other filters (and matches
    # count_issues below), so filtered searches paginate correctly.
    issues = repo.list_issues(
        status=status_filter,
        priority=priority_filter,
        due_date=due_date_filter,
        tag=tag_filter,
        keyword=search_query,
        limit=limit,
        offset=offset,
    )

    total_issues = repo.count_issues(
        status=status_filter,
        priority=priority_filter,
        due_date=due_date_filter,
        tag=tag_filter,
        keyword=search_query,
    )

    import math

    total_pages = math.ceil(total_issues / limit) if total_issues else 0

    return render_template_string(
        ISSUES_LIST_TEMPLATE,
        active_page="issues",
        issues=issues,
        status_filter=status_filter,
        priority_filter=priority_filter,
        search_query=search_query,
        tag_filter=tag_filter,
        page=page,
        total_pages=total_pages,
        total_issues=total_issues,
        message=request.args.get("message"),
    )


def _link_related_issues(repo: Any, issue_id: int, raw: Optional[str]) -> list[str]:
    """Link comma-separated issue IDs as 'related'; return failure notes."""
    failures = []
    for part in (raw or "").split(","):
        token = part.strip().lstrip("#")
        if not token:
            continue
        if not token.isdigit():
            failures.append(f"invalid issue ID {part.strip()!r}")
            continue
        try:
            repo.link_issues(issue_id, int(token), "related")
        except ValueError as e:
            failures.append(f"#{token}: {e}")
    return failures


@app.route("/issues/new", methods=["GET", "POST"])
def create_issue() -> Union[str, Response]:
    """Create a new issue."""
    repo = get_repo()

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        priority = request.form.get("priority", "medium")
        status = request.form.get("status", "open")
        due_date = request.form.get("due_date")
        tags_str = request.form.get("tags")

        if not title:
            return render_template_string(
                ISSUE_FORM_TEMPLATE,
                title="New Issue",
                issue=None,
                error="Title is required",
            )

        due_date_obj = None
        if due_date:
            try:
                from datetime import datetime

                due_date_obj = datetime.fromisoformat(due_date)
            except ValueError:
                return render_template_string(
                    ISSUE_FORM_TEMPLATE,
                    title="New Issue",
                    issue=None,
                    error="Invalid due date (use YYYY-MM-DD)",
                )

        issue = Issue(
            title=title,
            description=description,
            priority=Priority.from_string(priority),
            status=Status.from_string(status),
            due_date=due_date_obj,
        )

        created = repo.create_issue(issue)
        assert created.id is not None  # ID is always assigned after creation

        if tags_str:
            for tag in tags_str.split(","):
                if tag_name := tag.strip():
                    repo.add_issue_tag(created.id, tag_name)

        # The form documents this field as linking the new issue as 'related'.
        failures = _link_related_issues(repo, created.id, request.form.get("related_issues"))
        if failures:
            return redirect(
                url_for(
                    "issue_detail",
                    issue_id=created.id,
                    error="Could not link related issues: " + "; ".join(failures),
                )
            )

        return redirect(url_for("issue_detail", issue_id=created.id))

    return render_template_string(
        ISSUE_FORM_TEMPLATE,
        title="New Issue",
        issue=None,
        error=request.args.get("error"),
    )


@app.route("/issues/<int:issue_id>")
def issue_detail(issue_id: int) -> Union[str, Response]:
    """Issue detail page - loads basic info, async fetches the rest."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return redirect(url_for("issues_list", message="Issue not found"))

    # Only load basic issue info - everything else loads async via JS
    return render_template_string(
        ISSUE_DETAIL_TEMPLATE,
        active_page="issues",
        issue=issue,
        message=request.args.get("message"),
        error=request.args.get("error"),
    )


@app.route("/issues/<int:issue_id>/edit", methods=["GET", "POST"])
def edit_issue(issue_id: int) -> Union[str, Response]:
    """Edit an issue."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return redirect(url_for("issues_list", message="Issue not found"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        priority = request.form.get("priority")
        status = request.form.get("status")
        due_date = request.form.get("due_date")
        tags_str = request.form.get("tags")

        if not title:
            return render_template_string(
                ISSUE_FORM_TEMPLATE,
                title="Edit Issue",
                issue=issue,
                error="Title is required",
            )

        repo.update_issue(
            issue_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
        )

        # Handle tags
        current_tags = {t.name for t in repo.get_issue_tags(issue_id)}
        new_tags = set()
        if tags_str:
            new_tags = {t.strip() for t in tags_str.split(",") if t.strip()}

        for tag in new_tags - current_tags:
            repo.add_issue_tag(issue_id, tag)

        for tag in current_tags - new_tags:
            repo.remove_issue_tag(issue_id, tag)

        failures = _link_related_issues(repo, issue_id, request.form.get("related_issues"))
        if failures:
            return redirect(
                url_for(
                    "issue_detail",
                    issue_id=issue_id,
                    error="Could not link related issues: " + "; ".join(failures),
                )
            )

        return redirect(url_for("issue_detail", issue_id=issue_id))

    return render_template_string(ISSUE_FORM_TEMPLATE, title="Edit Issue", issue=issue)


@app.route("/audit")
def audit_log_page() -> str:
    """Audit log page."""
    repo = get_repo()
    issue_filter = request.args.get("issue_id", type=int)
    logs = repo.get_audit_logs(issue_id=issue_filter)

    return render_template_string(
        AUDIT_LOG_TEMPLATE,
        active_page="audit",
        logs=logs[:100],  # Limit to 100 entries
        issue_filter=issue_filter,
    )


@app.route("/memory")
def memory_page() -> str:
    """Memory management page."""
    repo = get_repo()
    memories = repo.list_memory()
    return render_template_string(
        MEMORY_TEMPLATE,
        active_page="memory",
        memories=memories,
    )


@app.route("/favicon.svg")
def favicon() -> Response:
    """Serve favicon."""
    from flask import send_from_directory

    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.svg")


@app.route("/static/fonts/<path:filename>")
def serve_fonts(filename: str) -> Response:
    """Serve font files."""

    from flask import send_from_directory

    return send_from_directory(os.path.join(app.root_path, "static/fonts"), filename)


@app.route("/lessons")
def lessons_page() -> str:
    """Lessons learned page."""
    repo = get_repo()
    lessons = repo.list_lessons()
    return render_template_string(
        LESSONS_TEMPLATE,
        active_page="lessons",
        lessons=lessons,
    )


@app.route("/memory/add", methods=["POST"])
def memory_add() -> Any:
    """Form handler for adding memory."""
    repo = get_repo()

    try:
        key = request.form.get("key")
        value = request.form.get("value")
        category = request.form.get("category", "general")

        if not key or not value:
            return "Key and value required", 400

        repo.add_memory(key=key, value=value, category=category)
        return redirect(url_for("memory_page"))
    except Exception as e:
        return f"Error: {str(e)}", 400


@app.route("/memory/delete/<key>", methods=["POST"])
def memory_delete(key: str) -> Any:
    """Form handler for deleting memory."""
    repo = get_repo()
    repo.delete_memory(key)
    return redirect(url_for("memory_page"))


@app.route("/lessons/add", methods=["POST"])
def add_lesson() -> Response:
    """Add a lesson learned."""
    repo = get_repo()
    lesson = request.form.get("lesson")
    category = request.form.get("category", "general")
    issue_id_str = request.form.get("issue_id")

    if not lesson:
        return redirect(url_for("lessons_page"))

    issue_id = None
    if issue_id_str:
        with contextlib.suppress(ValueError):
            issue_id = int(issue_id_str)

    repo.add_lesson(lesson=lesson, category=category, issue_id=issue_id)
    return redirect(url_for("lessons_page"))


@app.route("/lessons/delete/<int:lesson_id>", methods=["POST"])
def delete_lesson(lesson_id: int) -> Response:
    """Delete a lesson learned."""
    repo = get_repo()
    repo.delete_lesson(lesson_id)
    return redirect(url_for("lessons_page"))
