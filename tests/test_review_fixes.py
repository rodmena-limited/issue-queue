"""Regression tests for the code-review fixes (GitHub sync + full audit).

Each test pins a specific bug that was found and fixed so it cannot regress:

* previously-unreachable CLI subcommands are now registered and dispatched;
* ``report`` no longer crashes on ``wont-do`` issues;
* ``--json`` errors are emitted as JSON;
* ``bulk-update`` refuses to touch every issue without a filter / ``--all``;
* ``summary`` no longer leaks raw Python dict reprs;
* ``Status.from_string`` accepts underscore/space separators;
* the web layer blocks cross-origin mutations, returns 400 on bad input,
  and renders the link-delete button without an XSS-able inline handler.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

from issuedb.cli import main
from issuedb.models import Status
from issuedb.web import app


def _run_main(argv: list, monkeypatch) -> int:
    """Invoke the CLI ``main()`` with ``argv`` and return the exit code (0 on success)."""
    monkeypatch.setattr(sys, "argv", ["issuedb-cli", *argv])
    try:
        main()
        return 0
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 1)


@pytest.fixture
def db_path():
    """Path to a fresh temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


class TestCliCommandWiring:
    """Commands whose parsers were registered after ``parse_args`` / never wired."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["timer-status"],
            ["find-similar", "anything"],
            ["dedupe"],
            ["time-report"],
            ["affected", "some/file.py"],
        ],
    )
    def test_command_is_registered(self, argv, db_path, monkeypatch, capsys):
        code = _run_main(["--db", db_path, *argv], monkeypatch)
        # argparse exits 2 with "invalid choice" for unknown subcommands.
        assert code != 2
        assert "invalid choice" not in capsys.readouterr().err

    def test_timer_and_estimate_roundtrip(self, db_path, monkeypatch, capsys):
        assert _run_main(["--db", db_path, "create", "-t", "Task"], monkeypatch) == 0
        assert _run_main(["--db", db_path, "timer-start", "1"], monkeypatch) == 0
        assert _run_main(["--db", db_path, "estimate", "1", "2.5"], monkeypatch) == 0
        out = capsys.readouterr().out
        assert "Timer started" in out
        assert "Estimate set" in out

    def test_find_similar_and_dedupe_run(self, db_path, monkeypatch, capsys):
        _run_main(["--db", db_path, "create", "-t", "Login button is broken"], monkeypatch)
        capsys.readouterr()
        assert _run_main(["--db", db_path, "find-similar", "login broken"], monkeypatch) == 0
        assert _run_main(["--db", db_path, "dedupe"], monkeypatch) == 0

    def test_create_accepts_tags(self, db_path, monkeypatch, capsys):
        # README documents `create --tag`; it must attach the tags.
        code = _run_main(
            ["--db", db_path, "create", "-t", "Tagged", "--tag", "v1.0", "--tag", "backend"],
            monkeypatch,
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "v1.0" in out and "backend" in out
        # And the tag filter finds it.
        assert _run_main(["--db", db_path, "list", "--tag", "v1.0"], monkeypatch) == 0
        assert "Tagged" in capsys.readouterr().out


class TestReportWontDo:
    """``get_report`` raised KeyError for valid ``wont-do`` issues."""

    def test_report_handles_wont_do(self, db_path, monkeypatch, capsys):
        _run_main(["--db", db_path, "create", "-t", "Task"], monkeypatch)
        _run_main(["--db", db_path, "update", "1", "-s", "wont-do"], monkeypatch)
        capsys.readouterr()
        assert _run_main(["--db", db_path, "report"], monkeypatch) == 0
        out = capsys.readouterr().out
        assert "Wont Do" in out or "wont_do" in out


class TestJsonErrorMode:
    """Errors must be JSON when ``--json`` is set, not plain text."""

    def test_json_error_is_valid_json(self, db_path, monkeypatch, capsys):
        code = _run_main(["--json", "--db", db_path, "get", "9999"], monkeypatch)
        assert code == 1
        payload = json.loads(capsys.readouterr().err.strip())
        assert "error" in payload


class TestBulkUpdateGuard:
    """Unfiltered ``bulk-update`` must not silently rewrite every issue."""

    def test_requires_filter_or_all(self, db_path, monkeypatch, capsys):
        _run_main(["--db", db_path, "create", "-t", "A"], monkeypatch)
        _run_main(["--db", db_path, "create", "-t", "B"], monkeypatch)
        capsys.readouterr()

        code = _run_main(["--db", db_path, "bulk-update", "-s", "closed"], monkeypatch)
        assert code == 1
        assert "refusing to update ALL" in capsys.readouterr().err

        code = _run_main(["--db", db_path, "bulk-update", "-s", "closed", "--all"], monkeypatch)
        assert code == 0
        assert "Updated 2" in capsys.readouterr().out


class TestSummaryFormatting:
    """Human-readable ``summary`` must not leak Python dict reprs."""

    def test_no_raw_dict_repr(self, db_path, monkeypatch, capsys):
        _run_main(["--db", db_path, "create", "-t", "A"], monkeypatch)
        capsys.readouterr()
        _run_main(["--db", db_path, "summary"], monkeypatch)
        out = capsys.readouterr().out
        assert "{'" not in out
        assert "By Status" in out


class TestStatusNormalization:
    """``Status.from_string`` should accept underscore/space separators."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("in-progress", Status.IN_PROGRESS),
            ("in_progress", Status.IN_PROGRESS),
            ("in progress", Status.IN_PROGRESS),
            ("WONT_DO", Status.WONT_DO),
            (" Open ", Status.OPEN),
        ],
    )
    def test_separator_variants(self, value, expected):
        assert Status.from_string(value) == expected

    def test_invalid_still_raises(self):
        with pytest.raises(ValueError):
            Status.from_string("nonsense")


