"""Resolving ``#123`` when ``#123`` might mean more than one issue.

``issues.id`` is ``INTEGER PRIMARY KEY AUTOINCREMENT``, allocated locally, and
22 of the 42 repos in this estate commit ``.issue.db`` to git. So two clones
allocate from the same counter independently and both mint a different issue
numbered 3 — reproduced, not theorised. Once those replicas sync, one local
number denotes two issues.

Renumbering is not available as a repair. ``git_utils.parse_issue_refs`` pulls
``#123`` out of commit messages that are already immutable in git history;
renumbering issue 3 silently repoints every commit that referenced it at
somebody else's work. The reference does not break loudly — it starts meaning
something different, and nothing errors.

Hence the rule this module implements, frozen as a contract rule rather than a
display preference:

    WHEN A REFERENCE IS AMBIGUOUS, PRESENT EVERY CANDIDATE AND SELECT NONE.

A reference that resolves to the wrong issue is worse than one that refuses to
resolve, because the second is a question and the first is a lie. So
:func:`resolve_reference` returns a result the caller cannot accidentally
collapse: there is no "best" candidate, no ordering that implies preference,
and no attribute that hands back a single issue when several matched.

Standard library only.
"""

from __future__ import annotations

import sqlite3
from typing import Any, NamedTuple

from issuedb.sync._ledger import aliases_for_number, get_uid


class Candidate(NamedTuple):
    """One issue a reference might mean."""

    local_id: int
    uid: str | None
    title: str
    status: str
    updated_at: str

    def describe(self) -> str:
        """A one-line form with enough detail for a human to choose.

        The uid is included because it is the only globally unique thing here:
        two candidates share a local number by definition, so the number
        cannot distinguish them.
        """
        short_uid = self.uid.split(":")[-1][:12] if self.uid else "no-uid"
        return f"#{self.local_id} [{short_uid}] {self.status}: {self.title}"


class Reference(NamedTuple):
    """The outcome of resolving one ``#N``.

    There is deliberately no ``.issue`` or ``.best`` attribute. A caller that
    wants the single match must go through :meth:`resolved`, which returns
    None when the reference is ambiguous — so "just take the first one" is not
    something you can write by accident.
    """

    number: int
    candidates: tuple[Candidate, ...]

    @property
    def is_ambiguous(self) -> bool:
        return len(self.candidates) > 1

    @property
    def is_unknown(self) -> bool:
        return len(self.candidates) == 0

    def resolved(self) -> Candidate | None:
        """The single candidate, or None when there are zero or several.

        Returning None for "several" rather than a first-of is the whole
        point: a caller must handle ambiguity explicitly or get nothing.
        """
        return self.candidates[0] if len(self.candidates) == 1 else None

    def render(self) -> str:
        """Human-facing text. Never picks a winner."""
        if self.is_unknown:
            return f"#{self.number}: unknown reference (no such issue)"
        if not self.is_ambiguous:
            return f"#{self.number}: {self.candidates[0].describe()}"
        lines = [
            f"#{self.number} is AMBIGUOUS — {len(self.candidates)} issues carry this number:"
        ]
        lines.extend(f"    {candidate.describe()}" for candidate in self.candidates)
        lines.append(
            "  issuedb will not choose for you. Identify the one you mean by its uid."
        )
        return "\n".join(lines)


