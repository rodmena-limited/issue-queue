"""The frozen canonical form for sync identity.

This is the single most consequential file in the sync client. If issuedb and
Tracker derive different uids from the same row, the rows do not collide and
nothing errors — they simply become two rows that were meant to be one, in
both databases, forever. The failure has no symptom until someone notices
duplicate tags nobody created.

The form was negotiated with rodmena-tracker and frozen. Do not adjust it to
be "better"; adjust it only by agreeing a new version with the server, because
both sides must produce identical bytes.

    uid       = "s256t128:" + sha256(canonical).hexdigest()[:32]
    canonical = concat over fields of: decimal_byte_length + ":" + utf8(NFC(field))

Four decisions in that form are load-bearing, and each replaced something
that looked more obvious:

* **Length prefixes, not a separator.** The first draft joined fields with
  ``\\x1f`` on the grounds that a unit separator "cannot occur in any of our
  field values". Nothing in issuedb rejects control characters — tag names get
  at most ``.strip()`` on some paths and nothing in ``create_tag`` — so the
  claim was an assumption, never an assertion. A separator that can appear in
  a field makes the encoding ambiguous, which reintroduces exactly the
  collision the separator existed to prevent. Length prefixes make no byte
  special, so the question cannot arise.

* **No casefolding.** The first draft casefolded tag names. ``tags.name`` is
  ``TEXT UNIQUE`` with no ``COLLATE NOCASE``, so "Bug" and "bug" are two
  distinct rows in issuedb today and can both sit on one issue. Casefolding
  collapses them to one uid: local holds two, the server sees one, and the
  round trip returns one. A tag disappears silently. The rule that came out of
  it is worth stating plainly, because it generalises past this file — A
  DERIVED UID MUST REFLECT THE STORE'S OWN IDENTITY MODEL, NOT AN IMPROVED
  ONE. Changing what a tag *is* belongs in a migration with the collision
  reported to the user, never inside a hash function.

* **Truncation is named in the prefix.** ``s256t128``, not ``sha256``. 128
  bits is ample here, but a label claiming a function that does not produce
  those bytes costs somebody a day three years from now.

* **Symmetric relation endpoints are sorted, and excluded from the content
  hash.** See :func:`relation_content_hash`.

NFC normalisation is applied to every field because the same tag typed on
macOS and on Linux can be different byte sequences for the same characters.
Nothing is casefolded, so the NFC-then-casefold ordering trap does not arise;
if a field ever is folded, the order must be NFC -> casefold -> NFC, because
casefold is not closed under NFC.
"""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from collections.abc import Iterable

# Names the algorithm AND its truncation. Bump this if the form ever changes,
# so a uid carries the rule that produced it.
UID_PREFIX = "s256t128:"

# Entity tags. These are part of the hashed input, so they are wire format:
# renaming one changes every uid of that kind.
ENTITY_TAGS = {
    "issue_tag": "itag",
    "issue_dependency": "idep",
    "issue_relation": "irel",
}


def canonical_bytes(fields: Iterable[str]) -> bytes:
    """Encode fields unambiguously: ``len(field) ":" field``, concatenated.

    Length-prefixed rather than separator-joined, so no byte value is special
    and no field needs to be validated or escaped before hashing.
    """
    raw = b""
    for field in fields:
        encoded = unicodedata.normalize("NFC", field).encode("utf-8")
        raw += f"{len(encoded)}:".encode() + encoded
    return raw


def _digest(fields: Iterable[str]) -> str:
    return UID_PREFIX + hashlib.sha256(canonical_bytes(fields)).hexdigest()[:32]


def derived_uid(entity: str, *fields: str) -> str:
    """Derive the uid of a set-membership row from its identifying fields.

    Set-membership rows (a tag on an issue, a dependency between two issues)
    have no identity of their own beyond the things they relate, so their uid
    is DERIVED rather than minted. Two replicas that independently tag the
    same issue therefore produce the same uid and converge with no conflict
    machinery at all — which is the whole reason the derivation must be exact.

    Args:
        entity: One of ``issue_tag``, ``issue_dependency``, ``issue_relation``.
        fields: The identifying fields, in the order frozen in the protocol.

    Returns:
        The uid, e.g. ``s256t128:55cf7696f3df71f0cfc79f1349b0f385``.
    """
    try:
        tag = ENTITY_TAGS[entity]
    except KeyError:
        raise ValueError(
            f"unknown entity {entity!r}; expected one of {sorted(ENTITY_TAGS)}"
        ) from None
    return _digest([tag, *fields])


