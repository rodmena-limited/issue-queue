"""Tests for the forward-only schema migration ladder.

The shipped ladder is empty (baseline only), so a test suite that exercised
only ``MIGRATIONS`` would assert that nothing happens and pass no matter how
broken the machinery was. Every test here that checks the ladder DOES
something injects its own migrations, so the mechanism is exercised rather
than the current absence of work.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.database._migrations import (
    BASELINE_VERSION,
    SCHEMA_VERSION,
    MigrationError,
    NewerDatabaseError,
    apply_migrations,
    get_schema_version,
)
from issuedb.database._schema import initialize_schema


@pytest.fixture
def conn(tmp_path):
    """A baseline database, as initialize_schema leaves it, version unstamped."""
    connection = sqlite3.connect(str(tmp_path / "t.db"))
    initialize_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def _add_table(name: str):
    """A migration body that creates a table, so its effect is observable."""

    def apply(cursor: sqlite3.Cursor) -> None:
        cursor.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)")

    return apply


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row[0])


# --- baseline -------------------------------------------------------------


def test_database_predating_the_ladder_is_stamped_not_migrated(conn):
    """A version-0 file that already has tables is stamped to the baseline.

    Re-running baseline DDL over a populated file is the one move that could
    destroy data, so this asserts the rows survive rather than only that the
    version moved.
    """
    conn.execute("INSERT INTO issues (title) VALUES ('pre-existing work')")
    conn.commit()
    assert get_schema_version(conn) == 0

    assert apply_migrations(conn, migrations=[]) == BASELINE_VERSION
    assert get_schema_version(conn) == BASELINE_VERSION
    assert conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 1
    assert conn.execute("SELECT title FROM issues").fetchone()[0] == "pre-existing work"


def test_empty_file_is_not_stamped(tmp_path):
    """A file with no baseline tables is not claimed to be at the baseline.

    Stamping it would assert that tables exist which do not, and the next
    open would skip the DDL that creates them.
    """
    connection = sqlite3.connect(str(tmp_path / "empty.db"))
    try:
        assert apply_migrations(connection, migrations=[]) == 0
        assert get_schema_version(connection) == 0
    finally:
        connection.close()


def test_a_database_at_target_is_left_alone(conn):
    """Re-running the ladder is a no-op, not a repeat application."""
    apply_migrations(conn, migrations=[])
    calls = []

    def record(cursor: sqlite3.Cursor) -> None:  # pragma: no cover - must not run
        calls.append(1)

    ladder = [(BASELINE_VERSION, "already-applied", record)]
    assert apply_migrations(conn, migrations=ladder) == BASELINE_VERSION
    assert calls == []


# --- applying -------------------------------------------------------------


def test_migrations_apply_in_ascending_order(conn):
    """Order is by version number, not by list position."""
    order = []

    def note(tag: str):
        def apply(cursor: sqlite3.Cursor) -> None:
            order.append(tag)

        return apply

    ladder = [
        (4, "fourth", note("fourth")),
        (2, "second", note("second")),
        (3, "third", note("third")),
    ]
    assert apply_migrations(conn, migrations=ladder) == 4
    assert order == ["second", "third", "fourth"]
    assert get_schema_version(conn) == 4


def test_migration_effect_lands_and_version_advances(conn):
    ladder = [(2, "add sync_row", _add_table("sync_row"))]

    assert apply_migrations(conn, migrations=ladder) == 2
    assert _table_exists(conn, "sync_row")
    assert get_schema_version(conn) == 2


def test_only_pending_migrations_run(conn):
    """A database part-way up the ladder resumes, it does not restart."""
    ladder = [
        (2, "first", _add_table("step_two")),
        (3, "second", _add_table("step_three")),
    ]
    apply_migrations(conn, migrations=ladder[:1])
    assert get_schema_version(conn) == 2

    ran = []

    def should_not_run(cursor: sqlite3.Cursor) -> None:  # pragma: no cover
        ran.append(1)

    resumed = [(2, "first", should_not_run), (3, "second", _add_table("step_three"))]
    assert apply_migrations(conn, migrations=resumed) == 3
    assert ran == []
    assert _table_exists(conn, "step_three")


def test_target_caps_how_far_the_ladder_runs(conn):
    ladder = [
        (2, "two", _add_table("t_two")),
        (3, "three", _add_table("t_three")),
    ]
    assert apply_migrations(conn, migrations=ladder, target=2) == 2
    assert _table_exists(conn, "t_two")
    assert not _table_exists(conn, "t_three")


# --- failure --------------------------------------------------------------


def test_failed_migration_rolls_back_and_leaves_the_version_behind(conn):
    """The version must never describe a change that did not land.

    Asserts BOTH halves: the version stays put AND the partial effect is
    gone. Checking only the version would pass against an implementation
    that committed the DDL and failed to bump.
    """
    def half_then_fail(cursor: sqlite3.Cursor) -> None:
        cursor.execute("CREATE TABLE landed_before_failure (id INTEGER)")
        raise RuntimeError("migration blew up half way")

    apply_migrations(conn, migrations=[])
    ladder = [(2, "explodes", half_then_fail)]

    with pytest.raises(MigrationError) as excinfo:
        apply_migrations(conn, migrations=ladder)

    assert "explodes" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert get_schema_version(conn) == BASELINE_VERSION
    assert not _table_exists(conn, "landed_before_failure")


def test_a_later_migration_is_not_reached_after_a_failure(conn):
    reached = []

    def boom(cursor: sqlite3.Cursor) -> None:
        raise RuntimeError("no")

    def later(cursor: sqlite3.Cursor) -> None:  # pragma: no cover - must not run
        reached.append(1)

    ladder = [(2, "boom", boom), (3, "later", later)]
    with pytest.raises(MigrationError):
        apply_migrations(conn, migrations=ladder)
    assert reached == []


# --- a newer database -----------------------------------------------------


def test_a_newer_database_is_refused(conn):
    """Refusal is the point: this code cannot interpret a newer schema."""
    apply_migrations(conn, migrations=[])
    conn.execute("PRAGMA user_version = 999")
    conn.commit()

    with pytest.raises(NewerDatabaseError) as excinfo:
        apply_migrations(conn, migrations=[])

    assert excinfo.value.found == 999
    assert excinfo.value.supported == BASELINE_VERSION
    assert "newer issuedb" in str(excinfo.value)
    # Refused, not silently downgraded.
    assert get_schema_version(conn) == 999


def test_refusal_reaches_the_caller_through_database_open(tmp_path):
    """The guard must hold through the real open path, not only in isolation."""
    path = tmp_path / "newer.db"
    db = Database(str(path))
    assert db.schema_version == SCHEMA_VERSION

    with db.get_connection() as connection:
        connection.execute("PRAGMA user_version = 999")
    db.close_connection()
    Database._instances.clear()  # a new open, not the cached instance

    with pytest.raises(NewerDatabaseError):
        Database(str(path))
    Database._instances.clear()


# --- wiring ---------------------------------------------------------------


def test_a_fresh_database_opens_at_the_supported_version(tmp_path):
    db = Database(str(tmp_path / "fresh.db"))
    try:
        assert db.schema_version == SCHEMA_VERSION
        assert db.supported_schema_version == SCHEMA_VERSION
        assert SCHEMA_VERSION >= BASELINE_VERSION
    finally:
        db.close_connection()
        Database._instances.clear()


def test_reopening_does_not_change_the_version(tmp_path):
    path = str(tmp_path / "reopen.db")
    db = Database(path)
    first = db.schema_version
    db.close_connection()
    Database._instances.clear()

    db2 = Database(path)
    try:
        assert db2.schema_version == first
    finally:
        db2.close_connection()
        Database._instances.clear()


def test_shipped_ladder_is_consistent():
    """The ladder's invariants, checked on the real MIGRATIONS list.

    Guards the append-only rule: duplicate or descending versions would make
    'has this run?' unanswerable.
    """
    from issuedb.database._migrations import MIGRATIONS

    versions = [version for version, _, _ in MIGRATIONS]
    assert versions == sorted(versions), "ladder must be in ascending order"
    assert len(versions) == len(set(versions)), "duplicate migration versions"
    assert all(v > BASELINE_VERSION for v in versions), "migrations must exceed baseline"
    assert max([BASELINE_VERSION, *versions]) == SCHEMA_VERSION
