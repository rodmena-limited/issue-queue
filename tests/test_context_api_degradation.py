"""A failed git lookup must not be reported as a definite absence.

The context API shells out to git three times. The commit lookup swallowed
`TimeoutExpired` and `SubprocessError` and returned `[]`, which a caller cannot
tell apart from "no commit mentions this issue" — the branch field is still
populated, so the response looks entirely successful.

These tests exercise BOTH directions: the lookup succeeding must report
``commits_lookup_ok: True``, and the lookup failing must report ``False``. A
test that only asserted the failure case would pass against a version that
hard-codes the flag.

They build their OWN git repository in the temp cwd rather than relying on the
ambient one. The first version guarded on "not run inside a git work tree" and
skipped — every time, on every machine, because ``conftest`` chdirs each test
into ``tmp_path``. Three tests that can never run report exactly like three
tests that pass.
"""

import os
import subprocess

import pytest

from issuedb.models import Issue, Priority
from issuedb.repository import IssueRepository
from issuedb.web import app

# The developer's own ~/.gitconfig must not decide whether these pass.
_ISOLATED_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


@pytest.fixture
def client(tmp_path):
    """A test client over a temp database, inside a real one-commit git repo."""
    from issuedb.web import _app

    # conftest has already chdir'd us into tmp_path; make it a work tree so the
    # git branch of the context route is genuinely exercised.
    def run(*args: str) -> None:
        subprocess.run(
            args, cwd=tmp_path, capture_output=True, check=True, env=_ISOLATED_ENV
        )

    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "t@example.invalid")
    run("git", "config", "user.name", "t")
    run("git", "commit", "-q", "--allow-empty", "-m", "seed commit for #1")

    path = tmp_path / "ctx.sqlite"
    repo = IssueRepository(str(path))
    repo.create_issue(Issue(title="context fixture", priority=Priority.MEDIUM))

    app.config["TESTING"] = True
    app.config["ISSUEDB_DB_PATH"] = str(path)
    _app._repo_cache.clear()
    with app.test_client() as c:
        yield c
    _app._repo_cache.clear()


def _git(client):
    resp = client.get("/api/issues/1/context")
    assert resp.status_code == 200
    return (resp.get_json() or {}).get("git")


def test_commit_lookup_reports_success_when_git_works(client):
    """The known positive: without it, the failure assertion proves nothing."""
    git = _git(client)
    assert git is not None, "fixture failed to build a git work tree"
    assert git["commits_lookup_ok"] is True
    # The lookup really ran: the seed commit mentions #1.
    assert git["commits_mentioning_issue"], "known positive found no commits"


def test_commit_lookup_failure_is_reported_not_swallowed(client, monkeypatch):
    """A timed-out `git log` must not look like "no commits"."""
    real = subprocess.run

    def flaky(cmd, **kwargs):
        if isinstance(cmd, list) and "log" in cmd:
            raise subprocess.TimeoutExpired(cmd, 5)
        return real(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", flaky)
    git = _git(client)
    assert git is not None

    assert git["commits_mentioning_issue"] == []
    assert git["commits_lookup_ok"] is False
    # The rest of the git context still comes back — a failed sub-lookup
    # degrades one field, not the whole block.
    assert "branch" in git


def test_subprocess_error_is_reported_too(client, monkeypatch):
    """Both exception types the handler catches must set the flag."""
    real = subprocess.run

    def flaky(cmd, **kwargs):
        if isinstance(cmd, list) and "log" in cmd:
            raise subprocess.SubprocessError("boom")
        return real(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", flaky)
    git = _git(client)
    assert git is not None
    assert git["commits_lookup_ok"] is False


def test_commitless_repo_is_a_failed_lookup_not_an_empty_result(client, tmp_path):
    """`git log` exits 128 with no commits, and that is not "no commits found".

    The first version of the flag keyed only off the exception handlers, so a
    freshly initialised repository reported ``commits_lookup_ok: True`` beside
    an empty list — the flag asserting, falsely, that the search had run.
    """
    env = _ISOLATED_ENV
    # Throw away every commit, leaving a valid work tree with an unborn branch.
    subprocess.run(
        ["git", "checkout", "-q", "--orphan", "empty"],
        cwd=tmp_path, check=True, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "rm", "-rq", "--cached", "."],
        cwd=tmp_path, capture_output=True, env=env,
    )

    git = _git(client)
    assert git is not None
    assert git["commits_mentioning_issue"] == []
    assert git["commits_lookup_ok"] is False


def test_cli_context_reports_the_same_signal(tmp_path):
    """The CLI path carries its own flag, and `--all` makes it differ.

    `git log --all` exits 0 on an unborn branch — it searched every ref and
    found none — so the CLI's ``True`` here is correct rather than a repeat of
    the API's bug. Asserting it pins the divergence deliberately.
    """
    from issuedb.cli import _context

    env = _ISOLATED_ENV
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True,
                   capture_output=True, env=env)

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        info = _context._get_git_info(None, 1)
    finally:
        os.chdir(cwd)

    assert info is not None
    assert info["related_commits"] == []
    assert info["related_commits_lookup_ok"] is True
