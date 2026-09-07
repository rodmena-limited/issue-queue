"""Rendering a plan for a human to read.

Split out of ``_apply`` under the 550-line cap (issuedb #24) when comment
support pushed the file past its ratchet. Presentation and the write path have
no reason to share a module: this one is pure formatting over
:class:`~issuedb.sync._apply.Action` and touches no database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from issuedb.sync._kinds import AMBIGUOUS

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from issuedb.sync._apply import Action

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
