"""Pushing must not break applying, and must not mint a second identity.

issuedb #31 — two defects from one line, both shipped, both found by
`tracker-fbe1b4` running the same six-line probe twice.

`build_entries` writes minted uids to the ledger, which opens an implicit
transaction. `apply` then issues its own ``BEGIN IMMEDIATE`` and sqlite raises
"cannot start a transaction within a transaction". The whole apply rolls back,
taking the ledger writes with it. So on any sync that ALSO had something to
push:

    * NOTHING WAS APPLIED, while the run still printed "Pushed N";
    * the ledger stayed empty, so the next push minted FRESH uids for the same
      rows and the server grew a duplicate set every time.

Their measurement: two pushes of one local row produced two server rows and left
``sync_row`` at 0.

Every existing test synced ONCE against a server with nothing to pull, which is
the one shape where neither symptom appears.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.repository import IssueRepository
from issuedb.sync import _sync_command
from issuedb.sync._credentials import Credential
from issuedb.sync._project_file import write_project_file
from tests.test_sync_pagination import PROJECT, FakePagingClient


class RecordingClient(FakePagingClient):
    """Serves `total` changes to apply, and records every push."""

    def __init__(self, total=3, size=200):
        super().__init__(total=total, size=size)
        self.pushed: list[list[str]] = []

    def push(self, entries, replica_id):
        self.pushed.append([e["uid"] for e in entries])
        return [
            {"uid": e["uid"], "entity": e["entity"], "outcome": "created"} for e in entries
        ]


@pytest.fixture
def wired(monkeypatch, tmp_path):
    monkeypatch.setattr(
        _sync_command, "load",
        lambda server, env=None: Credential(
            server_url=server, key_id="01testkeyid00000000000000", secret="s3cr3t"
        ),
    )
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}


@pytest.fixture
def db_with_local_row(tmp_path):
    path = tmp_path / ".issue.db"
    IssueRepository(str(path))
    Database._instances.clear()
    write_project_file(str(path), PROJECT, "https://example.invalid")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO issues (title) VALUES ('written locally')")
    conn.commit()
    conn.close()
    return str(path)


def _count(path, table):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
    finally:
        conn.close()


def _sync(path, wired, monkeypatch, client):
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)
    return _sync_command.sync(path, "https://example.invalid", do_apply=True, env=wired)


def test_a_sync_that_pushes_also_applies(db_with_local_row, wired, monkeypatch, capsys):
    """The severe half: apply silently did nothing whenever push had work."""
    client = RecordingClient(total=3)
    _sync(db_with_local_row, wired, monkeypatch, client)

    out = capsys.readouterr()
    assert "cannot start a transaction" not in out.err
    assert "Applied 3 change(s)" in out.out, (
        "the pull half applied nothing on a sync that also had something to push"
    )
    # 3 from the server + the 1 written locally.
    assert _count(db_with_local_row, "issues") == 4


def test_the_minted_uid_survives_the_sync(db_with_local_row, wired, monkeypatch):
    """The ledger write must outlive apply's transactions, or identity is lost."""
    _sync(db_with_local_row, wired, monkeypatch, RecordingClient(total=3))
    assert _count(db_with_local_row, "sync_row") > 0, (
        "the ledger was empty after a push; the next sync will mint new uids"
    )


def test_pushing_twice_sends_the_same_uid(db_with_local_row, wired, monkeypatch):
    """The duplication, stated as the property that was violated."""
    first = RecordingClient(total=3)
    _sync(db_with_local_row, wired, monkeypatch, first)
    local_uid = first.pushed[0][0]

    # Touch the row so it is offered again, rather than relying on the echo.
    conn = sqlite3.connect(db_with_local_row)
    conn.execute("UPDATE issues SET title = 'renamed' WHERE title = 'written locally'")
    conn.commit()
    conn.close()

    second = RecordingClient(total=0)
    _sync(db_with_local_row, wired, monkeypatch, second)
    assert second.pushed, "the edited row was never offered again"
    assert second.pushed[0][0] == local_uid, (
        "the same local row was pushed under a second uid — the server now has two"
    )


def test_an_applied_change_is_not_pushed_straight_back(db_with_local_row, wired, monkeypatch):
    """Applying writes to a local table, which fires the outbox triggers.

    Without a guard every pulled row is offered back on the next sync: a round
    trip nobody asked for, and a version bump on rows nobody edited.
    """
    _sync(db_with_local_row, wired, monkeypatch, RecordingClient(total=3))

    second = RecordingClient(total=0)
    _sync(db_with_local_row, wired, monkeypatch, second)
    assert second.pushed == [], (
        f"rows just applied from the server were pushed back: {second.pushed}"
    )


def test_the_echo_guard_does_not_swallow_a_real_edit(db_with_local_row, wired, monkeypatch):
    """Control: the guard above must not simply stop pushing everything."""
    _sync(db_with_local_row, wired, monkeypatch, RecordingClient(total=3))

    conn = sqlite3.connect(db_with_local_row)
    conn.execute("INSERT INTO issues (title) VALUES ('genuinely new')")
    conn.commit()
    conn.close()

    third = RecordingClient(total=0)
    _sync(db_with_local_row, wired, monkeypatch, third)
    assert third.pushed, "a genuine local edit made after a sync was never pushed"


@pytest.fixture
def empty_clone(tmp_path):
    """A fresh clone: project binding, empty database — the commonest first sync."""
    path = tmp_path / ".issue.db"
    IssueRepository(str(path))
    Database._instances.clear()
    write_project_file(str(path), PROJECT, "https://example.invalid")
    return str(path)


def test_a_fresh_clone_settles_on_the_first_sync(empty_clone, wired, monkeypatch):
    """issuedb #33 — the echo guard never ran when there was nothing to push.

    `_finish_push` sat inside `if entries:`. A fresh clone has nothing local, so
    the guard was skipped entirely: apply wrote every row, the outbox triggers
    recorded an echo for each, the mark never moved, and the NEXT sync offered
    the whole project back.

    `tracker-fbe1b4` measured it as "runs 1 and 2 each re-pushed the full 313".
    Harmless — the uids are right and the server answers idempotently — but
    every replica pays for the entire project on the wire before it settles.
    """
    _sync(empty_clone, wired, monkeypatch, RecordingClient(total=20))

    second = RecordingClient(total=0)
    _sync(empty_clone, wired, monkeypatch, second)
    assert second.pushed == [], (
        f"a fresh clone offered its freshly-applied rows back: {second.pushed}"
    )


def test_the_fresh_clone_guard_still_pushes_a_real_edit(empty_clone, wired, monkeypatch):
    """Control: the guard above must not be 'never push after a clone'."""
    _sync(empty_clone, wired, monkeypatch, RecordingClient(total=20))

    conn = sqlite3.connect(empty_clone)
    conn.execute("INSERT INTO issues (title) VALUES ('written after the clone')")
    conn.commit()
    conn.close()

    second = RecordingClient(total=0)
    _sync(empty_clone, wired, monkeypatch, second)
    assert second.pushed, "an edit made after a fresh clone was never pushed"
