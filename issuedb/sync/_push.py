"""Turn outbox rows into push entries — the send half of sync.

Until this existed, ``SyncClient.push`` was fully written and had no caller
anywhere in the package: sync was pull-only, so no issue created in a
developer's ``.issue.db`` could ever reach Tracker (issuedb #14, reported from
the outside by `tracker-fbe1b4`).

WHAT THIS SENDS, and what it refuses to:

* ``issues`` — uid MINTED on first push and recorded in the ledger, so the same
  local row keeps one identity forever.
* ``issue_dependencies`` and ``issue_relations`` — uid DERIVED from the frozen
  canonical form, so two replicas that independently record the same edge
  converge with no conflict machinery.
* ``issue_tags`` — **refused, deliberately.** The outbox trigger records
  ``NEW.issue_id`` as ``local_id``, and the ledger is keyed ``(entity,
  local_id)``, so two tags on one issue collide on one ledger key: two uids,
  one row. Pushing them would send one tag under another's identity. That is
  issuedb #13 and it needs a schema change, not a workaround here.
* everything else — no sync entity exists on the wire for it (comments,
  templates, time entries…), reported by the coverage pass rather than dropped
  silently.

ONE ENTRY PER ROW, NOT ONE PER EVENT. The outbox is an event log: editing an
issue three times writes three rows. The server wants current state, so entries
are collapsed to the LAST event per ``(entity, local_id)`` — the same reasoning
as :func:`issuedb.sync._feed.collapse_duplicate_uids` on the way in. A delete
after an insert collapses to the delete; the row never existed for the server
and sending both would be an insert the server must then undo.

Standard library only.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from issuedb.sync._canonical import (
    canonical_bytes,
    dependency_uid,
    mint_uid,
    relation_uid,
)
from issuedb.sync._ledger import record_uid

# Local table -> the entity name the wire uses.
PUSHABLE = {
    "issues": "issue",
    "issue_dependencies": "issue_dependency",
    "issue_relations": "issue_relation",
}

# Local tables that have a wire entity but cannot be pushed correctly yet.
BLOCKED = {
    "issue_tags": (
        "issuedb #13: the outbox records issue_id as local_id and the ledger is "
        "keyed (entity, local_id), so two tags on one issue collide on one key"
    ),
}


def _content_hash(*fields: object) -> str:
    import hashlib

    raw = canonical_bytes([("" if f is None else str(f)) for f in fields])
    return "s256t128:" + hashlib.sha256(raw).hexdigest()[:32]


def _uid_for_issue(conn: sqlite3.Connection, local_id: int) -> str:
    """The stable uid of a local issue, minted once and remembered."""
    existing = resolve_uid_by_local(conn, "issues", local_id)
    if existing is not None:
        return existing
    uid = mint_uid()
    record_uid(conn, "issues", local_id, uid)
    return uid


def resolve_uid_by_local(conn: sqlite3.Connection, table: str, local_id: int) -> str | None:
    row = conn.execute(
        "SELECT uid FROM sync_row WHERE entity = ? AND local_id = ? AND deleted = 0",
        (table, local_id),
    ).fetchone()
    return None if row is None else str(row[0])


def collapse_outbox(rows: list[sqlite3.Row]) -> list[Any]:
    """Last event wins per (entity, local_id); feed order otherwise preserved."""
    last: dict[tuple[str, int], Any] = {}
    order: list[tuple[str, int]] = []
    for row in rows:
        key = (str(row["entity"]), int(row["local_id"]))
        if key not in last:
            order.append(key)
        last[key] = row
    return [last[key] for key in order]


def unsent_rows(conn: sqlite3.Connection) -> dict[str, list[int]]:
    """Pushable rows the server has never seen, per local table.

    THE OUTBOX IS NOT THE RECORD OF WHAT THE SERVER HAS SEEN — the LEDGER is.
    The outbox is an event log written by triggers, so it only contains rows
    touched SINCE those triggers were installed. Every issue that existed
    before the sync migration ran has no outbox row at all, and a push driven
    purely by the outbox skips them forever while reporting a healthy count.

    Measured on this repository's own database: 28 issues, 26 in the outbox,
    and issues #1 and #2 — created before the earliest outbox row — invisible
    to push with nothing said about them (issuedb #29).

    No test could have caught it, because a test database creates every row
    AFTER the triggers exist. That shape only occurs in a database that
    predates the feature, which is every existing user's.

    A row with no ledger entry has never been pushed. That criterion is
    complete for existence and says nothing about deletes — a deleted row has
    no local row to enumerate, which is what the outbox is still for.
    """
    found: dict[str, list[int]] = {}
    for table in PUSHABLE:
        rows = conn.execute(
            f"SELECT t.id FROM {table} t "  # noqa: S608 - table from a literal dict
            "LEFT JOIN sync_row s ON s.entity = ? AND s.local_id = t.id "
            "WHERE s.uid IS NULL ORDER BY t.id",
            (table,),
        ).fetchall()
        if rows:
            found[table] = [int(r[0]) for r in rows]
    return found


def build_entries(
    conn: sqlite3.Connection, project_uid: str, since_seq: int, limit: int = 500
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Build push entries from outbox rows after ``since_seq``.

    Returns the entries, the highest outbox seq they cover, and a count of what
    was skipped and why. The seq is the highest CONSIDERED, not the highest
    sent: a skipped row is permanently skipped, so leaving it behind the mark
    would re-examine it on every push forever.
    """
    conn.row_factory = sqlite3.Row
    rows = list(
        conn.execute(
            "SELECT seq, entity, local_id, op FROM sync_outbox "
            "WHERE seq > ? ORDER BY seq LIMIT ?",
            (since_seq, limit),
        )
    )

    highest = max(int(r["seq"]) for r in rows) if rows else since_seq
    skipped: dict[str, int] = {}
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for row in collapse_outbox(rows):
        table = str(row["entity"])
        if table in BLOCKED:
            skipped[table] = skipped.get(table, 0) + 1
            continue
        if table not in PUSHABLE:
            skipped[table] = skipped.get(table, 0) + 1
            continue

        entity = PUSHABLE[table]
        local_id = int(row["local_id"])
        op = "delete" if str(row["op"]) == "delete" else "upsert"
        entry = _entry_for(conn, entity, table, local_id, op, project_uid)
        if entry is None:
            skipped[f"{table} (row gone)"] = skipped.get(f"{table} (row gone)", 0) + 1
            continue
        seen.add((table, local_id))
        entries.append(entry)

    # BACKFILL: anything the ledger has never seen, whatever the outbox says.
    for table, local_ids in unsent_rows(conn).items():
        entity = PUSHABLE[table]
        for local_id in local_ids:
            if (table, local_id) in seen or len(entries) >= limit:
                continue
            entry = _entry_for(conn, entity, table, local_id, "upsert", project_uid)
            if entry is not None:
                entries.append(entry)

    return entries, highest, skipped


def _entry_for(
    conn: sqlite3.Connection,
    entity: str,
    table: str,
    local_id: int,
    op: str,
    project_uid: str,
) -> dict[str, Any] | None:
    if entity == "issue":
        if op == "delete":
            uid = resolve_uid_by_local(conn, table, local_id)
            if uid is None:
                # Never pushed, now deleted: the server never knew it. Sending a
                # delete for a uid the server has never seen is noise at best.
                return None
            return {"uid": uid, "entity": entity, "op": "delete",
                    "content_hash": _content_hash("delete", uid), "payload": {}}
        row = conn.execute(
            "SELECT title, description, status, priority FROM issues WHERE id = ?",
            (local_id,),
        ).fetchone()
        if row is None:
            return None
        uid = _uid_for_issue(conn, local_id)
        payload = {
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "priority": row["priority"],
        }
        return {
            "uid": uid,
            "entity": entity,
            "op": "upsert",
            "content_hash": _content_hash(*payload.values()),
            "payload": payload,
        }

    # Edges: both endpoints must already have uids, or the server cannot resolve
    # them. They are issues, and issues are pushed first because their outbox
    # rows have lower seq.
    if entity == "issue_dependency":
        row = conn.execute(
            "SELECT blocker_id, blocked_id FROM issue_dependencies WHERE id = ?", (local_id,)
        ).fetchone()
        if row is None:
            return None
        blocker = resolve_uid_by_local(conn, "issues", int(row["blocker_id"]))
        blocked = resolve_uid_by_local(conn, "issues", int(row["blocked_id"]))
        if blocker is None or blocked is None:
            return None
        uid = dependency_uid(project_uid, blocker, blocked)
        return {
            "uid": uid,
            "entity": entity,
            "op": op,
            "content_hash": _content_hash(blocker, blocked),
            "payload": {} if op == "delete" else {"blocker": blocker, "blocked": blocked},
        }

    row = conn.execute(
        "SELECT source_issue_id, target_issue_id, relation_type FROM issue_relations "
        "WHERE id = ?",
        (local_id,),
    ).fetchone()
    if row is None:
        return None
    source = resolve_uid_by_local(conn, "issues", int(row["source_issue_id"]))
    target = resolve_uid_by_local(conn, "issues", int(row["target_issue_id"]))
    if source is None or target is None:
        return None
    rel_type = str(row["relation_type"])
    uid = relation_uid(project_uid, source, rel_type, target)
    return {
        "uid": uid,
        "entity": entity,
        "op": op,
        "content_hash": _content_hash(source, rel_type, target),
        "payload": {} if op == "delete"
        else {"source": source, "target": target, "type": rel_type},
    }
