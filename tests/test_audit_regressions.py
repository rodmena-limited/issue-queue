"""Regression tests for the 2.12.0 full-audit fixes.

Each test pins a bug found in the audit so it cannot silently return.
"""

import json
import multiprocessing
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from issuedb.date_utils import parse_date
from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository
from issuedb.similarity import calculate_similarity


@pytest.fixture
def repo(tmp_path):
    return IssueRepository(str(tmp_path / "test.db"))


def _make(repo, title="Issue", status="open", priority="medium", **kwargs):
    issue = Issue(
        title=title,
        priority=Priority.from_string(priority),
        status=Status.from_string(status),
        **kwargs,
    )
    return repo.create_issue(issue)


class TestFilterNormalization:
    """Filters must bind the normalized enum value, not the raw input."""

    def test_list_accepts_underscore_and_spaces(self, repo):
        _make(repo, "A", status="in-progress")
        for form in ("in-progress", "in_progress", "in progress", " In_Progress "):
            assert len(repo.list_issues(status=form)) == 1, form

    def test_count_accepts_padded_priority(self, repo):
        _make(repo, "A", priority="high")
        assert repo.count_issues(priority=" HIGH ") == 1

    def test_get_next_accepts_underscore_status(self, repo):
        _make(repo, "A", status="in-progress")
        issue = repo.get_next_issue(status="in_progress", log_fetch=False)
        assert issue is not None and issue.title == "A"

    def test_advanced_search_normalizes_lists(self, repo):
        _make(repo, "A", status="in-progress", priority="high")
        found = repo.search_issues_advanced(statuses=["in_progress"], priorities=[" HIGH "])
        assert len(found) == 1

    def test_blocked_filter_normalizes(self, repo):
        a = _make(repo, "A", status="in-progress")
        b = _make(repo, "B")
        repo.add_dependency(a.id, b.id)
        assert len(repo.get_all_blocked_issues(status="in_progress")) == 1


class TestBulkCreatePersistsAllFields:
    def test_due_date_estimate_and_tags_saved(self, repo):
        created = repo.bulk_create_issues(
            [
                {
                    "title": "bulk",
                    "due_date": "2026-08-01T00:00:00",
                    "estimated_hours": 5.0,
                    "tags": [{"name": "backend"}],
                }
            ]
        )
        fetched = repo.get_issue(created[0].id)
        assert fetched.due_date == datetime.fromisoformat("2026-08-01T00:00:00")
        assert fetched.estimated_hours == 5.0
        assert [t.name for t in fetched.tags] == ["backend"]


class TestLikeEscaping:
    def test_percent_matches_literally(self, repo):
        _make(repo, "discount 50% off")
        _make(repo, "unrelated")
        assert len(repo.search_issues("%")) == 1
        assert repo.count_issues(keyword="%") == 1

    def test_underscore_matches_literally(self, repo):
        _make(repo, "snake_case_name")
        _make(repo, "snakeXcaseXname")
        assert len(repo.search_issues("snake_case")) == 1


class TestWontDoBlockers:
    def test_wont_do_blocker_is_resolved(self, repo):
        blocked = _make(repo, "Blocked")
        blocker = _make(repo, "Blocker")
        repo.add_dependency(blocked.id, blocker.id)

        assert repo.get_next_issue(log_fetch=False).id == blocker.id
        repo.update_issue(blocker.id, status="wont-do")

        assert repo.is_blocked(blocked.id) is False
        assert repo.get_next_issue(log_fetch=False).id == blocked.id
        assert repo.get_all_blocked_issues() == []


class TestUpdateValidation:
    def test_empty_title_rejected(self, repo):
        issue = _make(repo, "Valid")
        with pytest.raises(ValueError, match="Title is required"):
            repo.update_issue(issue.id, title="   ")


class TestPagination:
    def test_offset_without_limit(self, repo):
        for i in range(5):
            _make(repo, f"i{i}")
        assert len(repo.list_issues(offset=3)) == 2

    def test_limit_zero_returns_nothing(self, repo):
        _make(repo, "A")
        assert repo.list_issues(limit=0) == []


class TestTagsPopulated:
    def test_list_search_and_next_include_tags(self, repo):
        issue = _make(repo, "Tagged")
        repo.add_issue_tag(issue.id, "urgent")

        assert [t.name for t in repo.list_issues()[0].tags] == ["urgent"]
        assert [t.name for t in repo.search_issues("Tagged")[0].tags] == ["urgent"]
        assert [t.name for t in repo.get_next_issue(log_fetch=False).tags] == ["urgent"]


