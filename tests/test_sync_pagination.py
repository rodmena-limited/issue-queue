"""``sync`` must read the WHOLE feed, not the first page of it.

The client asked for one page and ignored ``has_more``. That was correct for
as long as every feed fit in one page, and it became wrong silently the moment
one did not: the user is told "Pulled 200 change(s)" and nothing whatsoever
about the remainder, and the dry run then describes a fraction of what
``--apply`` would do. Nothing errors, and the number shown is real — it is just
not the answer to the question the user asked.

Found against the live server: the first-contact probe reported "the entry
created by THIS RUN did not come back from pull" once the feed crossed 200
changes. The push was fine; the newest change was on the LAST page, which is
exactly the page a single read never sees. A false accusation against a correct
server, produced by a check that had been passing for hours.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.repository import IssueRepository
from issuedb.sync import _sync_command
from issuedb.sync._client import Handshake, PullResult
from issuedb.sync._credentials import Credential

FOUR = frozenset({"issue", "issue_tag", "issue_dependency", "issue_relation"})
PROJECT = "01TESTPROJECT0000000000000"


def _change(seq: int) -> dict[str, object]:
    return {
        "uid": f"s256t128:{seq:032x}",
        "entity": "issue",
        "seq": seq,
        "version": 1,
        "deleted": False,
        "content_hash": f"h{seq}",
        "payload": {"title": f"issue {seq}", "number": seq},
    }


class FakePagingClient:
    """Serves a feed in pages of `size`, exactly as the real server does."""

    def __init__(self, total: int, size: int) -> None:
        self.feed = [_change(i) for i in range(1, total + 1)]
        self.size = size
        self.pulls: list[str] = []

    def handshake(self) -> Handshake:
        return Handshake(
            protocol_min=1,
            protocol_max=1,
            project_uid=PROJECT,
            symmetric_relation_types=frozenset(),
            tombstone_retention_days=180,
            uid_algorithm="s256t128",
            raw={},
            authenticated=True,
            credential_rejected=False,
            entities=FOUR,
        )

    def pull(self, cursor: str) -> PullResult:
        self.pulls.append(cursor)
        after = int(cursor.split(":")[1])
        remaining = [c for c in self.feed if int(c["seq"]) > after]  # type: ignore[call-overload]
        page = remaining[: self.size]
        last = int(page[-1]["seq"]) if page else after  # type: ignore[call-overload]
        return PullResult(
            changes=page,
            cursor=f"c:{last}",
            has_more=len(remaining) > len(page),
            safe_horizon=None,
        )


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / ".issue.db")
    repository = IssueRepository(path)
    repository.db.close_connection()
    Database._instances.clear()
    yield path


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Point sync at a fake client and an isolated state/credential store."""
    monkeypatch.setattr(
        _sync_command, "load", lambda server, env=None: Credential(
            server_url=server, key_id="01testkeyid00000000000000", secret="s3cr3t"
        )
    )
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}


def test_sync_reads_every_page_not_just_the_first(db, wired, monkeypatch, capsys):
    """450 changes in pages of 200 must be reported as 450, not 200."""
    client = FakePagingClient(total=450, size=200)
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)

    assert _sync_command.sync(db, "https://example.invalid", do_apply=False, env=wired) == 0

    out = capsys.readouterr().out
    assert "Pulled 450 change(s) over 3 pages" in out, out
    assert client.pulls == ["c:0", "c:200", "c:400"], client.pulls


def test_a_single_page_feed_is_reported_without_a_page_count(db, wired, monkeypatch, capsys):
    """The control: the fix must not turn every ordinary sync into "over 1 pages"."""
    client = FakePagingClient(total=5, size=200)
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)

    assert _sync_command.sync(db, "https://example.invalid", do_apply=False, env=wired) == 0

    out = capsys.readouterr().out
    assert "Pulled 5 change(s) from cursor c:0" in out, out
    assert "pages" not in out
    assert client.pulls == ["c:0"]


def test_apply_lands_every_page_and_the_cursor_reaches_the_end(db, wired, monkeypatch, capsys):
    """The half that actually matters: rows from page 3 must exist locally.

    Asserting only the printed count would pass against a client that reads
    every page and applies the first.
    """
    client = FakePagingClient(total=450, size=200)
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)

    assert _sync_command.sync(db, "https://example.invalid", do_apply=True, env=wired) == 0

    conn = sqlite3.connect(db)
    try:
        titles = {r[0] for r in conn.execute("SELECT title FROM issues")}
    finally:
        conn.close()

    assert "issue 1" in titles, "page 1 did not land"
    assert "issue 250" in titles, "page 2 did not land"
    assert "issue 450" in titles, "PAGE 3 DID NOT LAND — the feed was truncated"

    out = capsys.readouterr().out
    assert "Cursor now c:450" in out, out


def test_a_server_that_never_lowers_has_more_is_bounded_and_says_so(
    db, wired, monkeypatch, capsys
):
    """An unbounded loop is not a fix. A partial run must never read as complete."""

    class Endless(FakePagingClient):
        def pull(self, cursor: str) -> PullResult:
            super().pull(cursor)  # records the cursor in self.pulls
            seq = int(cursor.split(":")[1]) + 1
            return PullResult(
                changes=[_change(seq)], cursor=f"c:{seq}", has_more=True, safe_horizon=None
            )

    monkeypatch.setattr(_sync_command, "MAX_PULL_PAGES", 5)
    client = Endless(total=10, size=1)
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)

    assert _sync_command.sync(db, "https://example.invalid", do_apply=False, env=wired) == 0

    captured = capsys.readouterr()
    assert len(client.pulls) == 5
    assert "stopped after 5 pages" in captured.err, captured.err
    assert "only part of the feed" in captured.err
