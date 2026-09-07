"""The project identity recorded inside ``.issue.db``.

``project_uid`` is the one piece of sync state that belongs IN the database
rather than beside it, and the reasoning is the mirror image of the cursor's.
A cursor is per-replica and mutable, so a tracked file would make it
time-travel with the branch. The project id is neither: it is the same for
every clone forever, it is server-minted, and it carries nothing secret.

THIS TABLE IS THE RUNTIME COPY, NOT THE ONE THAT TRAVELS. An earlier version of
this docstring said being committed was a feature — "a fresh clone of a tracked
repo knows which project it belongs to with zero setup" — which assumed
``.issue.db`` was itself committed. Nothing ever told users to commit it and
issuedb's own ``.gitignore`` forbids it, so the promise was never kept
(issuedb #28). The database is binary and unmergeable, and sharing issues is
what sync is for, so committing it was the wrong mechanism for the right goal.
The identity that travels now lives in a tracked ``.issuedb-project.json`` —
see :mod:`issuedb.sync._project_file`.

It is also load-bearing for correctness, not just convenience. From the frozen
canonical form, ``project_uid`` is FIELD 1 of every derived uid::

    issue_tag         "itag", project_uid, issue_uid, tag_name
    issue_dependency  "idep", project_uid, blocker_uid, blocked_uid
    issue_relation    "irel", project_uid, source_uid, relation_type, target_uid

Deriving with an empty string or a placeholder produces uids that differ from
the server's, and the rows then silently fail to converge — two rows where one
was meant, in both databases, with nothing erroring. That is why
:func:`require_project_uid` REFUSES rather than substituting a default: a
missing project id must stop the sync, not quietly change what a uid means.

Write-once. If the server ever reports a different project for a database that
already holds one, this database belongs to a different project — a path was
reused, a clone was repointed, or a key was swapped — and continuing would
merge two projects' rows. It raises instead.

Standard library only.
"""

from __future__ import annotations

import sqlite3
from typing import Any


class ProjectIdentityError(Exception):
    """The database's project identity is missing or contradicts the server."""


def create_project_table(cursor: Any) -> None:
    """Create the single-row table holding this database's project identity.

    ``id INTEGER PRIMARY KEY CHECK (id = 1)`` makes "at most one project per
    database" a schema constraint rather than a convention someone has to
    remember. A second project cannot be inserted even by a direct sqlite3
    write, which matters because that is a supported way to touch this file.
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_project (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            project_uid TEXT NOT NULL,
            server_url TEXT NOT NULL,
            recorded_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)


def get_project_uid(conn: sqlite3.Connection) -> str | None:
    """The recorded project uid, or None if this database has never synced."""
    try:
        row = conn.execute("SELECT project_uid FROM sync_project WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        # The table predates this migration. Not an error: an unsynced
        # database legitimately has no project.
        return None
    return None if row is None else str(row[0])


def get_server_url(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute("SELECT server_url FROM sync_project WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else str(row[0])


def record_project_uid(conn: sqlite3.Connection, project_uid: str, server_url: str) -> bool:
    """Record the project identity. Returns True if this call recorded it.

    Idempotent for the SAME uid, so a second sync is not an error. A
    DIFFERENT uid raises: the database already belongs to a project, and
    adopting a new one would merge two projects' rows under one identity.

    Raises:
        ProjectIdentityError: a different project is already recorded, or the
            uid is empty.
    """
    if not project_uid:
        raise ProjectIdentityError(
            "refusing to record an empty project_uid. The server did not supply one — "
            "check the API key is project-bound, since an unscoped key names no project."
        )

    existing = get_project_uid(conn)
    if existing is not None:
        if existing == project_uid:
            return False
        raise ProjectIdentityError(
            f"this database belongs to project {existing}, but the server reported "
            f"{project_uid}. Refusing to sync: adopting a new project id would merge "
            f"two projects' rows under one identity. If this checkout really should "
            f"follow a different project, start from a fresh .issue.db."
        )

    conn.execute(
        "INSERT INTO sync_project (id, project_uid, server_url) VALUES (1, ?, ?)",
        (project_uid, server_url),
    )
    return True


def require_project_uid(conn: sqlite3.Connection) -> str:
    """The project uid, or raise. Never returns a placeholder.

    Callers deriving a uid must use this rather than ``get_project_uid() or
    ""``. An empty field 1 hashes perfectly happily and produces a uid the
    server will never agree with, so the failure would be silent divergence
    rather than an error.
    """
    project_uid = get_project_uid(conn)
    if not project_uid:
        raise ProjectIdentityError(
            "no project_uid recorded for this database, so no uid can be derived — "
            "project_uid is field 1 of every derived uid, and deriving without it "
            "would produce uids the server never agrees with. Run a sync first: the "
            "authenticated handshake supplies it."
        )
    return project_uid