class TestWebSecurity:
    """CSRF, input validation, and XSS hardening of the Flask layer."""

    @pytest.fixture
    def web(self):
        app.config["TESTING"] = True
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db = f.name
        with app.test_client() as client:
            yield client, db
        Path(db).unlink(missing_ok=True)

    def test_same_origin_post_allowed(self, web):
        client, db = web
        resp = client.post(
            f"/api/issues?db={db}",
            json={"title": "Same origin"},
            headers={"Origin": "http://localhost"},
        )
        assert resp.status_code in (200, 201)

    def test_cross_origin_post_blocked(self, web):
        client, db = web
        resp = client.post(
            f"/api/issues?db={db}",
            json={"title": "Cross origin"},
            headers={"Origin": "http://evil.example"},
        )
        assert resp.status_code == 403

    def test_cross_origin_referer_blocked(self, web):
        client, db = web
        resp = client.post(
            f"/api/issues?db={db}",
            json={"title": "Cross referer"},
            headers={"Referer": "http://evil.example/x"},
        )
        assert resp.status_code == 403

    def test_get_requests_not_blocked(self, web):
        client, db = web
        resp = client.get(f"/api/issues?db={db}", headers={"Origin": "http://evil.example"})
        assert resp.status_code == 200

    def test_bad_priority_returns_400_not_500(self, web):
        client, db = web
        resp = client.post(f"/api/issues?db={db}", json={"title": "X", "priority": "urgent"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_json_body_not_500(self, web):
        client, db = web
        # Content-Type application/json with an empty body used to crash on data["..."].
        resp = client.post(
            f"/api/memory?db={db}", data="", content_type="application/json"
        )
        assert resp.status_code != 500

    def test_link_delete_button_has_no_inline_xss_sink(self, web):
        client, db = web
        client.post(f"/api/issues?db={db}", json={"title": "Has detail page"})
        resp = client.get(f"/issues/1?db={db}")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        # The safe rewrite uses a data-attribute + escapeAttr, not an inline
        # onclick that string-concatenates the user-controlled link type.
        assert "data-link-type=" in body
        assert "escapeAttr(link.type)" in body
        assert "deleteLink(' + issueId + ', ' + link.id + ', \\'" not in body


class TestDeferredFixes:
    """Deferred review items: field-clearing, due-date no-op, time-report LEFT JOIN,
    atomic dependency cycle check."""

    @pytest.fixture
    def repo(self):
        from issuedb.repository import IssueRepository

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        yield IssueRepository(path)
        Path(path).unlink(missing_ok=True)

    def test_update_clears_description_and_due_date(self, repo):
        from datetime import datetime

        from issuedb.models import Issue

        issue = repo.create_issue(
            Issue(title="T", description="some desc", due_date=datetime(2026, 6, 20))
        )
        cleared = repo.update_issue(issue.id, description="")
        assert cleared is not None and cleared.description == ""
        cleared = repo.update_issue(issue.id, due_date="")
        assert cleared is not None and cleared.due_date is None

    def test_due_date_reset_is_noop(self, repo):
        from issuedb.models import Issue

        issue = repo.create_issue(Issue(title="T"))
        repo.update_issue(issue.id, due_date="2026-06-20")
        before = len(repo.get_audit_logs(issue_id=issue.id))
        # Re-setting the identical date must not write another audit entry.
        repo.update_issue(issue.id, due_date="2026-06-20")
        after = len(repo.get_audit_logs(issue_id=issue.id))
        assert after == before

    def test_time_report_includes_estimated_untracked_issue(self, repo):
        from issuedb.models import Issue

        issue = repo.create_issue(Issue(title="Estimated but untracked"))
        repo.set_estimate(issue.id, 5)
        report = repo.get_time_report(period="all")
        ids = [row["issue_id"] for row in report["issues"]]
        # Previously dropped because WHERE turned the LEFT JOIN into an INNER JOIN.
        assert issue.id in ids

    def test_add_dependency_rejects_and_rolls_back_cycle(self, repo):
        from issuedb.models import Issue

        a = repo.create_issue(Issue(title="A"))
        b = repo.create_issue(Issue(title="B"))
        assert repo.add_dependency(a.id, b.id) is True  # A blocked by B
        with pytest.raises(ValueError, match="cycle"):
            repo.add_dependency(b.id, a.id)  # B blocked by A -> cycle
        # The rejected insert must have been rolled back.
        assert all(bl.id != a.id for bl in repo.get_blockers(b.id))
