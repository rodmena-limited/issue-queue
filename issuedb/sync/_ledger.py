"""The sync_row uid ledger and the sync_outbox change feed.

Two tables, and the reasons for their shape are not obvious.

**sync_row has NO FOREIGN KEYS.** Every other child table in issuedb declares
``REFERENCES issues(id) ON DELETE CASCADE``, and the ledger deliberately does
not. A ledger entry must OUTLIVE the row it describes: when an issue is
deleted, the fact that uid X existed and is now gone is precisely what the
server needs, and a cascade would delete that fact along with the row. A
tombstone that gets cascaded away is a deletion that never propagates, and the
row comes back on the next sync from any replica that still has it.

**sync_row does NOT declare uid UNIQUE.** This is the constraint that took a
live reproduction to find. ``link_issues(A, B, 'relates_to')`` and
``link_issues(B, A, 'relates_to')`` both succeed today — ``UNIQUE(source,
target, type)`` does not stop them because the tuples differ — so a database
written before uids existed can already hold two rows that derive ONE uid
under the symmetric rule. A ``UNIQUE`` here would make the backfill fail on
real user data, and "fixing" that with ``INSERT OR IGNORE`` would silently
drop one of the two rows. Neither is acceptable, so the ledger records both
and :func:`find_uid_collisions` reports them.

**sync_outbox is written by TRIGGERS, not by the repository layer.** issuedb
has three write paths that do not share code: the CLI, the Flask UI, and a
user with ``sqlite3`` and a shell. There is a fourth — an OLDER INSTALLED
issuedb writing to the same file, which is normal here because 22 of 42 repos
in this estate commit ``.issue.db`` to git. A trigger fires for all of them.
An outbox maintained in Python would be silently incomplete for exactly the
writes nobody remembered to instrument.

Standard library only.
"""

from __future__ import annotations

import sqlite3
from typing import Any, NamedTuple

# Tables whose changes are fed to the outbox, with the column holding the
# owning issue where there is one. Order matters only for readability.
TRACKED_TABLES: dict[str, str | None] = {
    "issues": None,
    "comments": "issue_id",
    "code_references": "issue_id",
    "issue_tags": "issue_id",
    "issue_dependencies": None,
    "issue_relations": None,
    "issue_links": None,
    "time_entries": "issue_id",
    "tags": None,
    "memory": None,
    "lessons_learned": None,
}


class UidCollision(NamedTuple):
    """Two or more pre-existing rows that derive the same uid."""

    uid: str
    entity: str
    local_ids: list[int]


def create_alias_table(cursor: Any) -> None:
    """The issue-number alias table.

    Two clones of a repo that commits ``.issue.db`` allocate from the same
    AUTOINCREMENT counter independently, so both mint a different issue
    numbered 3. When they sync, the server keeps the first as canonical and
    records the loser's number as an alias — it cannot renumber it, because
    ``parse_issue_refs`` resolves ``#3`` out of commit messages already
    immutable in git history.

    KEYED BY UID, not by number. Keyed by number the table would have the very
    collision it exists to resolve. ``(replica_id, local_number)`` are
    attributes, and lookup by number returns a SET.

    No foreign keys, for the same reason as ``sync_row``: an alias must
    outlive the row so a historical ``#3`` in a five-year-old commit still
    resolves to something.
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issue_number_alias (
            uid TEXT NOT NULL,
            local_number INTEGER NOT NULL,
            replica_id TEXT NOT NULL,
            canonical_number INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (uid, local_number, replica_id)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_alias_local_number "
        "ON issue_number_alias(local_number)"
    )


def record_alias(
    conn: sqlite3.Connection,
    uid: str,
    local_number: int,
    replica_id: str,
    canonical_number: int | None = None,
) -> None:
    """Record that ``uid`` was numbered ``local_number`` on ``replica_id``."""
    conn.execute(
        """
        INSERT INTO issue_number_alias (uid, local_number, replica_id, canonical_number)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(uid, local_number, replica_id)
        DO UPDATE SET canonical_number = excluded.canonical_number
        """,
        (uid, local_number, replica_id, canonical_number),
    )


def aliases_for_number(conn: sqlite3.Connection, local_number: int) -> list[Any]:
    """Every alias claiming this local number. Deliberately a list."""
    return list(
        conn.execute(
            """
            SELECT uid, local_number, replica_id, canonical_number
            FROM issue_number_alias WHERE local_number = ?
            ORDER BY uid
            """,
            (local_number,),
        )
    )


def create_sync_tables(cursor: Any) -> None:
    """Create the ledger and the outbox. Idempotent."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_row (
            entity TEXT NOT NULL,
            local_id INTEGER NOT NULL,
            uid TEXT NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (entity, local_id)
        )
    """)
    # NOT unique, deliberately: pre-existing bidirectional relations derive a
    # shared uid, and refusing them would fail the backfill on real data.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_row_uid ON sync_row(uid)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_row_deleted ON sync_row(deleted) WHERE deleted = 1"
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_outbox (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            local_id INTEGER,
            op TEXT NOT NULL,
            recorded_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_outbox_entity ON sync_outbox(entity)")


def create_change_triggers(cursor: Any, tables: dict[str, str | None] | None = None) -> None:
    """Install INSERT/UPDATE/DELETE triggers feeding sync_outbox.

    Triggers rather than application code, because the CLI, the Flask UI, a
    raw ``sqlite3`` session and an older installed issuedb all write to this
    file and share no Python. See the module docstring.

    ``issue_tags`` has no ``id`` column — its primary key is ``(issue_id,
    tag_id)`` — so its outbox rows carry ``issue_id`` as ``local_id`` and the
    push side resolves the membership from it. Recording NULL would produce an
    outbox entry naming a change nobody can locate.
    """
    for table, _issue_col in (tables or TRACKED_TABLES).items():
        if not _table_exists(cursor, table):
            # A table absent in this database (an older file mid-ladder) is
            # skipped rather than failing the migration.
            continue
        key = "issue_id" if table == "issue_tags" else "id"
        for op, alias in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
            cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS sync_outbox_{table}_{op.lower()}
                AFTER {op} ON {table}
                BEGIN
                    INSERT INTO sync_outbox (entity, local_id, op)
                    VALUES ('{table}', {alias}.{key}, '{op.lower()}');
                END
            """)