class TestBulkUpdateAccuracy:
    def test_already_at_target_not_counted_or_touched(self, repo):
        already = _make(repo, "closed one", status="closed")
        _make(repo, "open one")
        before = repo.get_issue(already.id).updated_at

        count = repo.bulk_update_issues(new_status="closed")

        assert count == 1
        assert repo.get_issue(already.id).updated_at == before


class TestBulkAllOrNothing:
    def test_update_from_json_missing_id_changes_nothing(self, repo):
        a = _make(repo, "A")
        with pytest.raises(ValueError, match="not found"):
            repo.bulk_update_issues_from_json(
                [{"id": a.id, "status": "closed"}, {"id": 999, "status": "closed"}]
            )
        assert repo.get_issue(a.id).status == Status.OPEN

    def test_close_missing_id_changes_nothing(self, repo):
        a = _make(repo, "A")
        with pytest.raises(ValueError, match="not found"):
            repo.bulk_close_issues([a.id, 999])
        assert repo.get_issue(a.id).status == Status.OPEN

    def test_update_from_json_invalid_status_changes_nothing(self, repo):
        a = _make(repo, "A")
        b = _make(repo, "B")
        with pytest.raises(ValueError):
            repo.bulk_update_issues_from_json(
                [{"id": a.id, "status": "closed"}, {"id": b.id, "status": "bogus"}]
            )
        assert repo.get_issue(a.id).status == Status.OPEN


class TestTimerRaces:
    def test_double_start_rejected(self, repo):
        issue = _make(repo, "A")
        repo.start_timer(issue.id)
        with pytest.raises(ValueError, match="already running"):
            repo.start_timer(issue.id)

    def test_unique_index_blocks_concurrent_insert(self, repo):
        """The partial unique index must reject a second running timer even if
        the application-level check is bypassed (concurrent process)."""
        issue = _make(repo, "A")
        repo.start_timer(issue.id)
        with repo.db.get_connection() as conn, pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO time_entries (issue_id, started_at) VALUES (?, ?)",
                (issue.id, datetime.now().isoformat()),
            )

    def test_stop_all_timers(self, repo):
        a = _make(repo, "A")
        b = _make(repo, "B")
        repo.start_timer(a.id)
        repo.start_timer(b.id)
        stopped = repo.stop_all_timers()
        assert len(stopped) == 2
        assert repo.get_running_timers() == []


class TestTagAndLinkValidation:
    def test_tag_missing_issue_leaves_no_orphan_tag(self, repo):
        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.add_issue_tag(999, "ghost")
        assert all(t.name != "ghost" for t in repo.list_tags())

    def test_link_missing_issue_raises_value_error(self, repo):
        a = _make(repo, "A")
        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.link_issues(a.id, 999, "related")


class TestZeroEstimate:
    def test_report_includes_zero_hour_estimate(self, repo):
        issue = _make(repo, "A")
        repo.set_estimate(issue.id, 0)
        report = repo.get_time_report(issue_id=issue.id)
        entry = report["issues"][0]
        assert entry["difference_hours"] is not None
        assert entry["over_estimate"] is False


class TestTemplateSeeding:
    def test_deleted_builtin_template_stays_deleted(self, tmp_path):
        from issuedb.database import Database
        from issuedb.database._schema import initialize_schema

        db_path = str(tmp_path / "tmpl.db")
        repo = IssueRepository(db_path)
        assert repo.delete_template("bug") is True

        # Re-running schema init (a new process start) must not resurrect it.
        with Database(db_path).get_connection() as conn:
            initialize_schema(conn)
        assert repo.get_template("bug") is None


