"""Forward-only schema migration ladder for IssueDB.

Before this module the only migration tool was ``_add_column_if_missing``:
every process re-derived "what is missing?" by inspecting the live schema on
every open. That works for adding a nullable column and for nothing else. It
cannot express a data backfill, it cannot express a change that must happen
exactly once, and it has no way to notice that a database was written by a
newer issuedb than the code reading it.

The ladder replaces the inspection with a recorded number. ``PRAGMA
user_version`` holds the schema version; migrations are applied in ascending
order, each inside its own transaction, and the version is advanced in the
same transaction as the change it describes. A crash therefore leaves the
database at a version that is true, never half-applied.

Two properties are worth stating because they are what the rest of the
project will lean on:

* **Forward only.** There is no down-migration. A rollback path that is never
  exercised is a rollback path that does not work, and restoring a file is a
  better answer for a single-file SQLite database than replaying inverse DDL.
* **A newer database is refused, not tolerated.** If ``user_version`` exceeds
  what this code knows about, the file was written by a later issuedb whose
  schema this code cannot interpret. Opening it read-write anyway is how a
  ``.issue.db`` shared through git gets silently corrupted by whichever
  machine has the older install.

Standard library only, per the project's zero-dependency rule.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Callable

# A migration is (version, name, apply). ``version`` is the value written to
# PRAGMA user_version once ``apply`` returns. Names exist for error messages
# and for the operator reading a failure at 3am.
Migration = tuple[int, str, Callable[[sqlite3.Cursor], None]]

# Version 1 is the BASELINE: the schema as created by ``initialize_schema``.
# Databases that predate the ladder carry user_version 0 while already having
# every baseline table, so they are stamped to 1 rather than migrated to it.
BASELINE_VERSION = 1

# The ladder. Append only; never renumber and never edit an entry that has
# shipped, because some database somewhere has already recorded that it ran.
MIGRATIONS: list[Migration] = []

# The version this code targets. Derived from the ladder so the two can never
# disagree — a hand-maintained constant beside a list is a constant that will
# eventually be wrong.
SCHEMA_VERSION = max([BASELINE_VERSION, *(version for version, _, _ in MIGRATIONS)])


class MigrationError(Exception):
    """Base class for ladder failures."""


class NewerDatabaseError(MigrationError):
    """The database was written by a newer issuedb than this code.

    Raised instead of proceeding: this code cannot know what the newer schema
    means, and writing to it with older assumptions is how data is lost.
    """

    def __init__(self, found: int, supported: int) -> None:
        self.found = found
        self.supported = supported
        super().__init__(
            f"This database is at schema version {found}, but this issuedb "
            f"supports up to {supported}. It was written by a newer issuedb. "
            f"Upgrade issuedb (pip install -U issuedb) rather than continuing: "
            f"writing to it with older assumptions can lose data."
        )


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the database's recorded schema version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Write the schema version.

    PRAGMA does not accept bound parameters, so the value is interpolated —
    hence the assertion. ``version`` only ever comes from the ladder above,
    but an int check costs nothing and makes that guarantee local.
    """
    if not isinstance(version, int) or isinstance(version, bool):
        raise TypeError(f"schema version must be an int, got {version!r}")
    conn.execute(f"PRAGMA user_version = {version:d}")


def _has_baseline_tables(conn: sqlite3.Connection) -> bool:
    """Whether this file already holds the baseline schema.

    Used to tell a brand-new database apart from one that predates the
    ladder. Both report user_version 0; only the latter has tables.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='issues'"
    ).fetchone()
    return bool(row[0])


def apply_migrations(
    conn: sqlite3.Connection,
    migrations: Sequence[Migration] | None = None,
    target: int | None = None,
) -> int:
    """Bring ``conn`` up to ``target``, and return the version it ends at.

    Each migration runs inside ``BEGIN IMMEDIATE`` together with the
    ``user_version`` bump, so a failure rolls back both and the recorded
    version never describes a change that did not land.

    IMMEDIATE (rather than DEFERRED) takes the write lock up front. Two
    processes opening the same ``.issue.db`` at once is normal for this
    project — a CLI invocation while the Flask UI is running — and the
    version is re-read under that lock so the loser of the race observes the
    winner's work instead of repeating it.

    Args:
        conn: An open connection. Any in-flight implicit transaction is
            committed first, since a migration cannot begin inside one.
        migrations: Ladder to apply. Defaults to the module ladder; tests
            inject their own so the machinery is exercised even when the
            shipped ladder is empty.
        target: Highest version to apply. Defaults to the ladder's top.

    Returns:
        The schema version the database is at when this returns.

    Raises:
        NewerDatabaseError: The file is ahead of this code.
    """
    ladder = list(MIGRATIONS if migrations is None else migrations)
    ladder.sort(key=lambda entry: entry[0])

    if target is None:
        target = max([BASELINE_VERSION, *(version for version, _, _ in ladder)])

    # A migration cannot start inside a transaction, and callers reach this
    # from inside ``get_connection``, which may have one open.
    conn.commit()

    current = get_schema_version(conn)
    if current > target:
        raise NewerDatabaseError(found=current, supported=target)

    # Explicit transaction control. pysqlite's implicit handling would
    # otherwise decide for us where a transaction starts, which is precisely
    # the decision that must be exact here.
    previous_isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        if current == 0:
            current = _stamp_baseline(conn)

        for version, name, apply in ladder:
            if version <= current:
                continue
            if version > target:
                break
            current = _apply_one(conn, version, name, apply, current)
    finally:
        conn.isolation_level = previous_isolation

    return current


def _stamp_baseline(conn: sqlite3.Connection) -> int:
    """Record that a version-0 database is at the baseline.

    A database predating the ladder already HAS the baseline schema — it was
    created by ``initialize_schema`` — so the baseline is stamped, never
    re-applied. Re-running baseline DDL against a populated file is the one
    move here that could destroy data, so it is the one move this function
    does not make.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-read under the write lock: another process may have stamped it
        # between our unlocked read and this one.
        live = get_schema_version(conn)
        if live != 0:
            conn.execute("ROLLBACK")
            return live
        if not _has_baseline_tables(conn):
            # A genuinely empty file. initialize_schema runs before the
            # ladder, so this means the caller invoked the ladder alone;
            # stamping anyway would claim tables exist that do not.
            conn.execute("ROLLBACK")
            return 0
        _set_schema_version(conn, BASELINE_VERSION)
        conn.execute("COMMIT")
        return BASELINE_VERSION
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _apply_one(
    conn: sqlite3.Connection,
    version: int,
    name: str,
    apply: Callable[[sqlite3.Cursor], None],
    current: int,
) -> int:
    """Apply a single migration, or observe that someone else already did."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        live = get_schema_version(conn)
        if live >= version:
            # Another process won the race and applied it. Not an error.
            conn.execute("ROLLBACK")
            return live
        apply(conn.cursor())
        _set_schema_version(conn, version)
        conn.execute("COMMIT")
        return version
    except BaseException as exc:
        conn.execute("ROLLBACK")
        if isinstance(exc, Exception):
            raise MigrationError(
                f"migration {version} ({name}) failed and was rolled back; "
                f"database remains at version {current}"
            ) from exc
        raise
