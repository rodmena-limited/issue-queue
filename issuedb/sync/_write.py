"""Executing one planned action against the database.

Split out of ``_apply`` under the 550-line cap (issuedb #24) when comment
support pushed it past the ratchet. The split is along a real seam: ``_apply``
DECIDES what should happen to each change and this module CARRIES IT OUT. The
decision is pure over the feed plus current state; the write is the only part
that mutates.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from issuedb.sync._endpoints import _resolve_endpoint
from issuedb.sync._kinds import CREATE, DELETE, UPDATE
from issuedb.sync._ledger import record_uid, tombstone

if TYPE_CHECKING:  # pragma: no cover
    from issuedb.sync._apply import Action

# Server entity name -> local table. The ledger records the LOCAL table name as
# its entity, so this mapping is part of identity, not a convenience.
ENTITY_TABLE = {
    "issue": "issues",
    "comment": "comments",
    "issue_relation": "issue_relations",
    "issue_dependency": "issue_dependencies",
}


def _apply_one(conn: sqlite3.Connection, action: Action) -> None:
    """The single-row write. Called inside a transaction by :func:`apply`."""
    table = ENTITY_TABLE[action.entity]

    # A relation/dependency cannot be written without its endpoints. The plan
    # always resolves them, so this is a guard against a programming error, not
    # a server condition — and it lets mypy narrow the Optional.
    endpoints = action.endpoints
    if action.entity != "issue" and endpoints is None:
        raise ValueError(f"{action.entity} action carries no resolved endpoints")
    if action.entity != "issue":
        assert endpoints is not None
        endpoint_ids = (
            _resolve_endpoint(conn, endpoints[0]),
            _resolve_endpoint(conn, endpoints[1]),
        )

    if action.kind == DELETE:
        # Tombstone the ledger entry BEFORE deleting the row: the ledger must
        # outlive the row, and doing it after would lose the record if the
        # delete succeeded and the process died.
        tombstone(conn, table, action.local_id)  # type: ignore[arg-type]
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (action.local_id,))
        return

    if action.kind == UPDATE:
        if action.entity == "issue":
            conn.execute(
                "UPDATE issues SET title = ?, updated_at = datetime('now','localtime') "
                "WHERE id = ?",
                (action.title, action.local_id),
            )
        else:
            assert endpoints is not None  # the guard above guarantees it
            if action.entity == "issue_relation":
                # The uid is derived from the endpoints, so an UPDATE on the same
                # uid normally means the same endpoints — but a symmetric
                # relation can arrive with the endpoints in the opposite order,
                # and the server's direction is authoritative. Converge to it.
                conn.execute(
                    "UPDATE issue_relations SET source_issue_id = ?, target_issue_id = ?, "
                    "relation_type = ? WHERE id = ?",
                    (endpoint_ids[0], endpoint_ids[1], action.relation_type, action.local_id),
                )
            elif action.entity == "issue_dependency":
                conn.execute(
                    "UPDATE issue_dependencies SET blocker_id = ?, blocked_id = ? WHERE id = ?",
                    (endpoint_ids[0], endpoint_ids[1], action.local_id),
                )
            elif action.entity == "comment":
                # The parent is not re-pointed: a comment moving between issues
                # is not something the wire expresses, so only the text
                # converges to the server's version.
                conn.execute(
                    "UPDATE comments SET text = ? WHERE id = ?",
                    (action.title, action.local_id),
                )
        return

    if action.kind == CREATE:
        if action.entity == "issue":
            cursor_ = conn.execute("INSERT INTO issues (title) VALUES (?)", (action.title,))
        else:
            assert endpoints is not None  # the guard above guarantees it
            if action.entity == "issue_relation":
                cursor_ = conn.execute(
                    "INSERT INTO issue_relations (source_issue_id, target_issue_id, "
                    "relation_type) VALUES (?, ?, ?)",
                    (endpoint_ids[0], endpoint_ids[1], action.relation_type),
                )
            elif action.entity == "issue_dependency":
                cursor_ = conn.execute(
                    "INSERT INTO issue_dependencies (blocker_id, blocked_id) VALUES (?, ?)",
                    (endpoint_ids[0], endpoint_ids[1]),
                )
            elif action.entity == "comment":
                cursor_ = conn.execute(
                    "INSERT INTO comments (issue_id, text) VALUES (?, ?)",
                    (endpoint_ids[0], action.title),
                )
            else:
                raise ValueError(f"unhandled entity {action.entity!r}")
        new_id = cursor_.lastrowid
        if new_id is None:
            raise RuntimeError("insert returned no rowid")
        record_uid(conn, table, int(new_id), action.uid)
        return

    raise ValueError(f"unhandled action kind {action.kind!r}")
