"""JSON API routes (part 1)."""

from typing import Any

from flask import jsonify, redirect, request, url_for

from issuedb.models import Issue, Priority, Status
from issuedb.similarity import find_similar_issues
from issuedb.web._app import _issue_id_from_referer, app, get_repo


@app.route("/api/issues", methods=["GET"])
def api_list_issues() -> Any:
    """API: List issues."""
    repo = get_repo()

    status = request.args.get("status")
    priority = request.args.get("priority")
    limit = request.args.get("limit", type=int)

    issues = repo.list_issues(status=status, priority=priority, limit=limit)
    return jsonify([i.to_dict() for i in issues])


@app.route("/api/issues", methods=["POST"])
def api_create_issue() -> Any:
    """API: Create a new issue."""
    repo = get_repo()

    # Handle form data or JSON
    data = (request.get_json(silent=True) or {}) if request.is_json else request.form.to_dict()

    title = data.get("title", "").strip()
    if not title:
        if request.is_json:
            return jsonify({"error": "Title is required"}), 400
        return redirect(url_for("issue_new", error="Title is required"))

    description = data.get("description")
    priority = data.get("priority", "medium")
    status = data.get("status", "open")
    due_date = data.get("due_date")

    due_date_obj = None
    if due_date:
        try:
            from datetime import datetime

            due_date_obj = datetime.fromisoformat(due_date)
        except ValueError:
            pass

    issue = Issue(
        title=title,
        description=description,
        priority=Priority.from_string(priority),
        status=Status.from_string(status),
        due_date=due_date_obj,
    )

    created = repo.create_issue(issue)
    assert created.id is not None  # ID is always assigned after creation
    issue_id = created.id

    if "tags" in data:
        tags_str = data["tags"]
        for tag in tags_str.split(","):
            if tag_name := tag.strip():
                repo.add_issue_tag(issue_id, tag_name)

    if request.is_json:
        # Refetch to include tags
        refetched = repo.get_issue(issue_id)
        assert refetched is not None  # Issue was just created
        return jsonify(refetched.to_dict()), 201

    return redirect(url_for("issue_detail", issue_id=created.id))


