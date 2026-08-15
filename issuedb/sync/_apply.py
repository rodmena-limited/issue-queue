"""Applying pulled changes to the local database.

This is the dangerous direction. Everything else in this package writes into
Tracker — a server with backups, an audit trail and someone watching it. Apply
writes into SOMEONE'S LOCAL ISSUE DATABASE, where a defect destroys work that
exists nowhere else.

So the module is built around four refusals rather than four features:

**It does nothing by default.** :func:`plan` computes what WOULD change and
touches nothing; :func:`apply` is a separate call the CLI only makes on an
explicit flag. A user's first encounter with sync must not be a mutation.

**Absence never deletes.** A uid missing from a pulled page means "not on this
page". It does not mean deleted. Only an explicit ``deleted: true`` tombstone
removes a row, in both directions. A `git checkout` can make rows vanish that
nobody deleted, and a sync that treated absence as intent would delete a
colleague's work on the strength of pagination.

**The cursor advances only to what was durably committed.** Not to the end of
the page, not to the last change examined — to the last one whose transaction
returned. A cursor advanced past a failed apply skips those rows forever,
because nothing ever asks for them again and no error is ever raised.

**A failure stops the run.** Already-applied changes stay; the rest are not
attempted. Partially applying a page and continuing is how a database ends up
in a state neither side believes in.

Standard library only.
"""

from __future__ import annotations

import sqlite3
from typing import Any, NamedTuple

from issuedb.sync._ledger import record_uid, resolve_uid, tombstone

CREATE = "create"
UPDATE = "update"
DELETE = "delete"
SKIP = "skip"
AMBIGUOUS = "ambiguous"


class Action(NamedTuple):
    """One planned change. Computed without touching the database."""

    kind: str
    uid: str
    entity: str
    seq: int
    local_id: int | None
    title: str
    reason: str

    def describe(self, uid_width: int = 12) -> str:
        target = f"#{self.local_id}" if self.local_id is not None else "(new)"
        short = self.uid.split(":")[-1][:uid_width]
        return f"{self.kind.upper():<9} {target:<7} [{short}] {self.title}  — {self.reason}"


class ApplyResult(NamedTuple):
    applied: int
    failed: int
    cursor: str
    stopped_at: str | None


UNSUPPORTED = "unsupported"
MALFORMED = "malformed"