def mint_uid() -> str:
    """Mint a uid for a row that has identity of its own.

    An issue, a comment or a code reference is not defined by the things it
    relates, so its uid cannot be derived — two replicas writing "the same"
    comment have genuinely written two comments. These get a random uid at
    creation, which then never changes.

    ``uuid4`` is used for its entropy only; the value is formatted like every
    other uid so that consumers never have to branch on which kind they hold.
    """
    return _digest([uuid.uuid4().hex])


def relation_uid(
    project_uid: str,
    source_uid: str,
    relation_type: str,
    target_uid: str,
    symmetric_types: Iterable[str] = (),
) -> str:
    """Derive a relation's uid, sorting the endpoints for symmetric types.

    ``issue_relations`` stores a direction — ``UNIQUE(source_issue_id,
    target_issue_id, relation_type)`` — but several relation types mean the
    same thing both ways round. Two replicas recording "A relates_to B" and "B
    relates_to A" have recorded ONE fact, so for those types the endpoints are
    sorted before hashing and both produce the same uid.

    ``symmetric_types`` is a PARAMETER, read from the server handshake, and is
    deliberately not a constant in this file. issuedb and Tracker once
    disagreed on a derivation precisely because one side's symmetric set
    contained a test type and the other's did not — both implementations
    correct, the contract silently ambiguous. A hardcoded set here would
    rebuild that trap and would also mean the contract could not change
    without a client release.
    """
    if relation_type in set(symmetric_types):
        source_uid, target_uid = min(source_uid, target_uid), max(source_uid, target_uid)
    return derived_uid("issue_relation", project_uid, source_uid, relation_type, target_uid)


def dependency_uid(project_uid: str, blocker_uid: str, blocked_uid: str) -> str:
    """Derive a dependency's uid: ``(project_uid, blocker_uid, blocked_uid)``.

    A dependency is directional and stays directional — "A blocks B" is not
    "B blocks A" — so unlike :func:`relation_uid` the endpoints are never
    sorted. Reversing them must produce a different uid, and a test asserts
    that rather than leaving it implied.

    THE FIELD ORDER HERE IS **MEASURED, NOT SPECIFIED**, and the distinction
    matters. Until this function existed, nothing in issuedb derived a
    dependency uid at all: ``idep`` sat in :data:`ENTITY_TAGS` unused, with no
    helper, no call site and no vector. The order below was established
    empirically against Tracker's live feed — all 16 server-derived
    dependencies matched ``(project, blocker, blocked)`` and none matched the
    reverse — and `tracker-fbe1b4` has correctly noted that **an observed order
    does not become the contract until PROTOCOL.md says so.**

    So: this reproduces what the counterpart does today, and the frozen vector
    pins it against the value THE SERVER produced rather than against our own
    output. If PROTOCOL.md later specifies a different order, this is the
    defect and the vector is the evidence of when it diverged — which is the
    situation the whole canonical form exists to make visible instead of
    silent.
    """
    return derived_uid("issue_dependency", project_uid, blocker_uid, blocked_uid)


def relation_content_hash(
    source_uid: str,
    relation_type: str,
    target_uid: str,
    symmetric_types: Iterable[str] = (),
    **extra: str,
) -> str:
    """The content hash of a relation, excluding the endpoints when symmetric.

    Sorting the endpoints fixes IDENTITY and leaves DIRECTION undefined, and
    the table stores a direction. Two replicas push A->B and B->A: same uid,
    different payloads. Push is idempotent by ``(uid, content_hash)``, so if
    the endpoints were part of the hash the second push would look like
    "known uid, new content" — an ordinary UPDATE — and the stored direction
    would flip on every single sync. That flip is silent and permanent, and it
    arrives by faithfully implementing the idempotency rule.

    Excluding the endpoints from the hash for symmetric types makes the
    opposite direction a genuine REPLAY: identical uid, identical content
    hash, so the frozen idempotency clause fires unmodified and "no-op, return
    the existing row" falls out of it. No special case on either side, and the
    property holds structurally rather than because two codebases each
    remembered a caveat.

    The direction still travels in the payload and is still stored. It is
    simply not part of what identifies the version.
    """
    if relation_type in set(symmetric_types):
        source_uid, target_uid = min(source_uid, target_uid), max(source_uid, target_uid)
    fields = [
        source_uid,
        relation_type,
        target_uid,
        *(f"{key}={value}" for key, value in sorted(extra.items())),
    ]
    return _digest(fields)