@app.route("/api/issues/<int:issue_id>", methods=["GET"])
def api_get_issue(issue_id: int) -> Any:
    """API: Get issue by ID."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    return jsonify(issue.to_dict())


@app.route("/api/issues/<int:issue_id>", methods=["POST", "PUT", "PATCH"])
def api_update_issue(issue_id: int) -> Any:
    """API: Update an issue."""
    repo = get_repo()

    # Handle method override for HTML forms
    method = request.form.get("_method", request.method).upper()

    if method == "DELETE":
        return api_delete_issue(issue_id)

    # Handle form data or JSON
    if request.is_json:
        data = (request.get_json(silent=True) or {})
    else:
        data = request.form.to_dict()
        data.pop("_method", None)

    updates = {}
    if "title" in data and data["title"]:
        updates["title"] = data["title"]
    if "description" in data:
        updates["description"] = data["description"]
    if "priority" in data and data["priority"]:
        updates["priority"] = data["priority"]
    if "status" in data and data["status"]:
        updates["status"] = data["status"]
    if "due_date" in data:
        updates["due_date"] = data["due_date"]

    if not updates and "tags" not in data:
        if request.is_json:
            return jsonify({"error": "No updates provided"}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error="No updates provided"))

    if updates:
        repo.update_issue(issue_id, **updates)

    # Handle tags
    if "tags" in data:
        tags_str = data["tags"]
        current_tags = {t.name for t in repo.get_issue_tags(issue_id)}
        new_tags = {t.strip() for t in tags_str.split(",") if t.strip()}

        for tag in new_tags - current_tags:
            repo.add_issue_tag(issue_id, tag)

        for tag in current_tags - new_tags:
            repo.remove_issue_tag(issue_id, tag)

    if request.is_json:
        updated = repo.get_issue(issue_id)
        return (
            jsonify(updated.to_dict()) if updated else (jsonify({"error": "Issue not found"}), 404)
        )

    return redirect(url_for("issue_detail", issue_id=issue_id, message="Issue updated"))


@app.route("/api/issues/<int:issue_id>", methods=["DELETE"])
def api_delete_issue(issue_id: int) -> Any:
    """API: Delete an issue."""
    repo = get_repo()

    deleted = repo.delete_issue(issue_id)

    if not deleted:
        if request.is_json or request.method == "DELETE":
            return jsonify({"error": "Issue not found"}), 404
        return redirect(url_for("issues_list", message="Issue not found"))

    if request.is_json or request.method == "DELETE":
        return jsonify({"message": "Issue deleted"})
    return redirect(url_for("issues_list", message="Issue deleted"))


@app.route("/api/issues/<int:issue_id>/comments", methods=["POST"])
def api_add_comment(issue_id: int) -> Any:
    """API: Add comment to an issue."""
    repo = get_repo()

    data = (request.get_json(silent=True) or {}) if request.is_json else request.form.to_dict()

    text = data.get("text", "").strip()
    if not text:
        if request.is_json:
            return jsonify({"error": "Comment text is required"}), 400
        return redirect(
            url_for("issue_detail", issue_id=issue_id, error="Comment text is required")
        )

    try:
        comment = repo.add_comment(issue_id, text)
        if request.is_json:
            return jsonify(comment.to_dict()), 201
        return redirect(url_for("issue_detail", issue_id=issue_id, message="Comment added"))
    except ValueError as e:
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error=str(e)))


@app.route("/api/comments/<int:comment_id>", methods=["POST", "DELETE"])
def api_delete_comment(comment_id: int) -> Any:
    """API: Delete a comment."""
    repo = get_repo()

    # Handle method override for HTML forms
    method = request.form.get("_method", request.method).upper()

    if method != "DELETE":
        return jsonify({"error": "Method not allowed"}), 405

    deleted = repo.delete_comment(comment_id)

    # Build the redirect target on the server. Never honor a client-supplied
    # location (open-redirect): at most we recover the issue id from a
    # same-origin Referer path (e.g. ``/issues/<id>``) and rebuild the URL with
    # ``url_for``; otherwise fall back to the issues list.
    issue_id = _issue_id_from_referer(request.headers.get("Referer"))
    if issue_id is not None:
        target = url_for("issue_detail", issue_id=issue_id)
    else:
        target = url_for("issues_list")

    if deleted:
        if request.is_json:
            return jsonify({"message": "Comment deleted"})
        return redirect(target)
    else:
        if request.is_json:
            return jsonify({"error": "Comment not found"}), 404
        return redirect(target)


@app.route("/api/issues/<int:issue_id>/start", methods=["POST"])
def api_start_issue(issue_id: int) -> Any:
    """API: Start working on an issue."""
    repo = get_repo()

    try:
        issue, started_at = repo.start_issue(issue_id)
        if request.is_json:
            return jsonify(
                {
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                }
            )
        return redirect(
            url_for("issue_detail", issue_id=issue_id, message="Started working on issue")
        )
    except ValueError as e:
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error=str(e)))


@app.route("/api/issues/stop", methods=["POST"])
def api_stop_issue() -> Any:
    """API: Stop working on active issue."""
    repo = get_repo()

    close = request.args.get("close") == "1"

    result = repo.stop_issue(close=close)

    if result:
        issue, started_at, stopped_at = result
        if request.is_json:
            return jsonify(
                {
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                    "stopped_at": stopped_at.isoformat(),
                }
            )
        return redirect(url_for("dashboard"))
    else:
        if request.is_json:
            return jsonify({"error": "No active issue"}), 400
        return redirect(url_for("dashboard"))


@app.route("/api/issues/<int:issue_id>/similar", methods=["GET"])
def api_similar_issues(issue_id: int) -> Any:
    """API: Find similar issues."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    threshold = request.args.get("threshold", 0.4, type=float)
    limit = request.args.get("limit", 10, type=int)

    all_issues = repo.list_issues()
    other_issues = [i for i in all_issues if i.id != issue_id]
    issue_text = f"{issue.title} {issue.description or ''}"

    similar_results = find_similar_issues(issue_text, other_issues, threshold=threshold)

    return jsonify(
        [{"issue": i.to_dict(), "score": round(score, 3)} for i, score in similar_results[:limit]]
    )


