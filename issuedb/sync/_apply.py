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

from issuedb.sync._endpoints import _endpoint_present
from issuedb.sync._feed import collapse_duplicate_uids
from issuedb.sync._fields import invalid_issue_field
from issuedb.sync._kinds import (
    AMBIGUOUS,
    CREATE,
    DELETE,
    MALFORMED,
    SKIP,
    UNSUPPORTED,
    UPDATE,
)
from issuedb.sync._ledger import resolve_uid


class Action(NamedTuple):
    """One planned change. Computed without touching the database."""

    kind: str
    uid: str
    entity: str
    seq: int
    local_id: int | None
    title: str
    reason: str
    # For issue_relation / issue_dependency: the UIDs of the two endpoint
    # issues. The apply resolves them to local ids once the feed has been
    # applied in order. None for issues.
    endpoints: tuple[str, str] | None = None
    # For issue_relation: the relation type. Empty otherwise.
    relation_type: str = ""
    # AN ISSUE IS MORE THAN ITS TITLE. Carrying only the title meant the write
    # inserted one column and let `status` and `priority` fall to their SQL
    # defaults — 'open' and 'medium' — so every issue pulled from the server was
    # silently reset, and push then sent those defaults BACK. Measured by
    # `tracker-fbe1b4` on one sync of a fresh clone: 25 issues reopened, 29
    # re-prioritised, the server's own data overwritten by a client that had
    # never been told the real values (issuedb #30).
    #
    # Empty means "the server did not say", which leaves the local value alone
    # on UPDATE and takes the column default on CREATE.
    status: str = ""
    priority: str = ""
    # A skip whose cause may RESOLVE LATER — a child whose parent has not
    # arrived yet. Only these hold the cursor back, and the distinction is the
    # whole point: a MALFORMED row can never be stored, so holding the cursor
    # for it re-delivers the same unusable change forever and the sync never
    # progresses. A deferred child, held, resolves on the sync where its parent
    # lands. Permanent problems are reported and stepped over; transient ones
    # are waited for.
    deferred: bool = False

    def describe(self, uid_width: int = 12) -> str:
        target = f"#{self.local_id}" if self.local_id is not None else "(new)"
        short = self.uid.split(":")[-1][:uid_width]
        return f"{self.kind.upper():<9} {target:<7} [{short}] {self.title}  — {self.reason}"


