"""Executing a plan and deciding how far the cursor may safely move.

Split out of ``_apply`` under the 550-line cap (issuedb #24). The seam is real:
``_apply`` decides WHAT should happen to each change, ``_write`` performs one
change, and this module runs the sequence and works out the watermark.

The watermark is the subtle part and it earned its own home. Actions are applied
in DEPENDENCY order, not feed order, so "the seq of the last action applied" is
not the answer — a child at seq 1 can be applied after its parent at seq 121,
and recording the last would rewind the cursor and re-deliver the whole feed.
What is safe is the highest seq with nothing unapplied below it.
"""

from __future__ import annotations

import sqlite3
from typing import NamedTuple

from issuedb.sync._apply import Action
from issuedb.sync._kinds import AMBIGUOUS, MALFORMED, SKIP, UNSUPPORTED
from issuedb.sync._write import _apply_one


class ApplyResult(NamedTuple):
    applied: int
    failed: int
    cursor: str
    stopped_at: str | None




# Issues carry no reference to anything else; every other entity names an issue
# by uid. So issues are written first and everything else after — one rank, not
# a general topological sort, because the reference graph is one level deep.


def apply(
    conn: sqlite3.Connection,
    actions: list[Action],
    cursor: str,
) -> ApplyResult:
    """Apply planned actions, one transaction each.

    Returns the cursor advanced ONLY to the last durably committed change. If
    an action raises, the run stops: everything before it stays, nothing after
    it is attempted, and the cursor names the last success rather than the
    last attempt.

    One transaction per action rather than one for the batch, deliberately.
    A batch transaction would be all-or-nothing, which sounds safer and means
    an interrupted sync re-does work it already did — and worse, it makes the
    durable cursor unknowable for a partial page.
    """
    applied = 0
    # THE CURSOR IS A WATERMARK, NOT A POSITION. Actions are applied in
    # dependency order (parents before children), not feed order, so "the seq
    # of the last action applied" is no longer the right answer — a child at
    # seq 1 can be applied after its parent at seq 121, and taking the last
    # would rewind the cursor to 1 and re-deliver the whole feed forever.
    #
    # What is safe to record is the highest seq such that EVERY change at or
    # below it has landed. Anything unapplied caps the watermark below itself.
    applied_seqs: list[int] = []
    unapplied_seqs: list[int] = []
    stopped_at: str | None = None

    for action in actions:
        if action.kind in (SKIP, AMBIGUOUS, UNSUPPORTED, MALFORMED):
            # Not applied, and NOT counted as progress: advancing the cursor
            # past an ambiguous change would mean never being asked about it
            # again.
            if action.kind == AMBIGUOUS:
                stopped_at = (
                    f"{action.uid}: ambiguous, and the cursor must not advance past a "
                    f"change that was never applied"
                )
                unapplied_seqs.append(action.seq)
                break
            # Only a DEFERRED skip holds the watermark. See Action.deferred.
            if action.deferred:
                unapplied_seqs.append(action.seq)
            continue

        try:
            conn.execute("BEGIN IMMEDIATE")
            _apply_one(conn, action)
            conn.execute("COMMIT")
        except Exception as exc:  # noqa: BLE001 - any failure must stop the run
            conn.execute("ROLLBACK")
            stopped_at = f"{action.uid}: {exc}"
            unapplied_seqs.append(action.seq)
            break

        applied += 1
        applied_seqs.append(action.seq)

    # Everything strictly below the first gap is durable.
    ceiling = min(unapplied_seqs) if unapplied_seqs else None
    below = [seq for seq in applied_seqs if ceiling is None or seq < ceiling]
    final_cursor = cursor if not below else f"c:{max(below)}"
    return ApplyResult(
        applied=applied,
        failed=1 if stopped_at else 0,
        cursor=final_cursor,
        stopped_at=stopped_at,
    )


# Server entity name -> local table. The ledger records the LOCAL table name as
# its entity, so record_uid / tombstone must be called with the table, not the
# wire name.
