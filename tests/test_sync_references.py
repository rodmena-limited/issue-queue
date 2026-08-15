"""Ambiguous issue references: present every candidate, select none.

The rule under test is a contract rule, not a display preference:

    WHEN A REFERENCE IS AMBIGUOUS, PRESENT EVERY CANDIDATE AND SELECT NONE.

A reference that resolves to the wrong issue is worse than one that refuses to
resolve — the second is a question, the first is a lie, and nothing errors
either way.

Note what makes these tests meaningful: ambiguity is REACHABLE here with real
rows. ``issues.id`` is a primary key, so a resolver consulting only the issues
table could never produce two candidates and every assertion below would be
vacuous. The alias table is what makes the ambiguous path executable.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._ledger import record_alias, record_uid
from issuedb.sync._references import (
    partition,
    render_report,
    resolve_all,
    resolve_reference,
)

MINE = "s256t128:" + "a" * 32
THEIRS = "s256t128:" + "b" * 32


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


@pytest.fixture
def issue(repo, conn):
    created = repo.create_issue(Issue(title="fix login timeout"))
    record_uid(conn, "issues", created.id, MINE)
    conn.commit()
    return created


def _make_ambiguous(conn, number, replica="replica-b", canonical=118):
    """Another replica's issue claimed the same local number."""
    record_alias(conn, THEIRS, number, replica, canonical_number=canonical)
    conn.commit()


# --- the ambiguous path is reachable --------------------------------------


def test_the_alias_table_exists(repo, conn):
    """Control. Without it every ambiguity test below would be vacuous."""
    assert repo.db.schema_version >= 3
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='issue_number_alias'"
    ).fetchone()
    assert row[0] == 1


def test_a_single_match_resolves(issue, conn):
    reference = resolve_reference(conn, issue.id)
    assert not reference.is_ambiguous
    assert not reference.is_unknown
    resolved = reference.resolved()
    assert resolved is not None
    assert resolved.title == "fix login timeout"
    assert resolved.uid == MINE


def test_two_replicas_claiming_one_number_is_ambiguous(issue, conn):
    _make_ambiguous(conn, issue.id)

    reference = resolve_reference(conn, issue.id)

    assert reference.is_ambiguous
    assert len(reference.candidates) == 2
    assert {c.uid for c in reference.candidates} == {MINE, THEIRS}


def test_an_ambiguous_reference_resolves_to_nothing(issue, conn):
    """The load-bearing assertion: no winner is handed back.

    resolved() returning a first-of would let every existing call site keep
    working while silently pointing at whichever row happened to sort first.
    """
    _make_ambiguous(conn, issue.id)
    assert resolve_reference(conn, issue.id).resolved() is None


def test_an_unknown_number_is_reported_not_omitted(conn):
    reference = resolve_reference(conn, 999)
    assert reference.is_unknown
    assert reference.resolved() is None
    assert "unknown" in reference.render().lower()


# --- what the user is shown -----------------------------------------------


def test_every_candidate_appears_in_the_output(issue, conn):
    _make_ambiguous(conn, issue.id)
    rendered = resolve_reference(conn, issue.id).render()

    assert "AMBIGUOUS" in rendered
    for candidate in resolve_reference(conn, issue.id).candidates:
        assert candidate.uid.split(":")[-1][:12] in rendered


def test_the_output_says_it_will_not_choose(issue, conn):
    _make_ambiguous(conn, issue.id)
    assert "will not choose" in resolve_reference(conn, issue.id).render()


def test_a_candidate_is_described_by_its_uid_not_only_its_number(issue, conn):
    """Two candidates share a number by definition, so the number cannot tell
    them apart — the uid is the only distinguishing thing available."""
    _make_ambiguous(conn, issue.id)
    for candidate in resolve_reference(conn, issue.id).candidates:
        assert candidate.uid
        assert candidate.uid.split(":")[-1][:12] in candidate.describe()


def test_a_candidate_not_present_locally_is_still_listed(issue, conn):
    """Omitting it would make an ambiguous reference look unambiguous.

    That is the exact failure this module exists to prevent, arriving through
    an apparently reasonable "we have no title for it" shortcut.
    """
    _make_ambiguous(conn, issue.id)
    absent = [c for c in resolve_reference(conn, issue.id).candidates if c.uid == THEIRS]
    assert len(absent) == 1
    assert "not present locally" in absent[0].title


def test_an_alias_for_the_same_issue_is_not_a_second_candidate(issue, conn):
    """A replica recording its OWN issue's number must not fake ambiguity.

    Without the uid de-duplication this would report every synced issue as
    ambiguous with itself, and the warning would become noise users learn to
    ignore — which is worse than no warning.
    """
    record_alias(conn, MINE, issue.id, "replica-a", canonical_number=issue.id)
    conn.commit()

    reference = resolve_reference(conn, issue.id)
    assert not reference.is_ambiguous
    assert reference.resolved() is not None


# --- batches ---------------------------------------------------------------


def test_resolve_all_is_sorted_and_deduplicated(repo, conn):
    first = repo.create_issue(Issue(title="one"))
    second = repo.create_issue(Issue(title="two"))
    references = resolve_all(conn, [second.id, first.id, first.id])
    assert [r.number for r in references] == sorted([first.id, second.id])


def test_partition_keeps_ambiguous_and_unknown_apart(repo, issue, conn):
    """They need different actions: unknown is stale, ambiguous needs a human."""
    other = repo.create_issue(Issue(title="unambiguous"))
    record_uid(conn, "issues", other.id, "s256t128:" + "c" * 32)
    _make_ambiguous(conn, issue.id)

    groups = partition(resolve_all(conn, [issue.id, other.id, 999]))

    assert [r.number for r in groups["resolved"]] == [other.id]
    assert [r.number for r in groups["ambiguous"]] == [issue.id]
    assert [r.number for r in groups["unknown"]] == [999]


def test_the_report_surfaces_ambiguity_rather_than_dropping_it(repo, issue, conn):
    other = repo.create_issue(Issue(title="unambiguous"))
    record_uid(conn, "issues", other.id, "s256t128:" + "c" * 32)
    _make_ambiguous(conn, issue.id)

    report = render_report(resolve_all(conn, [issue.id, other.id, 999]))

    assert "AMBIGUOUS" in report
    assert "unambiguous" in report
    assert "999" in report


def test_an_empty_reference_list_says_so(conn):
    assert "No issue references" in render_report([])


# --- the resolver never prefers -------------------------------------------


def test_recency_does_not_break_the_tie(repo, issue, conn):
    """Explicitly: not newest-wins, not most-recently-updated-wins.

    Any tie-break would be a silent choice, and a plausible one is the most
    dangerous kind because it looks like a feature.
    """
    _make_ambiguous(conn, issue.id)
    conn.execute("UPDATE issues SET updated_at = '2099-01-01' WHERE id = ?", (issue.id,))
    conn.commit()

    assert resolve_reference(conn, issue.id).resolved() is None


def test_a_reference_stays_ambiguous_across_repeated_resolution(issue, conn):
    """Stable, not flapping — the answer must not depend on row order."""
    _make_ambiguous(conn, issue.id)
    first = resolve_reference(conn, issue.id)
    second = resolve_reference(conn, issue.id)
    assert first.candidates == second.candidates