def plan(
    conn: sqlite3.Connection,
    changes: list[dict[str, Any]],
    server_entities: frozenset[str] | None = None,
) -> list[Action]:
    """Decide what each pulled change would do. MUTATES NOTHING.

    Separated from :func:`apply` so the dry run and the real run compute the
    same decisions from the same code. A dry run that used a different code
    path would be describing a plan the apply does not follow — which is worse
    than no dry run, because the user has been shown something and believes it.

    ``server_entities`` is the ``entities`` list from the handshake. It
    separates two causes that were previously ONE OBSERVATION:

        the server does not support this entity type YET   -> UNSUPPORTED
        this client does not apply this entity type yet    -> SKIP

    Before the field existed, both arrived as an identical per-entry rejection.
    A client that cannot tell them apart either retries forever against a
    server that will never accept tags, or discards a genuinely malformed entry
    as "unsupported". Same shape as the credential ambiguity: two causes, one
    observation.

    ``None`` means the server did not advertise the field — an older Tracker —
    and is NOT treated as "supports nothing". Defaulting to empty would mark
    every change unsupported and silently stop applying anything.
    """
    actions: list[Action] = []

    for change in changes:
        # NEVER str() a value that may be None. `str(None)` is "None" — a
        # TRUTHY string that sails past `if not uid:` and gets recorded in the
        # ledger as a real uid. Every row with a null uid would then share the
        # identity "None", collide with each other, and be pushed back to the
        # server under it.
        #
        # This is not hypothetical: Tracker's web-created issues had no
        # sync_uid and pull emitted `uid: null`. `.get("uid", "")` returns the
        # default only when the KEY IS ABSENT, never when it is present and
        # null — which is why the absent case worked and the null case did not.
        raw_uid = change.get("uid")
        raw_entity = change.get("entity")
        uid = raw_uid if isinstance(raw_uid, str) else ""
        entity = raw_entity if isinstance(raw_entity, str) else ""
        try:
            seq = int(change.get("seq", 0))
        except (TypeError, ValueError):
            seq = 0

        # Server data is INPUT, not something to trust. `payload.get(...)` on a
        # payload that is a string raises AttributeError and takes the whole
        # plan down — a malformed entry from the server should be reported,
        # never crash the client mid-plan.
        raw_payload = change.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else None
        title = str((payload or {}).get("title") or "")

        if not uid:
            actions.append(
                Action(
                    MALFORMED, uid, entity, seq, None, title,
                    f"uid is {type(raw_uid).__name__}, expected a string — a change with no "
                    f"identity cannot be applied or recorded",
                )
            )
            continue

        if not entity:
            actions.append(
                Action(
                    MALFORMED, uid, entity, seq, None, title,
                    f"entity is {type(raw_entity).__name__}, expected a string",
                )
            )
            continue

        if server_entities is not None and entity not in server_entities:
            # The SERVER says it does not support this type. Distinct from the
            # client not applying it: this one will not change by upgrading
            # issuedb, and retrying it is pointless until Tracker ships it.
            actions.append(
                Action(
                    UNSUPPORTED, uid, entity, seq, None, title,
                    f"the server does not support entity {entity!r} yet "
                    f"(handshake advertises {sorted(server_entities)})",
                )
            )
            continue

        # MALFORMED is checked AFTER the entity fork, so an unsupported type is
        # never reported as malformed and vice versa. Those are different
        # causes needing different actions: unsupported waits for the server,
        # malformed is a defect to report. A client that called everything
        # "unsupported" would satisfy the unsupported test alone, which is why
        # both directions are asserted.
        if entity == "issue":
            if payload is None:
                actions.append(
                    Action(
                        MALFORMED, uid, entity, seq, None, title,
                        f"payload is {type(raw_payload).__name__}, expected an object",
                    )
                )
                continue
            if not title.strip():
                actions.append(
                    Action(
                        MALFORMED, uid, entity, seq, None, title,
                        "an issue carries no title, and issues.title is NOT NULL locally",
                    )
                )
                continue

        if entity != "issue":
            # The CLIENT does not apply this type yet, though the server
            # supports it. Reported rather than silently ignored, so a user can
            # see the sync is incomplete instead of assuming it covered
            # everything — and this one IS fixed by upgrading issuedb.
            actions.append(
                Action(
                    SKIP, uid, entity, seq, None, title,
                    f"issuedb does not apply entity {entity!r} yet",
                )
            )
            continue

        local_ids = resolve_uid(conn, uid, include_deleted=True)

        if len(local_ids) > 1:
            # The ambiguity rule, at the apply layer: present every candidate
            # and select none. Picking one here would write server state over
            # whichever local row happened to sort first.
            actions.append(
                Action(
                    AMBIGUOUS, uid, entity, seq, None, title,
                    f"uid resolves to {len(local_ids)} local rows {local_ids}; issuedb will "
                    f"not choose",
                )
            )
            continue

        local_id = local_ids[0] if local_ids else None

        if change.get("deleted") is True:
            # ONLY an explicit tombstone deletes.
            if local_id is None:
                actions.append(
                    Action(SKIP, uid, entity, seq, None, title, "tombstone for a row we lack")
                )
            else:
                actions.append(
                    Action(DELETE, uid, entity, seq, local_id, title, "explicit tombstone")
                )
            continue

        if local_id is None:
            actions.append(Action(CREATE, uid, entity, seq, None, title, "not present locally"))
        else:
            actions.append(
                Action(UPDATE, uid, entity, seq, local_id, title, "present locally")
            )

    return actions


