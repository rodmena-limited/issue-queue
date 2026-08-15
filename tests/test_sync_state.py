"""Cursor and replica state — stored outside the database, on purpose."""

from __future__ import annotations

import json

import pytest

from issuedb.sync._state import (
    INITIAL_CURSOR,
    SyncState,
    load,
    new_replica_id,
    reset,
    save,
    state_path,
)

PROJECT = "s256t128:project"
OTHER_PROJECT = "s256t128:different"


@pytest.fixture
def env(tmp_path):
    return {"XDG_CONFIG_HOME": str(tmp_path / "config"), "HOME": str(tmp_path / "home")}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "repo" / ".issue.db"
    path.parent.mkdir(parents=True)
    path.touch()
    return path


# --- where it lives -------------------------------------------------------


def test_state_is_not_written_into_the_database(db, env):
    before = db.read_bytes()
    save(SyncState(str(db), PROJECT, "r1", "c:5", 3), env)
    assert db.read_bytes() == before, "the database was modified by saving sync state"


def test_state_lives_under_xdg_config_home(db, env):
    save(SyncState(str(db), PROJECT, "r1", "c:5", 3), env)
    assert state_path(env).exists()
    assert str(state_path(env)).startswith(env["XDG_CONFIG_HOME"])


def test_state_is_keyed_by_resolved_database_path(db, env):
    """./x and /full/x are one entry, or a relative invocation loses the cursor."""
    save(SyncState(str(db), PROJECT, "r1", "c:5", 3), env)
    data = json.loads(state_path(env).read_text())
    assert str(db.resolve()) in data


def test_two_databases_keep_separate_cursors(tmp_path, env):
    first = tmp_path / "a.db"
    second = tmp_path / "b.db"
    first.touch()
    second.touch()
    save(SyncState(str(first), PROJECT, "r1", "c:5", 1), env)
    save(SyncState(str(second), PROJECT, "r2", "c:9", 2), env)

    assert load(first, PROJECT, env).cursor == "c:5"
    assert load(second, PROJECT, env).cursor == "c:9"


# --- round trip -----------------------------------------------------------


def test_a_database_with_no_state_starts_from_zero(db, env):
    state = load(db, PROJECT, env)
    assert state.cursor == INITIAL_CURSOR
    assert state.last_pushed_seq == 0
    assert state.replica_id


def test_state_round_trips(db, env):
    save(SyncState(str(db), PROJECT, "replica-a", "c:42", 7), env)
    state = load(db, PROJECT, env)
    assert state.cursor == "c:42"
    assert state.replica_id == "replica-a"
    assert state.last_pushed_seq == 7


# --- the guard that stops a misapplied cursor -----------------------------


def test_a_cursor_from_a_different_project_is_discarded(db, env):
    """Paths get reused: delete a repo, clone another to the same directory.

    Applying the old cursor would skip every change the new project made
    before this replica existed — silently, because the client would believe
    it was up to date.
    """
    save(SyncState(str(db), PROJECT, "replica-a", "c:42", 7), env)

    state = load(db, OTHER_PROJECT, env)

    assert state.cursor == INITIAL_CURSOR, "a foreign cursor was applied"
    assert state.last_pushed_seq == 0
    assert state.project_uid == OTHER_PROJECT


def test_the_matching_project_still_gets_its_cursor(db, env):
    """The negative control for the test above.

    Without this, an implementation that discarded EVERY cursor would pass
    the discard test while making sync re-seed on every run.
    """
    save(SyncState(str(db), PROJECT, "replica-a", "c:42", 7), env)
    assert load(db, PROJECT, env).cursor == "c:42"


# --- replica identity -----------------------------------------------------


def test_replica_ids_are_unique(db, env):
    assert len({new_replica_id() for _ in range(200)}) == 200


def test_a_replica_id_survives_reload(db, env):
    first = load(db, PROJECT, env)
    save(first, env)
    assert load(db, PROJECT, env).replica_id == first.replica_id


def test_a_fresh_database_gets_a_new_replica_id(tmp_path, env):
    """Two clones must not claim one identity.

    If the replica id lived in a tracked .issue.db, every clone would come up
    as the same replica and their cursors would interleave under one name.
    """
    first = tmp_path / "clone-a.db"
    second = tmp_path / "clone-b.db"
    first.touch()
    second.touch()
    assert load(first, PROJECT, env).replica_id != load(second, PROJECT, env).replica_id


# --- reset ----------------------------------------------------------------


def test_reset_forces_a_reseed(db, env):
    save(SyncState(str(db), PROJECT, "r", "c:42", 7), env)
    assert reset(db, env) is True
    assert load(db, PROJECT, env).cursor == INITIAL_CURSOR


def test_reset_reports_when_there_was_nothing_to_reset(db, env):
    assert reset(db, env) is False


def test_reset_leaves_other_databases_alone(tmp_path, env):
    first = tmp_path / "a.db"
    second = tmp_path / "b.db"
    first.touch()
    second.touch()
    save(SyncState(str(first), PROJECT, "r1", "c:5", 1), env)
    save(SyncState(str(second), PROJECT, "r2", "c:9", 2), env)

    reset(first, env)

    assert load(first, PROJECT, env).cursor == INITIAL_CURSOR
    assert load(second, PROJECT, env).cursor == "c:9"


# --- corruption -----------------------------------------------------------


def test_a_corrupt_state_file_costs_a_reseed_not_a_crash(db, env):
    """Unlike a corrupt credential file, this is safe to recover from.

    The cursor is a cache; losing it costs a re-pull, and re-application is
    idempotent by uid. Failing hard here would strand a user whose only fault
    was a truncated write.
    """
    path = state_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ truncated")
    assert load(db, PROJECT, env).cursor == INITIAL_CURSOR


def test_no_temporary_files_are_left_behind(db, env):
    save(SyncState(str(db), PROJECT, "r", "c:1", 1), env)
    leftovers = [p.name for p in state_path(env).parent.iterdir() if p.name.startswith(".")]
    assert leftovers == []
