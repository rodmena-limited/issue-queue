"""Resolving a relation or dependency endpoint to a local row.

Split out of ``_apply`` under the 550-line cap (issuedb #24). These two are the
only place the plan and the write agree on what "the endpoint exists" means, so
keeping them together makes that agreement visible.
"""

from __future__ import annotations

import sqlite3

from issuedb.sync._ledger import resolve_uid


def _endpoint_present(
    conn: sqlite3.Connection, uid: str, feed_issue_uids: set[str]
) -> bool:
    """Whether an endpoint issue will be resolvable when the apply reaches it.

    True if the endpoint is already a live local issue, or if the feed itself
    will create it (the server enforces push ordering, so it is applied first).
    """
    return len(resolve_uid(conn, uid)) == 1 or uid in feed_issue_uids


def _resolve_endpoint(conn: sqlite3.Connection, uid: str) -> int:
    """The local id of an endpoint issue, resolved at apply time.

    The plan carries endpoint UIDs because the feed creates the issues; by the
    time the apply reaches the edge, the feed has been applied in order and the
    endpoint is present. A uid that resolves to zero or two rows is a defect in
    the plan's endpoint check, and must stop the run rather than write a
    dangling foreign key.
    """
    ids = resolve_uid(conn, uid)
    if len(ids) != 1:
        raise ValueError(f"endpoint {uid} resolves to {len(ids)} local rows")
    return ids[0]