class TestMemoryLessonsRelationsCoverage:
    """Basic roundtrips for previously untested repository modules."""

    def test_memory_roundtrip(self, repo):
        repo.add_memory("style", "functional", "code")
        assert repo.get_memory("style").value == "functional"
        with pytest.raises(ValueError):
            repo.add_memory("style", "dup")
        repo.update_memory("style", value="OO")
        assert repo.get_memory("style").value == "OO"
        assert len(repo.list_memory(category="code")) == 1
        assert repo.delete_memory("style") is True
        assert repo.get_memory("style") is None

    def test_lessons_roundtrip(self, repo):
        issue = _make(repo, "A")
        lesson = repo.add_lesson("sanitize inputs", issue.id, "security")
        assert repo.get_lesson(lesson.id).lesson == "sanitize inputs"
        assert len(repo.list_lessons(issue_id=issue.id)) == 1
        with pytest.raises(ValueError):
            repo.add_lesson("dangling", 999)
        assert repo.delete_lesson(lesson.id) is True

    def test_relations_roundtrip(self, repo):
        a = _make(repo, "A")
        b = _make(repo, "B")
        repo.link_issues(a.id, b.id, "related")
        rels = repo.get_issue_relations(a.id)
        assert rels["source"][0]["target_id"] == b.id
        with pytest.raises(ValueError, match="already exists"):
            repo.link_issues(a.id, b.id, "related")
        assert repo.unlink_issues(a.id, b.id, "related") is True


class TestBlankDateRows:
    """Empty-string date columns (from older data) must not break listings."""

    def test_empty_due_date_string_does_not_crash_listing(self, repo, tmp_path):
        issue = _make(repo, "has blank due date")
        # Simulate legacy/third-party data: due_date stored as '' not NULL.
        with repo.db.get_connection() as conn:
            conn.execute("UPDATE issues SET due_date = '' WHERE id = ?", (issue.id,))

        listed = repo.list_issues()
        assert len(listed) == 1
        assert listed[0].due_date is None
        # get_issue and search must survive it too.
        assert repo.get_issue(issue.id).due_date is None
        assert len(repo.search_issues("blank")) == 1


class TestSimilarityEdgeCases:
    def test_punctuation_only_texts_not_identical(self):
        assert calculate_similarity("???", "!!!") == 0.0
        assert calculate_similarity("???", "???") == 1.0

    def test_huge_relative_date_is_value_error(self):
        with pytest.raises(ValueError):
            parse_date("999999999m")


def _hammer_worker(args):
    repo_path, worker_id = args
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from issuedb.models import Issue as WIssue
    from issuedb.repository import IssueRepository as WRepo

    try:
        wrepo = WRepo(repo_path)
        for i in range(5):
            wrepo.create_issue(WIssue(title=f"w{worker_id}-{i}"))
        return None
    except Exception as e:  # pragma: no cover - failure reporting only
        return f"{type(e).__name__}: {e}"


class TestMultiProcessConcurrency:
    def test_concurrent_fresh_database_open_and_create(self, tmp_path):
        """Several processes opening a FRESH database at once must not crash
        on the WAL switch or the duplicate-column migration race."""
        db_path = str(tmp_path / "conc.db")
        with multiprocessing.Pool(4) as pool:
            errors = [e for e in pool.map(_hammer_worker, [(db_path, i) for i in range(4)]) if e]
        assert errors == []
        assert IssueRepository(db_path).count_issues() == 20


CLI = [sys.executable, "-m", "issuedb.cli"]
REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def _run_cli(args, cwd):
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, capture_output=True, text=True, env=env)


class TestCliExitCodes:
    """The agent contract: errors exit nonzero with the message on stderr."""

    def test_create_invalid_due_date(self, tmp_path):
        result = _run_cli(["create", "-t", "X", "--due-date", "nope"], tmp_path)
        assert result.returncode == 1
        assert "Invalid date format" in result.stderr
        assert result.stdout == ""

    def test_memory_update_missing_key_json(self, tmp_path):
        result = _run_cli(["--json", "memory", "update", "nope", "-v", "x"], tmp_path)
        assert result.returncode == 1
        assert json.loads(result.stderr)["error"] == "Memory 'nope' not found"
        assert result.stdout == ""

    def test_bare_subcommand_exits_2(self, tmp_path):
        result = _run_cli(["tag"], tmp_path)
        assert result.returncode == 2

    def test_estimate_missing_issue(self, tmp_path):
        result = _run_cli(["estimate", "999", "4"], tmp_path)
        assert result.returncode == 1
        assert "not found" in result.stderr


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
class TestGitEndToEnd:
    def test_get_commit_message_returns_that_commit(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "init", "-q", "."], check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=T",
                        "commit", "-q", "--allow-empty", "-m", "first commit"], check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=T",
                        "commit", "-q", "--allow-empty", "-m", "second commit"], check=True)
        first_hash = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        from issuedb.git_utils import get_commit_message

        # The pathspec bug returned the wrong (HEAD) message for older hashes.
        assert get_commit_message(first_hash) == "first commit"
