"""Data that cannot sync must be STATED, not left to silence.

The apply path reports UNSUPPORTED when a change for such an entity arrives.
An entity the server has no interface for never arrives, so without this the
user sees "52 applied" and nothing at all about the rest — and concludes their
data is synced because nothing said otherwise.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._coverage import render, uncovered

FOUR = frozenset({"issue", "issue_tag", "issue_dependency", "issue_relation"})


@pytest.fixture
def repo(tmp_path):
    repository = IssueRepository(str(tmp_path / ".issue.db"))
    yield repository
    repository.db.close_connection()
    Database._instances.clear()


@pytest.fixture
def conn(repo):
    connection = sqlite3.connect(str(repo.db.db_path))
    yield connection
    connection.close()


def test_a_table_with_rows_and_no_entity_is_reported(repo, conn):
    issue = repo.create_issue(Issue(title="x"))
    repo.add_comment(issue.id, "a comment the server cannot carry")

    items = uncovered(conn, FOUR)
    tables = {i.table for i in items}
    assert "comments" in tables
    assert "issues" not in tables, "a COVERED table was reported as uncovered"


def test_an_empty_table_is_not_reported(repo, conn):
    """Noise is how a real warning gets ignored."""
    repo.create_issue(Issue(title="x"))
    assert "time_entries" not in {i.table for i in uncovered(conn, FOUR)}


def test_nothing_is_claimed_when_the_server_advertises_no_list(repo, conn):
    """An older server makes this UNKNOWN, not true.

    Claiming data is unsyncable on a guess is the same defect pointing the
    other way.
    """
    issue = repo.create_issue(Issue(title="x"))
    repo.add_comment(issue.id, "c")
    assert uncovered(conn, None) == []
    assert "UNKNOWN" in render([], None)


def test_the_report_names_the_rows_and_the_missing_entity(repo, conn):
    issue = repo.create_issue(Issue(title="x"))
    repo.add_comment(issue.id, "c")
    text = render(uncovered(conn, FOUR), FOUR)
    assert "NOT SYNCED" in text
    assert "comments" in text
    assert "comment" in text
    assert "cannot transfer" in text


def test_the_report_is_silent_when_everything_is_covered(repo, conn):
    repo.create_issue(Issue(title="x"))
    everything = FOUR | {"comment", "issue_link", "code_reference", "time_entry",
                         "audit_log", "lesson", "memory", "saved_search", "issue_template"}
    assert render(uncovered(conn, everything), everything) == ""


def test_a_growing_entity_list_shrinks_the_report(repo, conn):
    """The list grows as the server ships; coverage must follow it."""
    issue = repo.create_issue(Issue(title="x"))
    repo.add_comment(issue.id, "c")
    before = {i.table for i in uncovered(conn, FOUR)}
    after = {i.table for i in uncovered(conn, FOUR | {"comment"})}
    assert "comments" in before
    assert "comments" not in after