def _distinguishing_width(actions: list[Action], minimum: int = 12) -> int:
    """Shortest uid prefix that is unique across this plan, like git's sha abbreviation."""
    hexes = [a.uid.split(":")[-1] for a in actions if a.uid]
    longest = max((len(h) for h in hexes), default=minimum)
    for width in range(minimum, longest + 1):
        if len({h[:width] for h in hexes}) == len(set(hexes)):
            return width
    return longest


def render_plan(actions: list[Action], applying: bool) -> str:
    """The dry-run report. Says plainly that nothing has changed."""
    if not actions:
        return "Nothing to apply — no changes pulled."

    counts: dict[str, int] = {}
    for action in actions:
        counts[action.kind] = counts.get(action.kind, 0) + 1

    # Widen the uid prefix until every uid in THIS plan is distinguishable.
    #
    # A fixed 12 characters looked fine until a real pull returned uids sharing
    # their first 12 hex chars — three rows displayed as [37cf85f2c974] and a
    # reader could not tell them apart. The whole reason a plan shows uids is
    # that the local number cannot distinguish rows, so a truncation that
    # collides defeats the point exactly where it matters.
    lines = [action.describe(_distinguishing_width(actions)) for action in actions]
    summary = ", ".join(f"{count} {kind}" for kind, count in sorted(counts.items()))
    lines.append("")
    lines.append(f"{len(actions)} change(s): {summary}")

    if not applying:
        lines.append("")
        lines.append("DRY RUN — nothing has been changed. Re-run with --apply to apply this.")
    if counts.get(AMBIGUOUS):
        lines.append(
            f"{counts[AMBIGUOUS]} ambiguous reference(s) will NOT be applied: issuedb does not "
            f"choose between candidates."
        )
    return "\n".join(lines)


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
    durable_seq: int | None = None
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
                break
            continue

        try:
            conn.execute("BEGIN IMMEDIATE")
            _apply_one(conn, action)
            conn.execute("COMMIT")
        except Exception as exc:  # noqa: BLE001 - any failure must stop the run
            conn.execute("ROLLBACK")
            stopped_at = f"{action.uid}: {exc}"
            break

        applied += 1
        durable_seq = action.seq

    final_cursor = cursor if durable_seq is None else f"c:{durable_seq}"
    return ApplyResult(
        applied=applied,
        failed=1 if stopped_at else 0,
        cursor=final_cursor,
        stopped_at=stopped_at,
    )


def _apply_one(conn: sqlite3.Connection, action: Action) -> None:
    """The single-row write. Called inside a transaction by :func:`apply`."""
    if action.kind == DELETE:
        # Tombstone the ledger entry BEFORE deleting the row: the ledger must
        # outlive the row, and doing it after would lose the record if the
        # delete succeeded and the process died.
        tombstone(conn, "issues", action.local_id)  # type: ignore[arg-type]
        conn.execute("DELETE FROM issues WHERE id = ?", (action.local_id,))
        return

    if action.kind == UPDATE:
        conn.execute(
            "UPDATE issues SET title = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (action.title, action.local_id),
        )
        return

    if action.kind == CREATE:
        cursor_ = conn.execute(
            "INSERT INTO issues (title) VALUES (?)",
            (action.title,),
        )
        new_id = cursor_.lastrowid
        if new_id is None:
            raise RuntimeError("insert returned no rowid")
        record_uid(conn, "issues", int(new_id), action.uid)
        return

    raise ValueError(f"unhandled action kind {action.kind!r}")


def already_applied(conn: sqlite3.Connection, uid: str) -> bool:
    """Whether this uid is in the ledger at all, tombstoned or not.

    Interrupt safety rests on this: after a kill mid-apply, re-running must
    converge rather than duplicate. The ledger is what makes a re-pulled
    change idempotent — the uid is already mapped to a local row, so the plan
    sees UPDATE rather than CREATE and no second row appears.

    include_deleted=True deliberately: a tombstoned uid IS known, and treating
    it as unknown would let a re-pull resurrect a row that was correctly
    deleted.
    """
    return bool(resolve_uid(conn, uid, include_deleted=True))
