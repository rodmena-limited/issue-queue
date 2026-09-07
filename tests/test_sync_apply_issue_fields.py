"""An issue is more than its title.

issuedb #30, and the most damaging defect this client has shipped. The apply
path wrote `INSERT INTO issues (title)` and `UPDATE issues SET title`, so
`status` and `priority` fell to their SQL defaults — 'open' and 'medium'. Every
issue pulled from the server was silently reset, and the push half then sent
those defaults BACK, overwriting the server's own data.

Measured by `tracker-fbe1b4` on ONE sync of a fresh clone:

    status   'closed'      -> 'open'      x21
    status   'in-progress' -> 'open'      x4
    priority 'high'        -> 'medium'    x17
    priority 'critical'    -> 'medium'    x12

They traced it field by field on one issue — served 'critical', stored 'medium',
pushed back 'medium' — which is why this is a fix and not an investigation.

No test here caught it because every fixture asserted on titles.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.repository import IssueRepository
from issuedb.sync._apply import CREATE, MALFORMED, UPDATE, plan
from issuedb.sync._run import apply

UID = "s256t128:" + "a" * 32
ENTITIES = frozenset({"issue", "comment", "issue_tag", "issue_dependency", "issue_relation"})


@pytest.fixture
def conn(tmp_path):
    repo = IssueRepository(str(tmp_path / ".issue.db"))
    connection = sqlite3.connect(str(repo.db.db_path))
    yield connection
    connection.close()
    repo.db.close_connection()
    Database._instances.clear()


def _issue(status="closed", priority="critical", seq=1, uid=UID, title="served by tracker"):
    return {
        "uid": uid, "entity": "issue", "seq": seq, "deleted": False,
        "content_hash": f"h{seq}",
        "payload": {"title": title, "status": status, "priority": priority},
    }


def _row(conn):
    return conn.execute("SELECT title, status, priority FROM issues").fetchone()


def test_a_served_status_and_priority_are_stored(conn):
    apply(conn, plan(conn, [_issue()], server_entities=ENTITIES), "c:0")
    assert _row(conn) == ("served by tracker", "closed", "critical"), (
        "the server's status and priority were dropped and replaced by column defaults"
    )


def test_the_defaults_are_exactly_what_was_being_written(conn):
    """The control that makes the assertion above mean something.

    'open' and 'medium' are the column defaults, so a test asserting them would
    have passed against the broken build. This pins that the served values are
    NOT the defaults, or the test above proves nothing.
    """
    served = _issue()["payload"]
    assert served["status"] != "open"
    assert served["priority"] != "medium"


def test_an_update_carries_the_new_status(conn):
    apply(conn, plan(conn, [_issue()], server_entities=ENTITIES), "c:0")
    actions = plan(conn, [_issue(status="in-progress", seq=2)], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [UPDATE]
    apply(conn, actions, "c:1")
    assert _row(conn) == ("served by tracker", "in-progress", "critical"), (
        "an update dropped a field the server sent, or clobbered one it did not"
    )


def test_a_field_the_server_omits_leaves_the_local_value_alone(conn):
    """Absent is not 'reset me'. Coercing absence to a default is the bug."""
    apply(conn, plan(conn, [_issue()], server_entities=ENTITIES), "c:0")
    bare = _issue(seq=2)
    del bare["payload"]["status"]
    del bare["payload"]["priority"]
    apply(conn, plan(conn, [bare], server_entities=ENTITIES), "c:1")
    assert _row(conn) == ("served by tracker", "closed", "critical")


def test_an_unrecognised_status_stops_rather_than_falls_back(conn):
    """A value we cannot store must not be silently replaced by a default —
    that substitution is exactly how the fields were lost."""
    actions = plan(conn, [_issue(status="banana")], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [MALFORMED]
    assert "banana" in actions[0].reason
    apply(conn, actions, "c:0")
    assert conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 0


def test_an_unrecognised_priority_stops_too(conn):
    actions = plan(conn, [_issue(priority="urgent-ish")], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [MALFORMED]
    assert "urgent-ish" in actions[0].reason


def test_every_valid_status_and_priority_round_trips(conn):
    """The enum, exhaustively — a partial mapping is how one value gets lost."""
    from issuedb.models import Priority, Status

    feed = []
    for n, (status, priority) in enumerate(
        [(s.value, p.value) for s in Status for p in Priority], start=1
    ):
        feed.append(_issue(status, priority, seq=n, uid=f"s256t128:{n:032d}", title=f"i{n}"))
    actions = plan(conn, feed, server_entities=ENTITIES)
    assert all(a.kind == CREATE for a in actions), [a.reason for a in actions]
    apply(conn, actions, "c:0")

    stored = {t: (s, p) for t, s, p in conn.execute("SELECT title, status, priority FROM issues")}
    assert len(stored) == len(feed)
    for change in feed:
        payload = change["payload"]
        assert stored[payload["title"]] == (payload["status"], payload["priority"])
