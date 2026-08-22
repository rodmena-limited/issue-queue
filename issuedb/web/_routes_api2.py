"""JSON API routes (part 2)."""

from typing import Any

from flask import jsonify, request

from issuedb.web._app import app, get_repo


@app.route("/api/issues/<int:issue_id>/context", methods=["GET"])
def api_get_context(issue_id: int) -> Any:
    """API: Get comprehensive context for an issue."""
    import subprocess

    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    context: dict[str, Any] = {
        "git": None,
        "suggested_actions": [],
        "related_issues": [],
    }

    # Get git info
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

            # Get recent commits mentioning this issue
            commits = []
            commits_lookup_ok = True
            try:
                log_result = subprocess.run(
                    # Non-digit boundary so issue 1 does not match #10..#19x.
                    ["git", "log", "--oneline", "-10", "-E", f"--grep=#{issue_id}([^0-9]|$)"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # A non-zero exit is a failed lookup too, not an empty
                # result: `git log` exits 128 in a repository with no commits
                # yet, and the first version of this flag reported that as a
                # successful search returning nothing.
                if log_result.returncode != 0:
                    commits_lookup_ok = False
                elif log_result.stdout.strip():
                    for line in log_result.stdout.strip().split("\n")[:5]:
                        if line:
                            parts = line.split(" ", 1)
                            commits.append(
                                {
                                    "hash": parts[0],
                                    "message": parts[1] if len(parts) > 1 else "",
                                }
                            )
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                # An empty list here would be indistinguishable from "no commit
                # mentions this issue", so the failure is reported rather than
                # swallowed: the caller sees an absence it cannot verify.
                commits_lookup_ok = False

            # Check if branch matches issue
            branch_matches = current_branch and str(issue_id) in current_branch

            context["git"] = {
                "branch": current_branch,
                "branch_matches_issue": branch_matches,
                "commits_mentioning_issue": commits,
                "commits_lookup_ok": commits_lookup_ok,
            }
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    # Generate suggested actions
    actions = []
    if issue.status.value == "open":
        actions.append(
            {
                "type": "start",
                "text": "Start working on this issue",
                "priority": "high" if issue.priority.value in ["critical", "high"] else "normal",
            }
        )
    elif issue.status.value == "in-progress":
        actions.append(
            {
                "type": "progress",
                "text": "Add a progress update comment",
                "priority": "normal",
            }
        )
        actions.append(
            {
                "type": "close",
                "text": "Close issue when complete",
                "priority": "normal",
            }
        )
    elif issue.status.value == "closed":
        actions.append(
            {
                "type": "reopen",
                "text": "Reopen if issue persists",
                "priority": "low",
            }
        )
    elif issue.status.value == "wont-do":
        actions.append(
            {
                "type": "reopen",
                "text": "Reopen if decision changes",
                "priority": "low",
            }
        )

    # Check comments
    comments = repo.get_comments(issue_id)
    if len(comments) == 0:
        actions.append(
            {
                "type": "comment",
                "text": "Add notes or context",
                "priority": "normal",
            }
        )

    # Check blockers
    blockers = repo.get_blockers(issue_id)
    open_blockers = [b for b in blockers if b.status.value not in ["closed", "wont-do"]]
    if open_blockers:
        actions.insert(
            0,
            {
                "type": "blocked",
                "text": f"Blocked by {len(open_blockers)} open issue(s)",
                "priority": "high",
            },
        )

    context["suggested_actions"] = actions

    # Get related issues (by keyword search)
    if issue.title:
        words = issue.title.split()
        if words:
            keyword = words[0]
            similar = repo.search_issues(keyword=keyword, limit=5)
            related = [
                {"id": i.id, "title": i.title, "status": i.status.value}
                for i in similar
                if i.id != issue_id
            ][:3]
            context["related_issues"] = related

    return jsonify(context)


@app.route("/api/memory", methods=["GET", "POST"])
def api_memory_list_create() -> Any:
    """API: List or create memory items."""
    repo = get_repo()

    if request.method == "POST":
        data = (request.get_json(silent=True) or {})
        try:
            memory = repo.add_memory(
                key=data["key"],
                value=data["value"],
                category=data.get("category", "general"),
            )
            return jsonify(memory.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except KeyError as e:
            return jsonify({"error": f"Missing field: {str(e)}"}), 400
    else:
        category = request.args.get("category")
        search = request.args.get("search")
        memories = repo.list_memory(category=category, search=search)
        return jsonify([m.to_dict() for m in memories])


@app.route("/api/memory/<path:key>", methods=["PUT", "DELETE"])
def api_memory_update_delete(key: str) -> Any:
    """API: Update or delete memory item."""
    repo = get_repo()

    if request.method == "DELETE":
        if repo.delete_memory(key):
            return jsonify({"message": "Memory deleted"})
        return jsonify({"error": "Memory not found"}), 404
    else:
        data = (request.get_json(silent=True) or {})
        memory = repo.update_memory(
            key=key,
            value=data.get("value"),
            category=data.get("category"),
        )
        if memory:
            return jsonify(memory.to_dict())
        return jsonify({"error": "Memory not found"}), 404


@app.route("/api/lessons", methods=["GET", "POST"])
def api_lessons_list_create() -> Any:
    """API: List or create lessons learned."""
    repo = get_repo()

    if request.method == "POST":
        data = (request.get_json(silent=True) or {})
        try:
            ll = repo.add_lesson(
                lesson=data["lesson"],
                issue_id=data.get("issue_id"),
                category=data.get("category", "general"),
            )
            return jsonify(ll.to_dict()), 201
        except KeyError as e:
            return jsonify({"error": f"Missing field: {str(e)}"}), 400
    else:
        issue_id = request.args.get("issue_id", type=int)
        category = request.args.get("category")
        lessons = repo.list_lessons(issue_id=issue_id, category=category)
        return jsonify([lesson.to_dict() for lesson in lessons])


@app.route("/api/tags", methods=["GET"])
def api_tags_list() -> Any:
    """API: List all tags."""
    repo = get_repo()
    tags = repo.list_tags()
    return jsonify([t.to_dict() for t in tags])


@app.route("/api/issues/<int:issue_id>/tags", methods=["GET", "POST", "DELETE"])
def api_issue_tags(issue_id: int) -> Any:
    """API: Manage issue tags."""
    repo = get_repo()

    if request.method == "GET":
        tags = repo.get_issue_tags(issue_id)
        return jsonify([t.to_dict() for t in tags])

    elif request.method == "POST":
        data = (request.get_json(silent=True) or {})
        tag_name = data.get("tag")
        if not tag_name:
            return jsonify({"error": "Tag name required"}), 400

        if repo.add_issue_tag(issue_id, tag_name):
            return jsonify({"message": "Tag added"}), 201
        return jsonify({"message": "Tag already exists"}), 200

    elif request.method == "DELETE":
        tag_name = request.args.get("tag")
        if not tag_name:
            return jsonify({"error": "Tag name required"}), 400

        if repo.remove_issue_tag(issue_id, tag_name):
            return jsonify({"message": "Tag removed"})
        return jsonify({"error": "Tag not found on issue"}), 404


@app.route("/api/links", methods=["POST", "DELETE"])
def api_links() -> Any:
    """API: Manage issue links."""
    repo = get_repo()

    data = (request.get_json(silent=True) or {})
    source = data.get("source")
    target = data.get("target")
    type = data.get("type")

    if not source or not target:
        return jsonify({"error": "Source and target required"}), 400

    if request.method == "POST":
        if not type:
            return jsonify({"error": "Type required"}), 400
        try:
            rel = repo.link_issues(source, target, type)
            return jsonify(rel.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    elif request.method == "DELETE":
        if repo.unlink_issues(source, target, type):
            return jsonify({"message": "Unlinked"})
        return jsonify({"error": "Link not found"}), 404

