"""Feed-level normalisation applied before the plan sees a walk."""

from __future__ import annotations

from typing import Any


def collapse_duplicate_uids(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one change per uid — the one with the highest seq.

    ONE WALK CAN DELIVER ONE UID TWICE. The feed is one row per uid carrying
    current state, and seq advances on change, so a row touched between the
    moment page 1 was served and the moment page 3 was served appears on both
    under two different seqs. Nothing is wrong on the server; that is the
    documented semantics (``SPECS/feed-semantics.md``).

    Planned naively, both occurrences are "not present locally" — the plan is
    computed for the whole feed BEFORE anything is applied, so the first
    occurrence has not been written yet when the second is planned. Two CREATE
    actions follow, two rows are inserted, and **the ledger ends up with two
    entries for one uid**, destroying the one-to-one identity it exists to
    hold. Measured before this existed: 451 changes produced 451 creates,
    ``issue 200`` present twice, and two ``sync_row`` rows for one uid.

    The LAST occurrence wins because the feed carries current state, so the
    higher seq is the newer truth. Feed order is otherwise preserved, which
    matters because endpoints must still be planned before the rows that
    reference them.

    A change with a missing or non-string uid is **not** collapsed: those must
    each reach the plan and be reported individually rather than silently
    merged, since one of them is a malformed-row report the operator needs.
    """
    seen_last: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for change in changes:
        uid = change.get("uid")
        if isinstance(uid, str) and uid:
            prior = seen_last.get(uid)
            if prior is None:
                seen_last[uid] = change
                continue
            try:
                newer = int(change.get("seq", 0)) >= int(prior.get("seq", 0))
            except (TypeError, ValueError):
                newer = True
            if newer:
                seen_last[uid] = change
        else:
            passthrough.append(change)

    if len(seen_last) + len(passthrough) == len(changes):
        return changes

    first_index = {}
    for position, change in enumerate(changes):
        uid = change.get("uid")
        if isinstance(uid, str) and uid and uid not in first_index:
            first_index[uid] = position
    kept = sorted(seen_last.items(), key=lambda item: first_index[item[0]])
    return passthrough + [change for _, change in kept]
