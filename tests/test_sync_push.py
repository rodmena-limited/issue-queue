"""Sync must send local changes, not only receive them.

issuedb #14. Reported from outside by `tracker-fbe1b4`: `SyncClient.push` was
fully written and had no caller anywhere in the package, so no issue created in
a developer's `.issue.db` could ever reach Tracker.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.sync import _sync_command
from issuedb.sync._credentials import Credential
from issuedb.sync._project_file import write_project_file
from issuedb.sync._push import build_entries, collapse_outbox
from tests.test_sync_pagination import PROJECT, FakePagingClient


@pytest.fixture
def wired(monkeypatch, tmp_path):
    monkeypatch.setattr(
        _sync_command,
        "load",
        lambda server, env=None: Credential(
            server_url=server, key_id="01testkeyid00000000000000", secret="s3cr3t"
        ),
    )
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / ".issue.db"
    Database(str(path))
    write_project_file(str(path), PROJECT, "https://example.invalid")
    return str(path)


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


class PushRecordingClient(FakePagingClient):
    """A client that records what it was asked to send."""

    def __init__(self, total=0, size=200, outcome="created"):
        super().__init__(total=total, size=size)
        self.pushed: list[list[dict]] = []
        self.outcome = outcome

    def push(self, entries, replica_id):
        self.pushed.append(entries)
        return [
            {"uid": e["uid"], "entity": e["entity"], "outcome": self.outcome}
            for e in entries
        ]


def test_a_locally_created_issue_is_offered_to_the_server(db, wired, monkeypatch, capsys):
    conn = _conn(db)
    conn.execute("INSERT INTO issues (title) VALUES ('travels to the server')")
    conn.commit()
    conn.close()

    client = PushRecordingClient()
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)
    rc = _sync_command.sync(db, "https://example.invalid", do_apply=True, env=wired)

    assert rc == 0
    assert client.pushed, "sync applied and pushed nothing — the send half never ran"
    sent = [e for batch in client.pushed for e in batch]
    titles = [e["payload"].get("title") for e in sent if e["entity"] == "issue"]
    assert "travels to the server" in titles


def test_a_dry_run_reports_the_outbound_half_without_sending(db, wired, monkeypatch, capsys):
    conn = _conn(db)
    conn.execute("INSERT INTO issues (title) VALUES ('not sent yet')")
    conn.commit()
    conn.close()

    client = PushRecordingClient()
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)
    _sync_command.sync(db, "https://example.invalid", do_apply=False, env=wired)

    out = capsys.readouterr().out
    assert "WOULD PUSH" in out
    assert client.pushed == [], "a dry run sent data to the server"


def test_a_rejected_entry_does_not_advance_the_mark(db, wired, monkeypatch, capsys):
    """A per-uid rejection inside a 200 is not success."""
    conn = _conn(db)
    conn.execute("INSERT INTO issues (title) VALUES ('will be rejected')")
    conn.commit()
    conn.close()

    client = PushRecordingClient(outcome="rejected")
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)
    rc = _sync_command.sync(db, "https://example.invalid", do_apply=True, env=wired)

    assert rc == 1
    assert "REJECTED" in capsys.readouterr().err

    # And the change is offered again rather than lost.
    client2 = PushRecordingClient()
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client2)
    _sync_command.sync(db, "https://example.invalid", do_apply=True, env=wired)
    assert client2.pushed, "a rejected change was never retried"


def test_an_issue_keeps_one_uid_across_edits(db, wired, monkeypatch):
    conn = _conn(db)
    conn.execute("INSERT INTO issues (title) VALUES ('one identity')")
    conn.commit()
    conn.close()

    c = _conn(db)
    try:
        entries, _, _ = build_entries(c, PROJECT, 0)
        c.commit()
    finally:
        c.close()
    first = [e["uid"] for e in entries if e["entity"] == "issue"][0]

    conn = _conn(db)
    conn.execute("UPDATE issues SET title = 'renamed' WHERE title = 'one identity'")
    conn.commit()
    conn.close()

    c = _conn(db)
    try:
        entries2, _, _ = build_entries(c, PROJECT, 0)
        c.commit()
    finally:
        c.close()
    second = [e["uid"] for e in entries2 if e["entity"] == "issue"][0]
    assert first == second, "editing an issue changed its identity"


def test_issue_tags_are_refused_rather_than_pushed_wrongly(db, wired, monkeypatch):
    """#13: the ledger cannot hold two tag uids for one issue, so tags must not travel."""
    conn = _conn(db)
    conn.execute("INSERT INTO issues (title) VALUES ('tagged')")
    conn.execute("INSERT INTO tags (name) VALUES ('bug')")
    conn.execute("INSERT INTO issue_tags (issue_id, tag_id) VALUES (1, 1)")
    conn.commit()
    conn.close()

    c = _conn(db)
    try:
        entries, _, skipped = build_entries(c, PROJECT, 0)
        c.commit()
    finally:
        c.close()
    assert not [e for e in entries if e["entity"] == "issue_tag"]
    assert "issue_tags" in skipped


def test_three_edits_collapse_to_one_entry():
    """The outbox is an event log; the server wants current state."""
    rows = [
        {"seq": 1, "entity": "issues", "local_id": 7, "op": "insert"},
        {"seq": 2, "entity": "issues", "local_id": 7, "op": "update"},
        {"seq": 3, "entity": "issues", "local_id": 7, "op": "update"},
        {"seq": 4, "entity": "issues", "local_id": 9, "op": "insert"},
    ]
    collapsed = collapse_outbox(rows)
    assert len(collapsed) == 2
    assert collapsed[0]["op"] == "update", "the last event for a row must win"
