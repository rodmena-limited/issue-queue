"""git-scan must not act on an ambiguous `#N`.

This is where "present every candidate, select none" stops being a display
rule and starts preventing a destructive write. `git-scan --auto-close` CLOSES
issues based on a number parsed out of a commit message, and two clones of a
repo that commits `.issue.db` allocate that number independently.

So an ambiguous reference here does not merely mislabel something — it closes
somebody else's issue, and nothing errors when it does. For an automated
action, "select none" has to mean DO NOTHING AND REPORT.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.git_repository import GitLinkRepository
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._ledger import record_alias, record_uid

MINE = "s256t128:" + "a" * 32
THEIRS = "s256t128:" + "b" * 32


@pytest.fixture
def repo(tmp_path):
    repository = IssueRepository(str(tmp_path / ".issue.db"))
    yield repository
    repository.db.close_connection()
    Database._instances.clear()


@pytest.fixture
def git_repo(repo):
    return GitLinkRepository(str(repo.db.db_path))


@pytest.fixture
def conn(repo):
    connection = sqlite3.connect(str(repo.db.db_path))
    yield connection
    connection.close()


def _commit(issue_id, verb="fixes"):
    return {"hash": "abc123def456", "message": f"{verb} #{issue_id}\n\nSome work."}


# --- the unambiguous path still works (the positive control) --------------


def test_an_unambiguous_reference_is_still_linked_and_closed(repo, git_repo, conn):
    """Without this, a scanner that refused EVERYTHING would pass the tests
    below while making git-scan useless."""
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)

    assert result["links_created"] == 1
    assert result["issues_closed"] == 1
    assert result["ambiguous_refs"] == 0
    assert repo.get_issue(issue.id).status.value == "closed"


# --- the ambiguous path refuses to act ------------------------------------


def test_an_ambiguous_reference_does_not_close_anything(repo, git_repo, conn):
    """The destructive case. Closing here closes the wrong issue silently."""
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    record_alias(conn, THEIRS, issue.id, "replica-b", canonical_number=118)
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)

    assert result["issues_closed"] == 0, "an ambiguous reference closed an issue"
    assert repo.get_issue(issue.id).status.value != "closed"


def test_an_ambiguous_reference_does_not_create_a_link(repo, git_repo, conn):
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    record_alias(conn, THEIRS, issue.id, "replica-b")
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)

    assert result["links_created"] == 0
    assert git_repo.get_links(issue.id) == []


def test_an_ambiguous_reference_is_counted_and_reported(repo, git_repo, conn):
    """It must appear on the summary, not only inside details.

    "0 issues closed" with the refusal buried in a details list reads as
    "nothing to do" — the user never learns a decision was declined.
    """
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    record_alias(conn, THEIRS, issue.id, "replica-b", canonical_number=118)
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)

    assert result["ambiguous_refs"] == 1
    entries = [d for d in result["details"] if d["action"] == "ambiguous"]
    assert len(entries) == 1
    assert "will not choose" in entries[0]["reason"]


def test_every_candidate_is_named_in_the_report(repo, git_repo, conn):
    """A refusal without the candidates is a dead end for the user."""
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    record_alias(conn, THEIRS, issue.id, "replica-b", canonical_number=118)
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)
    entry = next(d for d in result["details"] if d["action"] == "ambiguous")

    assert {c["uid"] for c in entry["candidates"]} == {MINE, THEIRS}


def test_ambiguity_is_checked_before_the_issue_lookup(repo, git_repo, conn):
    """Order matters: the local issue is always findable, so a lookup-first
    scanner would act on it and never reach the ambiguity check."""
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    record_alias(conn, THEIRS, issue.id, "replica-b")
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)
    actions = {d["action"] for d in result["details"]}

    assert actions == {"ambiguous"}
    assert "linked" not in actions
    assert "closed" not in actions


def test_a_scan_still_processes_other_commits(repo, git_repo, conn):
    """One ambiguous reference must not abort the whole scan."""
    ambiguous = repo.create_issue(Issue(title="ambiguous one"))
    clean = repo.create_issue(Issue(title="clean one"))
    record_uid(conn, "issues", ambiguous.id, MINE)
    record_uid(conn, "issues", clean.id, "s256t128:" + "c" * 32)
    record_alias(conn, THEIRS, ambiguous.id, "replica-b")
    conn.commit()

    result = git_repo.scan_commits_and_close_issues(
        [_commit(ambiguous.id), {"hash": "def789", "message": f"fixes #{clean.id}"}],
        auto_close=True,
    )

    assert result["scanned"] == 2
    assert result["ambiguous_refs"] == 1
    assert result["issues_closed"] == 1
    assert repo.get_issue(clean.id).status.value == "closed"
    assert repo.get_issue(ambiguous.id).status.value != "closed"


def test_an_alias_for_the_same_issue_does_not_block_the_scan(repo, git_repo, conn):
    """A replica's own alias must not make every scan refuse.

    A refusal that fires constantly is one users disable, which is worse than
    no refusal at all.
    """
    issue = repo.create_issue(Issue(title="fix login"))
    record_uid(conn, "issues", issue.id, MINE)
    record_alias(conn, MINE, issue.id, "replica-a", canonical_number=issue.id)
    conn.commit()

    result = git_repo.scan_commits_and_close_issues([_commit(issue.id)], auto_close=True)

    assert result["ambiguous_refs"] == 0
    assert result["issues_closed"] == 1
