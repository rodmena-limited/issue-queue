"""Applying pulled changes to the local database.

This is the direction that can destroy work existing nowhere else, so the
tests are written around the refusals rather than the features:

* a dry run changes NOTHING — asserted against the rows, not the return value;
* ABSENCE NEVER DELETES — a uid missing from a page leaves its row alone;
* the cursor advances only to what was DURABLY committed;
* an interrupted apply converges on re-run rather than duplicating.

Every destructive path has a test that fails if the guard is removed. The
manager's condition was "prove the destructive paths RED before trusting
them", and a guard whose removal breaks nothing is not a guard.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.models import Issue
from issuedb.repository import IssueRepository
from issuedb.sync._apply import (
    AMBIGUOUS,
    CREATE,
    DELETE,
    SKIP,
    already_applied,
    apply,
    plan,
    render_plan,
)
from issuedb.sync._ledger import record_uid, resolve_uid

UID_A = "s256t128:" + "a" * 32
UID_B = "s256t128:" + "b" * 32
UID_C = "s256t128:" + "c" * 32


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


def _change(uid, seq=1, title="from server", deleted=False, entity="issue"):
    return {
        "uid": uid,
        "entity": entity,
        "seq": seq,
        "version": 1,
        "deleted": deleted,
        "payload": {"title": title},
    }


def _issue_count(conn):
    return conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]


# --- the dry run changes nothing ------------------------------------------


def test_plan_does_not_touch_the_database(repo, conn):
    """Asserted against the ROWS, not against plan()'s return value.

    A plan that quietly wrote and then described what it wrote would satisfy
    any assertion about its output.
    """
    existing = repo.create_issue(Issue(title="local work"))
    record_uid(conn, "issues", existing.id, UID_A)
    conn.commit()
    before = conn.execute("SELECT id, title, status FROM issues ORDER BY id").fetchall()

    plan(conn, [_change(UID_A, title="server would rename this"), _change(UID_B)])

    assert conn.execute("SELECT id, title, status FROM issues ORDER BY id").fetchall() == before


def test_the_dry_run_report_says_nothing_changed(repo, conn):
    actions = plan(conn, [_change(UID_B)])
    report = render_plan(actions, applying=False)
    assert "DRY RUN" in report
    assert "nothing has been changed" in report
    assert "--apply" in report


def test_the_apply_report_does_not_claim_to_be_a_dry_run(repo, conn):
    actions = plan(conn, [_change(UID_B)])
    assert "DRY RUN" not in render_plan(actions, applying=True)


# --- absence never deletes -------------------------------------------------


def test_a_uid_absent_from_the_page_is_left_alone(repo, conn):
    """The finding this whole design rests on.

    A uid missing from a pulled page means "not on this page". Treating it as
    deleted would remove a colleague's work on the strength of pagination,
    with nothing erroring.
    """
    keep = repo.create_issue(Issue(title="must survive"))
    record_uid(conn, "issues", keep.id, UID_A)
    conn.commit()

    # A page that mentions a DIFFERENT uid entirely.
    actions = plan(conn, [_change(UID_B)])
    apply(conn, actions, "c:0")
    conn.commit()

    assert repo.get_issue(keep.id) is not None, "an absent uid deleted a local row"
    assert [a.kind for a in actions] == [CREATE]


def test_an_empty_page_deletes_nothing(repo, conn):
    keep = repo.create_issue(Issue(title="must survive"))
    record_uid(conn, "issues", keep.id, UID_A)
    conn.commit()

    actions = plan(conn, [])
    result = apply(conn, actions, "c:7")
    conn.commit()

    assert _issue_count(conn) == 1
    assert result.applied == 0
    assert result.cursor == "c:7", "an empty page advanced the cursor"


# --- only an explicit tombstone deletes ------------------------------------


def test_an_explicit_tombstone_deletes(repo, conn):
    """The positive control for the two tests above.

    Without it, an implementation that never deleted anything would pass every
    absence test while making tombstones inert — deletions would silently stop
    propagating and every replica would keep rows the server considers gone.
    """
    doomed = repo.create_issue(Issue(title="deleted upstream"))
    record_uid(conn, "issues", doomed.id, UID_A)
    conn.commit()

    actions = plan(conn, [_change(UID_A, deleted=True)])
    assert [a.kind for a in actions] == [DELETE]

    apply(conn, actions, "c:0")
    conn.commit()

    assert repo.get_issue(doomed.id) is None


def test_a_tombstone_keeps_the_ledger_entry(repo, conn):
    """The ledger must outlive the row, or the deletion cannot propagate."""
    doomed = repo.create_issue(Issue(title="deleted upstream"))
    record_uid(conn, "issues", doomed.id, UID_A)
    conn.commit()

    apply(conn, plan(conn, [_change(UID_A, deleted=True)]), "c:0")
    conn.commit()

    assert resolve_uid(conn, UID_A) == []
    assert resolve_uid(conn, UID_A, include_deleted=True) == [doomed.id]


def test_a_tombstone_for_an_unknown_row_is_a_skip_not_an_error(repo, conn):
    actions = plan(conn, [_change(UID_C, deleted=True)])
    assert [a.kind for a in actions] == [SKIP]
    assert apply(conn, actions, "c:0").failed == 0


# --- create and update -----------------------------------------------------


def test_a_new_uid_is_created_and_ledgered(repo, conn):
    actions = plan(conn, [_change(UID_B, seq=4, title="new from server")])
    assert [a.kind for a in actions] == [CREATE]

    result = apply(conn, actions, "c:0")
    conn.commit()

    assert result.applied == 1
    assert result.cursor == "c:4"
    rows = conn.execute("SELECT id, title FROM issues").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "new from server"
    assert resolve_uid(conn, UID_B) == [rows[0][0]]


def test_a_known_uid_is_updated_not_duplicated(repo, conn):
    existing = repo.create_issue(Issue(title="old title"))
    record_uid(conn, "issues", existing.id, UID_A)
    conn.commit()

    apply(conn, plan(conn, [_change(UID_A, title="new title")]), "c:0")
    conn.commit()

    assert _issue_count(conn) == 1
    assert conn.execute("SELECT title FROM issues").fetchone()[0] == "new title"


# --- the cursor ------------------------------------------------------------


def test_the_cursor_advances_only_to_the_last_durable_change(repo, conn):
    actions = plan(conn, [_change(UID_A, seq=3), _change(UID_B, seq=9)])
    result = apply(conn, actions, "c:0")
    conn.commit()
    assert result.cursor == "c:9"


def test_a_failure_stops_the_run_and_does_not_advance_past_it(repo, conn, monkeypatch):
    """The rule that stops rows being skipped forever.

    A cursor advanced past a failed apply means nothing ever asks for those
    rows again, and no error is raised at any later point.
    """
    import issuedb.sync._apply as apply_module

    real = apply_module._apply_one
    calls = {"n": 0}

    def fail_on_second(conn_, action):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk full")
        return real(conn_, action)

    monkeypatch.setattr(apply_module, "_apply_one", fail_on_second)

    actions = plan(conn, [_change(UID_A, seq=3), _change(UID_B, seq=9), _change(UID_C, seq=12)])
    result = apply_module.apply(conn, actions, "c:0")
    conn.commit()

    assert result.applied == 1
    assert result.failed == 1
    assert result.cursor == "c:3", "the cursor advanced past a change that failed"
    assert "disk full" in (result.stopped_at or "")
    assert _issue_count(conn) == 1, "the third change was attempted after a failure"


def test_a_failed_action_leaves_no_partial_row(repo, conn, monkeypatch):
    import issuedb.sync._apply as apply_module

    def always_fail(conn_, action):
        conn_.execute("INSERT INTO issues (title) VALUES ('half written')")
        raise RuntimeError("boom")

    monkeypatch.setattr(apply_module, "_apply_one", always_fail)
    apply_module.apply(conn, plan(conn, [_change(UID_A)]), "c:0")
    conn.commit()

    assert _issue_count(conn) == 0, "a failed action left a partially written row"


# --- ambiguity -------------------------------------------------------------


def test_an_ambiguous_uid_is_not_applied(repo, conn):
    first = repo.create_issue(Issue(title="one"))
    second = repo.create_issue(Issue(title="two"))
    record_uid(conn, "issues", first.id, UID_A)
    record_uid(conn, "issues", second.id, UID_A)
    conn.commit()

    actions = plan(conn, [_change(UID_A, title="server version")])
    assert [a.kind for a in actions] == [AMBIGUOUS]

    apply(conn, actions, "c:0")
    conn.commit()

    titles = {row[0] for row in conn.execute("SELECT title FROM issues")}
    assert titles == {"one", "two"}, "an ambiguous uid was applied to a chosen row"


def test_the_cursor_does_not_advance_past_an_ambiguous_change(repo, conn):
    """Otherwise the user is never asked about it again."""
    first = repo.create_issue(Issue(title="one"))
    second = repo.create_issue(Issue(title="two"))
    record_uid(conn, "issues", first.id, UID_A)
    record_uid(conn, "issues", second.id, UID_A)
    conn.commit()

    actions = plan(conn, [_change(UID_A, seq=5), _change(UID_B, seq=8)])
    result = apply(conn, actions, "c:1")

    assert result.cursor == "c:1"
    assert "ambiguous" in (result.stopped_at or "")


# --- interrupt safety ------------------------------------------------------


def test_re_running_after_an_interrupt_converges(repo, conn, monkeypatch):
    """Killed mid-apply, the re-run must converge — not duplicate, not skip.

    Tested by actually interrupting the first run rather than reasoning about
    idempotency: the ledger entry written by the successful action is what
    makes the re-run see UPDATE instead of a second CREATE.
    """
    import issuedb.sync._apply as apply_module

    real = apply_module._apply_one
    calls = {"n": 0}

    def die_on_second(conn_, action):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt("user hit ctrl-c")
        return real(conn_, action)

    monkeypatch.setattr(apply_module, "_apply_one", die_on_second)
    changes = [_change(UID_A, seq=3, title="first"), _change(UID_B, seq=9, title="second")]

    with pytest.raises(KeyboardInterrupt):
        apply_module.apply(conn, plan(conn, changes), "c:0")
    conn.commit()

    assert _issue_count(conn) == 1

    # Re-run with the real implementation, from the cursor we durably reached.
    monkeypatch.setattr(apply_module, "_apply_one", real)
    result = apply_module.apply(conn, plan(conn, changes), "c:3")
    conn.commit()

    assert _issue_count(conn) == 2, "the re-run duplicated or skipped"
    assert result.cursor == "c:9"
    titles = {row[0] for row in conn.execute("SELECT title FROM issues")}
    assert titles == {"first", "second"}


def test_already_applied_sees_a_tombstoned_uid(repo, conn):
    """A deleted uid is still KNOWN, or a re-pull resurrects it."""
    doomed = repo.create_issue(Issue(title="gone"))
    record_uid(conn, "issues", doomed.id, UID_A)
    conn.commit()
    apply(conn, plan(conn, [_change(UID_A, deleted=True)]), "c:0")
    conn.commit()

    assert already_applied(conn, UID_A) is True
    assert already_applied(conn, UID_C) is False


# --- entities we do not apply ----------------------------------------------


def test_an_unsupported_entity_is_reported_not_silently_dropped(repo, conn):
    actions = plan(conn, [_change(UID_A, entity="issue_tag")])
    assert [a.kind for a in actions] == [SKIP]
    assert "not applied yet" in actions[0].reason
    assert "issue_tag" in render_plan(actions, applying=True)