_APPLY_RANK = {"issue": 0}


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

    # The plan is computed for the WHOLE feed before anything is applied, so a
    # relation/dependency whose endpoint issues are IN this feed cannot resolve
    # them against the database yet — the issues are only planned, not applied.
    # The server enforces push ordering (issues, then edges), so an edge's
    # One walk can deliver one uid twice; collapse to the newest first.
    changes = collapse_duplicate_uids(changes)

    # endpoints always have a lower seq and are applied first; the plan just
    # has to know they are coming. This set is that knowledge: every live issue
    # uid the feed will create. An endpoint present here OR already in the
    # database is one the apply can resolve; an endpoint in neither is a SKIP.
    feed_issue_uids: set[str] = set()
    for c in changes:
        c_uid = c.get("uid")
        if (
            c.get("entity") == "issue"
            and c.get("deleted") is not True
            and isinstance(c_uid, str)
        ):
            feed_issue_uids.add(c_uid)

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
        endpoints: tuple[str, str] | None = None
        relation_type = ""
        status = ""
        priority = ""

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

            # A value we do not recognise must STOP, not fall back. Falling back
            # is precisely how the fields were lost: a default is indis-
            # tinguishable from a value the server actually sent, so a silent
            # substitution corrupts the row and then pushes the corruption back.
            status = str(payload.get("status") or "")
            priority = str(payload.get("priority") or "")
            bad = invalid_issue_field(status, priority)
            if bad is not None:
                actions.append(Action(MALFORMED, uid, entity, seq, None, title, bad))
                continue

        elif entity == "comment":
            # A comment hangs off an issue the way an edge hangs off two, so it
            # needs the same endpoint resolution: the payload names the parent
            # by UID and the local row references it by LOCAL id.
            #
            # `tracker-fbe1b4` measured that this was missing while push
            # worked: a comment written in the browser could not reach a
            # laptop. Push is one direction of two, and the missing one is the
            # one an operator notices when a colleague comments.
            if payload is None:
                actions.append(
                    Action(
                        MALFORMED, uid, entity, seq, None, title,
                        f"payload is {type(raw_payload).__name__}, expected an object",
                    )
                )
                continue
            parent_uid = payload.get("issue_uid")
            text = payload.get("text")
            if not isinstance(parent_uid, str) or not parent_uid:
                actions.append(
                    Action(
                        MALFORMED, uid, entity, seq, None, title,
                        "a comment carries no issue_uid, so it belongs to no issue",
                    )
                )
                continue
            if not isinstance(text, str) or not text:
                # comments.text is NOT NULL locally. A comment with no text is
                # not a comment, and writing an empty one would be inventing
                # content the server never sent.
                actions.append(
                    Action(
                        MALFORMED, uid, entity, seq, None, title,
                        "a comment carries no text, and comments.text is NOT NULL locally",
                    )
                )
                continue
            if not _endpoint_present(conn, parent_uid, feed_issue_uids):
                actions.append(
                    Action(
                        SKIP, uid, entity, seq, None, text[:60],
                        f"the issue {parent_uid[:20]} it comments on has not arrived yet; "
                        f"held for a later sync",
                        deferred=True,
                    )
                )
                continue
            # Both slots carry the parent: a comment has one endpoint, and
            # reusing the pair keeps one resolution path for every entity that
            # references an issue.
            endpoints = (parent_uid, parent_uid)
            title = text

        elif entity in ("issue_relation", "issue_dependency"):
            # A relation/dependency is defined by the issues it relates, so its
            # local row references them by LOCAL id. The server payload names
            # them by UID, so the endpoints must be resolved before the row can
            # be written. Push ordering is a hard constraint (issues, then
            # edges), so by the time an edge arrives its endpoints should be
            # present — but a missing endpoint is a SKIP, never a crash, and
            # never a row with a dangling foreign key.
            if payload is None:
                actions.append(
                    Action(
                        MALFORMED, uid, entity, seq, None, title,
                        f"payload is {type(raw_payload).__name__}, expected an object",
                    )
                )
                continue

            if entity == "issue_relation":
                source_uid = payload.get("source")
                target_uid = payload.get("target")
                rel_type = payload.get("type")
                # Check each field individually: `all(isinstance(...))` does not
                # narrow the individual variables for mypy, and a field that is
                # present-but-null must be caught here, not crash the plan.
                if not isinstance(source_uid, str) or not source_uid:
                    actions.append(
                        Action(
                            MALFORMED, uid, entity, seq, None, title,
                            "issue_relation payload needs string source, type and target",
                        )
                    )
                    continue
                if not isinstance(target_uid, str) or not target_uid:
                    actions.append(
                        Action(
                            MALFORMED, uid, entity, seq, None, title,
                            "issue_relation payload needs string source, type and target",
                        )
                    )
                    continue
                if not isinstance(rel_type, str) or not rel_type:
                    actions.append(
                        Action(
                            MALFORMED, uid, entity, seq, None, title,
                            "issue_relation payload needs string source, type and target",
                        )
                    )
                    continue
                if not (
                    _endpoint_present(conn, source_uid, feed_issue_uids)
                    and _endpoint_present(conn, target_uid, feed_issue_uids)
                ):
                    actions.append(
                        Action(
                            SKIP, uid, entity, seq, None, title,
                            "an endpoint issue has not arrived yet; held for a later sync",
                            deferred=True,
                        )
                    )
                    continue
                # Carry the endpoint UIDs; the apply resolves them to local ids
                # once the feed has been applied in order.
                endpoints = (source_uid, target_uid)
                relation_type = rel_type
                title = rel_type
            else:  # issue_dependency
                blocker_uid = payload.get("blocker")
                blocked_uid = payload.get("blocked")
                if not isinstance(blocker_uid, str) or not blocker_uid:
                    actions.append(
                        Action(
                            MALFORMED, uid, entity, seq, None, title,
                            "issue_dependency payload needs string blocker and blocked",
                        )
                    )
                    continue
                if not isinstance(blocked_uid, str) or not blocked_uid:
                    actions.append(
                        Action(
                            MALFORMED, uid, entity, seq, None, title,
                            "issue_dependency payload needs string blocker and blocked",
                        )
                    )
                    continue
                if not (
                    _endpoint_present(conn, blocker_uid, feed_issue_uids)
                    and _endpoint_present(conn, blocked_uid, feed_issue_uids)
                ):
                    actions.append(
                        Action(
                            SKIP, uid, entity, seq, None, title,
                            "an endpoint issue has not arrived yet; held for a later sync",
                            deferred=True,
                        )
                    )
                    continue
                endpoints = (blocker_uid, blocked_uid)
                title = "dependency"

        else:
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
                    Action(
                        DELETE, uid, entity, seq, local_id, title, "explicit tombstone",
                        endpoints=endpoints, relation_type=relation_type,
                    )
                )
            continue

        if local_id is None:
            actions.append(
                Action(
                    CREATE, uid, entity, seq, None, title, "not present locally",
                    status=status, priority=priority,
                    endpoints=endpoints, relation_type=relation_type,
                )
            )
        else:
            actions.append(
                Action(
                    UPDATE, uid, entity, seq, local_id, title, "present locally",
                    status=status, priority=priority,
                    endpoints=endpoints, relation_type=relation_type,
                )
            )

    # APPLY PARENTS BEFORE CHILDREN, WHATEVER ORDER THE FEED USED.
    #
    # The feed is NOT parent-ordered and cannot be. It is ordered by seq, and a
    # row's seq advances when it changes, so editing an issue moves it BEHIND
    # its own comments permanently. `tracker-fbe1b4` measured the extreme case
    # on production: of 100 comments on page 1, ONE HUNDRED had their issue in
    # a later page.
    #
    # The plan's lookahead already knows the parent is coming — that is what
    # `feed_issue_uids` is for — but the WRITE happened in feed order, so the
    # child was inserted first, its endpoint resolved to nothing, and the whole
    # batch aborted: 0 of 314 changes applied, a fresh clone left empty.
    # Aborting is the worst of the three wrong answers here (the others being
    # inventing the parent or dropping the child).
    #
    # Sorting is stable, so seq order is preserved WITHIN each rank and the
    # only thing that moves is a child that would otherwise precede its parent.
    return sorted(actions, key=lambda action: _APPLY_RANK.get(action.entity, 1))


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
