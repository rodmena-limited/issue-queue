"""What an issue's scalar fields may contain, and what to do when they do not.

Extracted from ``_apply`` under the 550-line cap (issuedb #24), and it earns
its own module for a better reason than line count: this is the boundary where
a value the server sent becomes a value this schema can store, and the rule at
that boundary is the whole of issuedb #30.

**An unrecognised value STOPS. It is never replaced by a default.** Silent
substitution is exactly how `status` and `priority` were lost: the write named
only `title`, the columns fell back to 'open' and 'medium', and a default is
indistinguishable from a value the server actually sent. The row was then
pushed back, so the client overwrote the server with its own defaults — 25
issues reopened and 29 re-prioritised in one sync of a fresh clone.

So absence and invalidity are kept apart:

* **absent** — the server said nothing. Leave the local value alone; take the
  column default only when creating.
* **present but unknown** — report it. We cannot store it and guessing which
  known value was meant is how the data was lost in the first place.
"""

from __future__ import annotations

from issuedb.models import Priority, Status

VALID_STATUS = frozenset(member.value for member in Status)
VALID_PRIORITY = frozenset(member.value for member in Priority)


def invalid_issue_field(status: str, priority: str) -> str | None:
    """The reason these values cannot be stored, or None if they can.

    Empty means "not sent" and is always acceptable; only a non-empty value
    outside the enum is a problem.
    """
    if status and status not in VALID_STATUS:
        return f"status {status!r} is not one of {sorted(VALID_STATUS)}"
    if priority and priority not in VALID_PRIORITY:
        return f"priority {priority!r} is not one of {sorted(VALID_PRIORITY)}"
    return None
