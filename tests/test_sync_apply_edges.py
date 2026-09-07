"""Applying pulled issue_relation and issue_dependency changes.

These are the two entity types the apply path used to skip. A relation or
dependency is defined by the issues it relates, so its local row references
them by LOCAL id while the server payload names them by UID — the endpoints
must be resolved before the row can be written, and a missing endpoint is a
SKIP, never a crash and never a dangling foreign key.

The destructive paths carry the same refusals as issues: absence never deletes,
the cursor advances only to what was durably committed, and a re-run converges
rather than duplicating.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._apply import CREATE, DELETE, MALFORMED, SKIP, UPDATE, plan
from issuedb.sync._ledger import record_uid, resolve_uid
from issuedb.sync._run import apply

UID_A = "s256t128:" + "a" * 32
UID_B = "s256t128:" + "b" * 32
UID_R = "s256t128:" + "r" * 32
UID_D = "s256t128:" + "d" * 32


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


def _issue(repo, conn, uid, title):
    """Create a local issue and record its uid in the ledger."""
    issue = repo.create_issue(Issue(title=title))
    record_uid(conn, "issues", issue.id, uid)
    conn.commit()  # release the write lock, or apply's BEGIN IMMEDIATE blocks
    return issue.id


def _relation(uid=UID_R, source=UID_A, target=UID_B, rel_type="relates_to",
              deleted=False, seq=1):
    return {
        "uid": uid,
        "entity": "issue_relation",
        "seq": seq,
        "version": 1,
        "deleted": deleted,
        "payload": {"source": source, "type": rel_type, "target": target},
    }


def _issue_change(uid, seq, title):
    return {
        "uid": uid,
        "entity": "issue",
        "seq": seq,
        "version": 1,
        "deleted": False,
        "payload": {"title": title},
    }


def _dependency(uid=UID_D, blocker=UID_A, blocked=UID_B, deleted=False, seq=1):
    return {
        "uid": uid,
        "entity": "issue_dependency",
        "seq": seq,
        "version": 1,
        "deleted": deleted,
        "payload": {"blocker": blocker, "blocked": blocked},
    }


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# --- plan: relations -------------------------------------------------------


def test_plan_a_relation_create_resolves_endpoints(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    actions = plan(conn, [_relation()])
    assert [x.kind for x in actions] == [CREATE]
    # The plan carries the endpoint UIDs; the apply resolves them to local ids.
    assert actions[0].endpoints == (UID_A, UID_B)
    assert actions[0].relation_type == "relates_to"


def test_plan_a_relation_whose_endpoint_is_in_the_feed_is_not_skipped(repo, conn):
    """The plan is computed for the whole feed before anything is applied, so a
    relation whose endpoint issues are IN this feed cannot resolve them against
    the database yet. It must know they are coming, or every relation in a real
    sync would be skipped."""
    feed = [
        _issue_change(UID_A, seq=1, title="A"),
        _issue_change(UID_B, seq=2, title="B"),
        _relation(seq=3),
    ]
    actions = plan(conn, feed)
    rel = [a for a in actions if a.entity == "issue_relation"]
    assert [a.kind for a in rel] == [CREATE], "the feed creates the endpoints, so not a SKIP"


def test_apply_a_relation_whose_endpoint_is_in_the_feed(repo, conn):
    """End to end: the feed creates A and B, then the relation, and the apply
    resolves the endpoints to the just-created issues."""
    feed = [
        _issue_change(UID_A, seq=1, title="A"),
        _issue_change(UID_B, seq=2, title="B"),
        _relation(seq=3),
    ]
    result = apply(conn, plan(conn, feed), "c:0")
    assert result.applied == 3
    assert _count(conn, "issue_relations") == 1
    row = conn.execute(
        "SELECT source_issue_id, target_issue_id FROM issue_relations"
    ).fetchone()
    a_id = resolve_uid(conn, UID_A)[0]
    b_id = resolve_uid(conn, UID_B)[0]
    assert row == (a_id, b_id)


def test_plan_a_relation_with_a_missing_endpoint_is_skipped(repo, conn):
    _issue(repo, conn, UID_A, "A")  # B is absent
    actions = plan(conn, [_relation()])
    assert [x.kind for x in actions] == [SKIP]
    assert "endpoint issue has not arrived yet" in actions[0].reason


def test_plan_a_relation_with_a_bad_payload_is_malformed(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    change = _relation()
    change["payload"] = {"source": UID_A}  # missing type and target
    actions = plan(conn, [change])
    assert [x.kind for x in actions] == [MALFORMED]


def test_plan_a_relation_tombstone_deletes(repo, conn):
    a = _issue(repo, conn, UID_A, "A")
    b = _issue(repo, conn, UID_B, "B")
    # The relation already exists locally, ledgered under UID_R.
    cur = conn.execute(
        "INSERT INTO issue_relations (source_issue_id, target_issue_id, relation_type) "
        "VALUES (?, ?, ?)",
        (a, b, "relates_to"),
    )
    record_uid(conn, "issue_relations", cur.lastrowid, UID_R)
    actions = plan(conn, [_relation(deleted=True)])
    assert [x.kind for x in actions] == [DELETE]


# --- plan: dependencies ----------------------------------------------------


def test_plan_a_dependency_create_resolves_endpoints(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    actions = plan(conn, [_dependency()])
    assert [x.kind for x in actions] == [CREATE]
    assert actions[0].endpoints == (UID_A, UID_B)


def test_plan_a_dependency_with_a_missing_endpoint_is_skipped(repo, conn):
    _issue(repo, conn, UID_A, "A")
    actions = plan(conn, [_dependency()])
    assert [x.kind for x in actions] == [SKIP]
    assert "endpoint issue has not arrived yet" in actions[0].reason


def test_plan_a_dependency_with_a_bad_payload_is_malformed(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    change = _dependency()
    change["payload"] = {"blocker": UID_A}  # missing blocked
    actions = plan(conn, [change])
    assert [x.kind for x in actions] == [MALFORMED]


# --- apply: relations ------------------------------------------------------


def test_apply_a_relation_create_writes_the_row_and_ledgers_it(repo, conn):
    a = _issue(repo, conn, UID_A, "A")
    b = _issue(repo, conn, UID_B, "B")
    result = apply(conn, plan(conn, [_relation()]), "c:0")
    assert result.applied == 1
    assert _count(conn, "issue_relations") == 1
    row = conn.execute(
        "SELECT id, source_issue_id, target_issue_id, relation_type FROM issue_relations"
    ).fetchone()
    assert row[1:] == (a, b, "relates_to")
    # The relation's own id is what the ledger records, so a re-pull of the
    # same uid resolves to it.
    assert resolve_uid(conn, UID_R) == [row[0]]


def test_apply_a_relation_delete_tombstones_and_removes(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    apply(conn, plan(conn, [_relation()]), "c:0")
    rid = conn.execute("SELECT id FROM issue_relations").fetchone()[0]
    result = apply(conn, plan(conn, [_relation(deleted=True)]), "c:1")
    assert result.applied == 1
    assert _count(conn, "issue_relations") == 0
    # The ledger entry survives, tombstoned — absence must never mean deletion.
    assert resolve_uid(conn, UID_R, include_deleted=True) == [rid]


def test_apply_a_relation_update_converges_the_direction(repo, conn):
    """A symmetric relation can arrive with the endpoints reversed; the server's
    direction is authoritative, so the local row converges to it."""
    a = _issue(repo, conn, UID_A, "A")
    b = _issue(repo, conn, UID_B, "B")
    apply(conn, plan(conn, [_relation(source=UID_A, target=UID_B)]), "c:0")
    # Same uid, endpoints reversed (symmetric type sorts them in the uid).
    result = apply(conn, plan(conn, [_relation(source=UID_B, target=UID_A)]), "c:1")
    assert result.applied == 1
    row = conn.execute(
        "SELECT source_issue_id, target_issue_id FROM issue_relations"
    ).fetchone()
    assert row == (b, a), "the local direction converged to the server's"


def test_apply_a_relation_re_run_converges_not_duplicates(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    apply(conn, plan(conn, [_relation()]), "c:0")
    # Re-planning the same change sees UPDATE, not a second CREATE.
    actions = plan(conn, [_relation()])
    assert [x.kind for x in actions] == [UPDATE]
    apply(conn, actions, "c:1")
    assert _count(conn, "issue_relations") == 1


# --- apply: dependencies ---------------------------------------------------


def test_apply_a_dependency_create_writes_the_row_and_ledgers_it(repo, conn):
    a = _issue(repo, conn, UID_A, "A")
    b = _issue(repo, conn, UID_B, "B")
    result = apply(conn, plan(conn, [_dependency()]), "c:0")
    assert result.applied == 1
    assert _count(conn, "issue_dependencies") == 1
    row = conn.execute(
        "SELECT blocker_id, blocked_id FROM issue_dependencies"
    ).fetchone()
    assert row == (a, b)


def test_apply_a_dependency_delete_tombstones_and_removes(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    apply(conn, plan(conn, [_dependency()]), "c:0")
    did = conn.execute("SELECT id FROM issue_dependencies").fetchone()[0]
    result = apply(conn, plan(conn, [_dependency(deleted=True)]), "c:1")
    assert result.applied == 1
    assert _count(conn, "issue_dependencies") == 0
    assert resolve_uid(conn, UID_D, include_deleted=True) == [did]


def test_apply_a_dependency_re_run_converges_not_duplicates(repo, conn):
    _issue(repo, conn, UID_A, "A")
    _issue(repo, conn, UID_B, "B")
    apply(conn, plan(conn, [_dependency()]), "c:0")
    actions = plan(conn, [_dependency()])
    assert [x.kind for x in actions] == [UPDATE]
    apply(conn, actions, "c:1")
    assert _count(conn, "issue_dependencies") == 1
