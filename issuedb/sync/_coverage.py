"""What this database holds that sync cannot carry.

The apply path reports an UNSUPPORTED entity when a change for it ARRIVES. But
an entity the server has no interface for never arrives at all — so the user
sees "52 applied" and nothing whatsoever about the data that cannot move.

That is an absence carrying a meaning, in the direction that matters most: the
user concludes their data is synced because nothing said otherwise. A person
migrating from issuedb's own UI to Tracker today would lose their links, code
references, time entries, audit trail, lessons and memory, and the product
would not mention it.

So coverage is computed from two facts the client already has — the server's
advertised ``entities`` and the rows actually present locally — and stated
plainly at the end of every sync, dry run included.

It reports only tables that ACTUALLY HOLD ROWS. "Your saved_searches cannot
sync" is noise when there are none, and noise is how a real warning gets
ignored.
"""

from __future__ import annotations

import sqlite3
from typing import NamedTuple

# Local table -> the sync entity that would carry it. Tables with no entity
# name are issuedb-only bookkeeping and are deliberately absent.
TABLE_TO_ENTITY = {
    "issues": "issue",
    "issue_tags": "issue_tag",
    "issue_dependencies": "issue_dependency",
    "issue_relations": "issue_relation",
    "comments": "comment",
    "issue_links": "issue_link",
    "code_references": "code_reference",
    "time_entries": "time_entry",
    "audit_logs": "audit_log",
    "lessons_learned": "lesson",
    "memory": "memory",
    "saved_searches": "saved_search",
    "issue_templates": "issue_template",
}


class Uncovered(NamedTuple):
    table: str
    entity: str
    rows: int


def uncovered(
    conn: sqlite3.Connection, server_entities: frozenset[str] | None
) -> list[Uncovered]:
    """Local tables holding rows that the server cannot accept.

    Returns [] when the server advertises no list — an older Tracker, where
    "cannot carry" is unknown rather than true. Claiming data is unsyncable on
    a guess would be the same defect pointing the other way.
    """
    if server_entities is None:
        return []

    out: list[Uncovered] = []
    for table, entity in sorted(TABLE_TO_ENTITY.items()):
        if entity in server_entities:
            continue
        try:
            rows = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            continue  # table absent in an older schema; not a gap to report
        if rows:
            out.append(Uncovered(table=table, entity=entity, rows=rows))
    return out


def render(items: list[Uncovered], server_entities: frozenset[str] | None) -> str:
    """The user-facing statement. Says nothing when there is nothing to say."""
    if server_entities is None:
        return (
            "This server does not advertise an entity list, so which of your data can "
            "sync is UNKNOWN. Treat nothing here as confirmed."
        )
    if not items:
        return ""

    total = sum(i.rows for i in items)
    lines = [
        f"NOT SYNCED — {total} row(s) across {len(items)} area(s) have nowhere to go on "
        f"this server:",
    ]
    lines.extend(f"    {i.rows:>6} {i.table}  (no '{i.entity}' entity)" for i in items)
    lines.append(
        "  This data stays local. The server advertises "
        f"{sorted(server_entities)} and carries nothing else, so these are not "
        "'pending' — they cannot transfer until the server implements them."
    )
    return "\n".join(lines)