def _candidates_for(conn: sqlite3.Connection, number: int) -> tuple[Candidate, ...]:
    """Every issue this local number might mean.

    Two sources, and the second is what makes ambiguity REACHABLE rather than
    a branch that can never execute:

    1. the local issue with that id — ``issues.id`` is a primary key, so at
       most one;
    2. every ALIAS claiming that number. An alias is recorded when a replica
       pushes an issue whose local number was already taken: the server keeps
       the first as canonical and the loser's number survives as an alias,
       because commit messages referencing it are immutable in git history.

    A resolver consulting only (1) could never return two candidates, and the
    ambiguity path would be untestable — a check that cannot go green cannot
    go red.
    """
    candidates: list[Candidate] = []
    seen_uids: set[str] = set()

    row = conn.execute(
        "SELECT id, title, status, updated_at FROM issues WHERE id = ?", (number,)
    ).fetchone()
    if row is not None:
        uid = get_uid(conn, "issues", int(row[0]))
        if uid:
            seen_uids.add(uid)
        candidates.append(
            Candidate(
                local_id=int(row[0]),
                uid=uid,
                title=str(row[1]),
                status=str(row[2]),
                updated_at=str(row[3]),
            )
        )

    if not _has_alias_table(conn):
        return tuple(candidates)

    for alias_uid, _local, _replica, canonical in aliases_for_number(conn, number):
        if alias_uid in seen_uids:
            # The alias describes the very issue we already listed.
            continue
        seen_uids.add(str(alias_uid))
        candidates.append(_candidate_from_alias(conn, str(alias_uid), number, canonical))

    return tuple(candidates)


def _has_alias_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='issue_number_alias'"
    ).fetchone()
    return bool(row[0])


def _candidate_from_alias(
    conn: sqlite3.Connection, uid: str, number: int, canonical: Any
) -> Candidate:
    """Describe an aliased issue, using local detail when we hold it.

    An alias can name an issue this replica has never pulled. That is still a
    candidate — omitting it because we lack a title would silently make an
    ambiguous reference look unambiguous, which is the failure this whole
    module exists to prevent.
    """
    local = conn.execute(
        """
        SELECT i.id, i.title, i.status, i.updated_at
        FROM sync_row s JOIN issues i ON i.id = s.local_id
        WHERE s.uid = ? AND s.entity = 'issues' AND s.deleted = 0
        """,
        (uid,),
    ).fetchone()

    if local is not None:
        return Candidate(
            local_id=int(local[0]),
            uid=uid,
            title=str(local[1]),
            status=str(local[2]),
            updated_at=str(local[3]),
        )

    canonical_number = int(canonical) if canonical is not None else number
    return Candidate(
        local_id=canonical_number,
        uid=uid,
        title="(not present locally — pull to see it)",
        status="unknown",
        updated_at="",
    )


def resolve_reference(conn: sqlite3.Connection, number: int) -> Reference:
    """Resolve one ``#N`` without ever choosing between candidates."""
    return Reference(number=number, candidates=_candidates_for(conn, number))


def resolve_all(conn: sqlite3.Connection, numbers: Any) -> list[Reference]:
    """Resolve several references, in ascending numeric order.

    Sorted so output is stable between runs; the order carries no preference
    and never implies one candidate over another.
    """
    return [resolve_reference(conn, number) for number in sorted(set(numbers))]


def partition(references: list[Reference]) -> dict[str, list[Reference]]:
    """Split references into resolved / ambiguous / unknown.

    Ambiguous and unknown are kept SEPARATE rather than merged into "not
    resolved": they need different actions from the user. Unknown means the
    reference is stale or wrong; ambiguous means it is real and needs a human
    to say which real thing it is.
    """
    return {
        "resolved": [r for r in references if r.resolved() is not None],
        "ambiguous": [r for r in references if r.is_ambiguous],
        "unknown": [r for r in references if r.is_unknown],
    }


def render_report(references: list[Reference]) -> str:
    """A full report. Ambiguity is surfaced, never quietly dropped."""
    if not references:
        return "No issue references found."

    groups = partition(references)
    lines: list[str] = []

    for reference in groups["resolved"]:
        lines.append(reference.render())

    if groups["ambiguous"]:
        lines.append("")
        for reference in groups["ambiguous"]:
            lines.append(reference.render())

    if groups["unknown"]:
        lines.append("")
        lines.extend(reference.render() for reference in groups["unknown"])

    return "\n".join(lines)