@app.route("/api/issues/<int:issue_id>/audit", methods=["GET"])
def api_issue_audit(issue_id: int) -> Any:
    """API: Get audit logs for an issue."""
    repo = get_repo()
    logs = repo.get_audit_logs(issue_id)

    return jsonify(
        [
            {
                "id": log.id,
                "issue_id": log.issue_id,
                "action": log.action,
                "field_name": log.field_name,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in logs
        ]
    )


@app.route("/api/summary", methods=["GET"])
def api_summary() -> Any:
    """API: Get summary statistics."""
    repo = get_repo()
    return jsonify(repo.get_summary())


@app.route("/api/next", methods=["GET"])
def api_next_issue() -> Any:
    """API: Get next issue to work on."""
    repo = get_repo()
    issue = repo.get_next_issue()

    if issue:
        return jsonify(issue.to_dict())
    return jsonify(None)


@app.route("/api/audit", methods=["GET"])
def api_audit_logs() -> Any:
    """API: Get all audit logs."""
    repo = get_repo()
    issue_id = request.args.get("issue_id", type=int)
    logs = repo.get_audit_logs(issue_id=issue_id)

    return jsonify(
        [
            {
                "id": log.id,
                "issue_id": log.issue_id,
                "action": log.action,
                "field_name": log.field_name,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in logs
        ]
    )


@app.route("/api/issues/<int:issue_id>/comments", methods=["GET"])
def api_get_comments(issue_id: int) -> Any:
    """API: Get comments for an issue."""
    repo = get_repo()
    comments = repo.get_comments(issue_id)
    return jsonify([c.to_dict() for c in comments])


@app.route("/api/issues/<int:issue_id>/time", methods=["GET"])
def api_get_time_entries(issue_id: int) -> Any:
    """API: Get time entries for an issue."""
    repo = get_repo()
    entries = repo.get_time_entries(issue_id)
    result = []
    total_seconds = 0
    for entry in entries:
        e = dict(entry)
        if e.get("duration_seconds"):
            total_seconds += e["duration_seconds"]
            hours = e["duration_seconds"] // 3600
            minutes = (e["duration_seconds"] % 3600) // 60
            e["duration_formatted"] = f"{hours}h {minutes}m" if hours else f"{minutes}m"
        else:
            e["duration_formatted"] = "running..."
        result.append(e)
    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60
    return jsonify(
        {
            "entries": result,
            "total_formatted": f"{total_hours}h {total_minutes}m"
            if total_hours
            else f"{total_minutes}m",
            "total_seconds": total_seconds,
        }
    )


@app.route("/api/issues/<int:issue_id>/dependencies", methods=["GET"])
def api_get_dependencies(issue_id: int) -> Any:
    """API: Get dependencies (blockers/blocking) for an issue."""
    repo = get_repo()
    blockers = repo.get_blockers(issue_id)
    blocking = repo.get_blocking(issue_id)
    return jsonify(
        {
            "blockers": [i.to_dict() for i in blockers],
            "blocking": [i.to_dict() for i in blocking],
        }
    )


@app.route("/api/issues/<int:issue_id>/links", methods=["GET"])
def api_get_issue_links(issue_id: int) -> Any:
    """API: Get links for an issue."""
    repo = get_repo()
    links = repo.get_issue_relations(issue_id)
    return jsonify(links)


@app.route("/api/issues/<int:issue_id>/refs", methods=["GET"])
def api_get_code_refs(issue_id: int) -> Any:
    """API: Get code references for an issue."""
    repo = get_repo()
    refs = repo.get_code_references(issue_id)
    return jsonify(
        [
            {
                "id": r.id,
                "file_path": r.file_path,
                "start_line": r.start_line,
                "end_line": r.end_line,
            }
            for r in refs
        ]
    )