def _table_exists(cursor: Any, name: str) -> bool:
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return bool(cursor.fetchone()[0])


def record_uid(
    conn: sqlite3.Connection, entity: str, local_id: int, uid: str, deleted: bool = False
) -> None:
    """Record (or update) a row's uid in the ledger."""
    conn.execute(
        """
        INSERT INTO sync_row (entity, local_id, uid, deleted) VALUES (?, ?, ?, ?)
        ON CONFLICT(entity, local_id) DO UPDATE SET uid = excluded.uid, deleted = excluded.deleted
        """,
        (entity, local_id, uid, int(deleted)),
    )


def tombstone(conn: sqlite3.Connection, entity: str, local_id: int) -> bool:
    """Mark a ledger entry deleted, KEEPING the uid.

    The entry is never removed. Absence must never mean deletion — a
    ``git checkout`` can make rows vanish that nobody deleted, so only an
    explicit tombstone deletes, in both directions.

    Returns True if an entry was tombstoned, False if none existed.
    """
    cursor = conn.execute(
        "UPDATE sync_row SET deleted = 1 WHERE entity = ? AND local_id = ? AND deleted = 0",
        (entity, local_id),
    )
    return cursor.rowcount > 0


def get_uid(conn: sqlite3.Connection, entity: str, local_id: int) -> str | None:
    """The uid recorded for a row, or None if it is not in the ledger."""
    row = conn.execute(
        "SELECT uid FROM sync_row WHERE entity = ? AND local_id = ?", (entity, local_id)
    ).fetchone()
    return None if row is None else str(row[0])


def resolve_uid(conn: sqlite3.Connection, uid: str, include_deleted: bool = False) -> list[int]:
    """Every local id carrying this uid.

    Returns a LIST, deliberately, and it may hold more than one member. A
    database written before uids existed can contain two rows deriving one
    uid, and the caller must decide what to do about that rather than being
    handed an arbitrary winner. Selecting one silently is how a reference
    starts pointing at somebody else's row with nothing erroring.
    """
    query = "SELECT local_id FROM sync_row WHERE uid = ?"
    if not include_deleted:
        query += " AND deleted = 0"
    return [int(row[0]) for row in conn.execute(query + " ORDER BY local_id", (uid,))]


def find_uid_collisions(conn: sqlite3.Connection, entity: str | None = None) -> list[UidCollision]:
    """Rows sharing a uid — reported, never silently merged.

    Expected to be non-empty on databases that predate uids: bidirectional
    ``relates_to`` pairs are legal today and derive one uid under the
    symmetric rule. The backfill calls this and surfaces what it found; it
    does not resolve it, because merging two relations means choosing which
    ``created_at`` to destroy and which direction the user did not mean.
    """
    query = """
        SELECT uid, entity, GROUP_CONCAT(local_id) FROM sync_row
        WHERE deleted = 0
    """
    params: tuple[Any, ...] = ()
    if entity is not None:
        query += " AND entity = ?"
        params = (entity,)
    query += " GROUP BY uid, entity HAVING COUNT(*) > 1 ORDER BY uid"

    return [
        UidCollision(uid=row[0], entity=row[1], local_ids=sorted(int(i) for i in row[2].split(",")))
        for row in conn.execute(query, params)
    ]


def outbox_pending(conn: sqlite3.Connection, after_seq: int = 0, limit: int = 1000) -> list[Any]:
    """Outbox entries after ``after_seq``, oldest first."""
    return list(
        conn.execute(
            """
            SELECT seq, entity, local_id, op, recorded_at FROM sync_outbox
            WHERE seq > ? ORDER BY seq LIMIT ?
            """,
            (after_seq, limit),
        )
    )
