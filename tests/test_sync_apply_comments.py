"""Comments must arrive, not only depart.

`tracker-fbe1b4` measured the asymmetry after we shipped comment PUSH: 119
comments reached the server, and the pull half still said
``issuedb does not apply entity 'comment' yet``. A comment written in Tracker's
web UI could not reach a laptop.

Their framing is why this got built immediately rather than filed: *"push is
one direction of two, and the direction that is still missing is the one an
operator notices when a colleague comments in the browser."*
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._apply import CREATE, MALFORMED, SKIP, UPDATE, apply, plan
from issuedb.sync._ledger import record_uid

UID_ISSUE = "s256t128:" + "a" * 32
UID_COMMENT = "s256t128:" + "c" * 32
ENTITIES = frozenset({"issue", "comment", "issue_tag", "issue_dependency", "issue_relation"})


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


def _issue(repo, conn, uid=UID_ISSUE, title="parent"):
    issue = repo.create_issue(Issue(title=title))
    record_uid(conn, "issues", issue.id, uid)
    conn.commit()
    return issue.id


def _comment(uid=UID_COMMENT, issue_uid=UID_ISSUE, text="from the browser", seq=1):
    return {
        "uid": uid,
        "entity": "comment",
        "seq": seq,
        "deleted": False,
        "content_hash": f"h{seq}",
        "payload": {"issue_uid": issue_uid, "text": text},
    }


def test_a_comment_from_the_server_lands_locally(repo, conn):
    issue_id = _issue(repo, conn)
    actions = plan(conn, [_comment()], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [CREATE], [a.reason for a in actions]

    apply(conn, actions, "c:0")
    rows = conn.execute("SELECT issue_id, text FROM comments").fetchall()
    assert rows == [(issue_id, "from the browser")], (
        "a comment written on the server never reached the local database"
    )


def test_a_second_sync_updates_rather_than_duplicating(repo, conn):
    _issue(repo, conn)
    apply(conn, plan(conn, [_comment()], server_entities=ENTITIES), "c:0")
    apply(
        conn,
        plan(conn, [_comment(text="edited on the server", seq=2)], server_entities=ENTITIES),
        "c:1",
    )
    rows = conn.execute("SELECT text FROM comments").fetchall()
    assert rows == [("edited on the server",)], "re-applying a comment duplicated it"


def test_the_second_sync_really_is_an_update(repo, conn):
    """Control: if the second plan said CREATE, the test above would still pass
    only because a UNIQUE constraint happened to exist. It does not."""
    _issue(repo, conn)
    apply(conn, plan(conn, [_comment()], server_entities=ENTITIES), "c:0")
    actions = plan(conn, [_comment(text="edited", seq=2)], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [UPDATE]


def test_a_comment_on_an_unknown_issue_is_skipped_not_written(repo, conn):
    """A dangling foreign key is worse than a missing comment."""
    actions = plan(conn, [_comment(issue_uid="s256t128:" + "f" * 32)], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [SKIP]
    assert "not present locally" in actions[0].reason
    apply(conn, actions, "c:0")
    assert conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0] == 0


def test_a_comment_with_no_text_is_malformed_not_written(repo, conn):
    """comments.text is NOT NULL; writing an empty one invents content."""
    _issue(repo, conn)
    bad = _comment()
    bad["payload"]["text"] = ""
    actions = plan(conn, [bad], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [MALFORMED]
    assert conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0] == 0


def test_a_comment_with_no_issue_uid_is_malformed(repo, conn):
    _issue(repo, conn)
    bad = _comment()
    del bad["payload"]["issue_uid"]
    actions = plan(conn, [bad], server_entities=ENTITIES)
    assert [a.kind for a in actions] == [MALFORMED]
    assert "belongs to no issue" in actions[0].reason


def test_a_comment_arriving_with_its_issue_in_one_feed(repo, conn):
    """The parent is created by the SAME feed, so it is not in the database when
    the comment is planned. The plan must look ahead, as it does for edges."""
    feed = [
        {"uid": UID_ISSUE, "entity": "issue", "seq": 1, "deleted": False,
         "content_hash": "h1", "payload": {"title": "created by this feed"}},
        _comment(seq=2),
    ]
    actions = plan(conn, feed, server_entities=ENTITIES)
    assert [a.kind for a in actions] == [CREATE, CREATE], [a.reason for a in actions]
    apply(conn, actions, "c:0")
    assert conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0] == 1
