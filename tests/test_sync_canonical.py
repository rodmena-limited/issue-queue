"""Tests for the frozen canonical uid form.

The most valuable test in this file is the CROSS-IMPLEMENTATION one: issuedb's
derivation is checked against Tracker's independently written expectations. Two
implementations, two repos, two authors agreeing on the same bytes is the only
real evidence that the specification is unambiguous — a suite written against
our own implementation would agree with itself no matter what the spec said.

That failure mode is not hypothetical here. Tracker's server and Tracker's own
FakeTracker once derived different uids from the same row, both correct against
their reading, because the contract left the symmetric-type set implicit.
Nothing errored; it was found by comparing two implementations.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from issuedb.sync import (
    UID_PREFIX,
    canonical_bytes,
    derived_uid,
    mint_uid,
    relation_content_hash,
    relation_uid,
)

VECTORS = pathlib.Path(__file__).parent / "data" / "tracker_uid_vectors.json"


def _load():
    data = json.loads(VECTORS.read_text())
    return data["derivations"]


def _derive(entry):
    fields = entry["fields"]
    symmetric = entry["symmetric_types"]
    kind = entry["kind"]
    if kind == "relation_content_hash":
        return relation_content_hash(*fields[:3], symmetric_types=symmetric)
    if kind == "issue_relation":
        return relation_uid(*fields[:4], symmetric_types=symmetric)
    return derived_uid(kind, *fields)


# --- the cross-implementation check ---------------------------------------


def test_the_vector_file_is_present_and_populated():
    """The control for every test below.

    If the vendored file went missing or empty, the parametrised test would
    collect zero cases and the suite would report success while checking
    nothing against Tracker at all.
    """
    assert VECTORS.exists(), f"vendored Tracker vectors missing at {VECTORS}"
    derivations = _load()
    assert len(derivations) >= 10, f"expected >=10 derivations, got {len(derivations)}"
    assert all(d["expect"].startswith(UID_PREFIX) for d in derivations)


@pytest.mark.parametrize("entry", _load(), ids=lambda e: f"{e['vector']}:{e['kind']}")
def test_agrees_with_trackers_frozen_derivation(entry):
    """issuedb's uid must equal Tracker's, byte for byte.

    A mismatch means the two sides would create two rows where one was meant,
    in both databases, with no error at any point.
    """
    assert _derive(entry) == entry["expect"]


# --- the properties the form exists to provide ----------------------------


def test_case_variant_tags_derive_different_uids():
    """tags.name is byte-exact in issuedb, so the uid must be too.

    Casefolding here would collapse "Bug" and "bug" — two legal rows today —
    into one uid, and a tag would silently vanish on a round trip.
    """
    upper = derived_uid("issue_tag", "p", "i", "Bug")
    lower = derived_uid("issue_tag", "p", "i", "bug")
    assert upper != lower


def test_two_replicas_tagging_the_same_issue_converge():
    assert derived_uid("issue_tag", "p", "i", "bug") == derived_uid("issue_tag", "p", "i", "bug")


def test_length_prefixing_removes_field_boundary_ambiguity():
    """Fields that concatenate to the same string must still differ.

    With a separator-joined encoding these two collide as soon as a field
    contains the separator; nothing in issuedb forbids that byte.
    """
    assert derived_uid("issue_tag", "p", "i", "ab") != derived_uid("issue_tag", "p", "ia", "b")


def test_a_control_character_in_a_field_is_hashed_not_rejected():
    """The unit separator is just data under length prefixing."""
    with_sep = derived_uid("issue_tag", "p", "i", "a\x1fb")
    assert with_sep.startswith(UID_PREFIX)
    assert with_sep != derived_uid("issue_tag", "p", "i", "ab")


def test_nfc_normalisation_makes_equivalent_spellings_equal():
    """The same characters typed on macOS and Linux must hash the same."""
    composed = "café"  # é as one code point
    decomposed = "café"  # e + combining acute
    assert composed != decomposed
    assert derived_uid("issue_tag", "p", "i", composed) == derived_uid(
        "issue_tag", "p", "i", decomposed
    )


def test_uid_shape():
    uid = derived_uid("issue_tag", "p", "i", "bug")
    assert uid.startswith(UID_PREFIX)
    assert len(uid) == len(UID_PREFIX) + 32
    int(uid[len(UID_PREFIX) :], 16)  # hex, or this raises


def test_unknown_entity_is_rejected():
    with pytest.raises(ValueError, match="unknown entity"):
        derived_uid("not_an_entity", "p")


def test_canonical_bytes_are_length_prefixed():
    assert canonical_bytes(["ab", "c"]) == b"2:ab1:c"
    assert canonical_bytes([]) == b""


# --- symmetry -------------------------------------------------------------

SYM = ["x-test-symmetric"]


def test_symmetric_relation_converges_from_either_direction():
    forward = relation_uid("p", "aaa", "x-test-symmetric", "bbb", symmetric_types=SYM)
    reverse = relation_uid("p", "bbb", "x-test-symmetric", "aaa", symmetric_types=SYM)
    assert forward == reverse


def test_directional_relation_does_not_converge():
    forward = relation_uid("p", "aaa", "blocks", "bbb", symmetric_types=SYM)
    reverse = relation_uid("p", "bbb", "blocks", "aaa", symmetric_types=SYM)
    assert forward != reverse


def test_symmetric_set_is_a_parameter_not_a_constant():
    """The same type is symmetric or not depending on the handshake.

    Hardcoding the set is what made Tracker's own two implementations
    disagree, and it would mean the contract could not change without a
    client release.
    """
    as_symmetric = relation_uid("p", "bbb", "relates_to", "aaa", symmetric_types=["relates_to"])
    as_directional = relation_uid("p", "bbb", "relates_to", "aaa", symmetric_types=[])
    assert as_symmetric != as_directional


def test_opposite_directions_share_a_content_hash_when_symmetric():
    """D3: this is what makes an opposite-direction push a genuine replay.

    If these differed, a correct implementation of "idempotent by (uid,
    content_hash)" would treat the reverse push as an UPDATE and flip the
    stored direction on every sync.
    """
    forward = relation_content_hash("aaa", "x-test-symmetric", "bbb", symmetric_types=SYM)
    reverse = relation_content_hash("bbb", "x-test-symmetric", "aaa", symmetric_types=SYM)
    assert forward == reverse


def test_opposite_directions_differ_when_directional():
    forward = relation_content_hash("aaa", "blocks", "bbb", symmetric_types=SYM)
    reverse = relation_content_hash("bbb", "blocks", "aaa", symmetric_types=SYM)
    assert forward != reverse


def test_content_hash_covers_extra_payload_fields():
    bare = relation_content_hash("aaa", "blocks", "bbb")
    annotated = relation_content_hash("aaa", "blocks", "bbb", note="why")
    assert bare != annotated


# --- minted uids ----------------------------------------------------------


def test_minted_uids_are_unique_and_shaped_like_derived_ones():
    """Rows with identity of their own cannot derive a uid.

    Two replicas writing "the same" comment have written two comments, so a
    derivation would wrongly merge them.
    """
    minted = {mint_uid() for _ in range(500)}
    assert len(minted) == 500
    assert all(uid.startswith(UID_PREFIX) and len(uid) == len(UID_PREFIX) + 32 for uid in minted)
