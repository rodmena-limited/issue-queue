"""Tests for the sync_row uid ledger and the sync_outbox change feed.

The claims worth testing here are not "the functions work". They are the three
design decisions that took a live reproduction to justify:

* the outbox is fed by TRIGGERS, so writes that never touch issuedb's Python
  are still captured — including a cascade delete, which is where tombstones
  would otherwise be lost silently;
* the ledger tolerates two rows deriving ONE uid, because databases written
  before uids existed already contain them;
* a tombstone is never removed, because absence must never mean deletion.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._ledger import (
    UidCollision,
    find_uid_collisions,
    get_uid,
    outbox_pending,
    record_uid,
    resolve_uid,
    tombstone,
)


@pytest.fixture
def repo(tmp_path):
    path = str(tmp_path / ".issue.db")
    repository = IssueRepository(path)
    yield repository
    repository.db.close_connection()
    Database._instances.clear()


@pytest.fixture
def raw(repo):
    """A connection that bypasses issuedb entirely, as a user with sqlite3 would."""
    connection = sqlite3.connect(str(repo.db.db_path))
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def _outbox(connection):
    return [(row[1], row[2], row[3]) for row in outbox_pending(connection)]


# --- the migration ---------------------------------------------------------


def test_a_fresh_database_has_the_sync_tables(repo, raw):
    tables = {
        row[0]
        for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"sync_row", "sync_outbox"} <= tables
    assert repo.db.schema_version >= 2


def test_uid_is_not_unique_in_the_ledger(raw):
    """The constraint that a live reproduction forced.

    Two pre-existing bidirectional relations derive ONE uid. A UNIQUE index
    here would fail the backfill on real user data, and 'fixing' that with
    INSERT OR IGNORE would silently drop one of the two rows.
    """
    record_uid(raw, "issue_relation", 1, "s256t128:same")
    record_uid(raw, "issue_relation", 2, "s256t128:same")
    raw.commit()
    assert resolve_uid(raw, "s256t128:same") == [1, 2]


# --- the outbox is fed by triggers ----------------------------------------


def test_writes_through_issuedb_are_captured(repo, raw):
    issue = repo.create_issue(Issue(title="A"))
    entries = _outbox(raw)
    assert ("issues", issue.id, "insert") in entries


def test_a_write_that_never_touches_issuedb_is_captured(repo, raw):
    """The whole justification for using triggers.

    The CLI, the Flask UI, a user with sqlite3, and an OLDER INSTALLED issuedb
    all write to this file and share no Python. 22 of 42 repos in this estate
    commit .issue.db to git, so a mixed-version write is normal, not exotic.
    An outbox maintained in the repository layer would miss every one of these.
    """
    repo.create_issue(Issue(title="A"))
    before = outbox_pending(raw)[-1][0]

    raw.execute("INSERT INTO issues (title) VALUES ('written by sqlite3')")
    raw.commit()

    new = [(row[1], row[2], row[3]) for row in outbox_pending(raw, after_seq=before)]
    assert new == [("issues", 2, "insert")]


def test_an_external_update_and_delete_are_captured(repo, raw):
    issue = repo.create_issue(Issue(title="A"))
    before = outbox_pending(raw)[-1][0]

    raw.execute("UPDATE issues SET title='changed' WHERE id=?", (issue.id,))
    raw.execute("DELETE FROM issues WHERE id=?", (issue.id,))
    raw.commit()

    ops = [row[3] for row in outbox_pending(raw, after_seq=before)]
    assert ops == ["update", "delete"]


def test_cascade_deleted_children_are_captured(repo, raw):
    """Verified against SQLite rather than assumed.

    An issue's comments and relations go by ON DELETE CASCADE. If those child
    deletions did not fire their triggers, the outbox would record the parent's
    deletion only, the children's tombstones would never propagate, and every
    other replica would keep rows the server believes are gone — with nothing
    erroring at any point.
    """
    parent = repo.create_issue(Issue(title="parent"))
    other = repo.create_issue(Issue(title="other"))
    repo.add_comment(parent.id, "child comment")
    repo.link_issues(parent.id, other.id, "relates_to")
    before = outbox_pending(raw)[-1][0]

    raw.execute("DELETE FROM issues WHERE id=?", (parent.id,))
    raw.commit()

    deleted = {row[1] for row in outbox_pending(raw, after_seq=before) if row[3] == "delete"}
    assert "issues" in deleted
    assert "comments" in deleted, "a cascade-deleted comment produced no outbox row"
    assert "issue_relations" in deleted, "a cascade-deleted relation produced no outbox row"


def test_issue_tags_outbox_rows_identify_the_membership(repo, raw):
    """issue_tags has no id column, so local_id must carry the ISSUE id.

    The first version of this test asserted only ``local_id is not None`` and
    a mutation swapping ``issue_id`` for ``rowid`` passed it — rowid is not
    None either. That assertion checked the shape of the container instead of
    the value in it, which is the same defect this collaboration keeps finding
    elsewhere. It asserts the identity now.

    It matters because ``issue_tags`` rowids are not stable across a VACUUM,
    so an outbox row naming one points at nothing afterwards.
    """
    first = repo.create_issue(Issue(title="A"))
    second = repo.create_issue(Issue(title="B"))
    repo.add_issue_tag(second.id, "bug")

    rows = [row for row in outbox_pending(raw) if row[1] == "issue_tags"]
    assert rows, "tagging an issue produced no outbox row"
    assert [row[2] for row in rows] == [second.id], (
        f"outbox must name the tagged issue ({second.id}), not {[r[2] for r in rows]}"
    )
    assert second.id != first.id  # the ids differ, so the assertion can discriminate


def test_outbox_is_ordered_and_resumable(repo, raw):
    for index in range(5):
        repo.create_issue(Issue(title=f"issue {index}"))

    everything = outbox_pending(raw)
    seqs = [row[0] for row in everything]
    assert seqs == sorted(seqs)

    midpoint = seqs[2]
    assert [row[0] for row in outbox_pending(raw, after_seq=midpoint)] == seqs[3:]


# --- the ledger ------------------------------------------------------------


def test_record_and_read_back(raw):
    record_uid(raw, "issue_tag", 7, "s256t128:abc")
    raw.commit()
    assert get_uid(raw, "issue_tag", 7) == "s256t128:abc"
    assert get_uid(raw, "issue_tag", 8) is None


def test_recording_the_same_row_twice_updates_rather_than_duplicates(raw):
    record_uid(raw, "issue_tag", 7, "s256t128:one")
    record_uid(raw, "issue_tag", 7, "s256t128:two")
    raw.commit()
    assert get_uid(raw, "issue_tag", 7) == "s256t128:two"
    assert raw.execute("SELECT COUNT(*) FROM sync_row").fetchone()[0] == 1


def test_a_tombstone_keeps_the_uid(raw):
    """Absence must never mean deletion, so the entry is kept, not removed.

    A `git checkout` can make rows vanish that nobody deleted. Only an explicit
    tombstone deletes — which requires the tombstone to still be there.
    """
    record_uid(raw, "issues", 3, "s256t128:gone")
    raw.commit()

    assert tombstone(raw, "issues", 3) is True
    raw.commit()

    assert raw.execute("SELECT COUNT(*) FROM sync_row").fetchone()[0] == 1
    assert get_uid(raw, "issues", 3) == "s256t128:gone"
    assert resolve_uid(raw, "s256t128:gone") == []
    assert resolve_uid(raw, "s256t128:gone", include_deleted=True) == [3]


def test_tombstoning_twice_reports_that_it_did_nothing(raw):
    """An operation that succeeds without changing anything must say so."""
    record_uid(raw, "issues", 3, "s256t128:gone")
    raw.commit()
    assert tombstone(raw, "issues", 3) is True
    raw.commit()
    assert tombstone(raw, "issues", 3) is False
    assert tombstone(raw, "issues", 999) is False


# --- shared uids -----------------------------------------------------------


def test_collisions_are_reported_not_merged(raw):
    record_uid(raw, "issue_relation", 1, "s256t128:shared")
    record_uid(raw, "issue_relation", 2, "s256t128:shared")
    record_uid(raw, "issue_relation", 3, "s256t128:alone")
    raw.commit()

    collisions = find_uid_collisions(raw)
    assert collisions == [
        UidCollision(uid="s256t128:shared", entity="issue_relation", local_ids=[1, 2])
    ]


def test_a_clean_database_reports_no_collisions(raw):
    """The negative case, so a broken query cannot pass by returning nothing.

    find_uid_collisions returning [] must mean 'none', not 'the query is
    wrong' — which is why the positive case above exists alongside it.
    """
    record_uid(raw, "issue_relation", 1, "s256t128:one")
    record_uid(raw, "issue_relation", 2, "s256t128:two")
    raw.commit()
    assert find_uid_collisions(raw) == []


def test_a_tombstoned_row_does_not_collide_with_a_live_one(raw):
    record_uid(raw, "issue_relation", 1, "s256t128:shared")
    record_uid(raw, "issue_relation", 2, "s256t128:shared")
    raw.commit()
    tombstone(raw, "issue_relation", 1)
    raw.commit()
    assert find_uid_collisions(raw) == []


def test_bidirectional_relations_really_do_derive_one_uid(repo, raw):
    """The reproduction that forced the non-unique index, end to end.

    Both link_issues calls succeed today — UNIQUE(source, target, type) does
    not stop them because the tuples differ — so a real database can hold two
    rows that the symmetric rule maps to a single uid.
    """
    from issuedb.sync import relation_uid

    first = repo.create_issue(Issue(title="A"))
    second = repo.create_issue(Issue(title="B"))
    repo.link_issues(first.id, second.id, "relates_to")
    repo.link_issues(second.id, first.id, "relates_to")

    rows = list(
        raw.execute("SELECT id, source_issue_id, target_issue_id FROM issue_relations ORDER BY id")
    )
    assert len(rows) == 2, "both directions must coexist, or this repo has changed"

    symmetric = ["relates_to"]
    uids = {
        relation_uid("p", f"i{row[1]}", "relates_to", f"i{row[2]}", symmetric_types=symmetric)
        for row in rows
    }
    assert len(uids) == 1, "the two directions must derive ONE uid under the symmetric rule"

    for row in rows:
        record_uid(raw, "issue_relation", row[0], next(iter(uids)))
    raw.commit()

    collisions = find_uid_collisions(raw, entity="issue_relation")
    assert len(collisions) == 1
    assert collisions[0].local_ids == [rows[0][0], rows[1][0]]
