"""The issue_dependency derivation, pinned against Tracker's own output.

Until `dependency_uid` existed, nothing in issuedb derived a dependency uid:
`idep` sat in ENTITY_TAGS with no helper, no call site and no vector, so the
field order the push direction (#14) would need was undefined.

**The expected uid in the vector was produced by Tracker's server, not by this
codebase.** A vector whose expected value came from our own function would be
self-confirming — it would pass against any field order, including a wrong one,
because both sides of the comparison would move together.
"""

import json
import pathlib
import unicodedata

import pytest

from issuedb.sync import dependency_uid, derived_uid

VECTOR = (
    pathlib.Path(__file__).parent
    / "data"
    / "vectors_issuedb"
    / "14-dependency-uid-derivation.json"
)


@pytest.fixture(scope="module")
def vector() -> dict:
    return json.loads(VECTOR.read_text())


def test_vector_is_present_and_shaped(vector):
    """Control: if the file were missing or empty the tests below would vacuously pass."""
    assert vector["cases"], "no cases in the vector"
    assert len(vector["cases"]) == 2
    assert vector["provenance"]["measured_against"].startswith("https://")


def test_matches_the_uid_the_server_produced(vector):
    """The cross-implementation pin. This value did not come from our code."""
    case = vector["cases"][0]
    f = case["fields"]
    assert dependency_uid(f["project_uid"], f["blocker_uid"], f["blocked_uid"]) == (
        case["expected_uid"]
    )


def test_reversing_the_endpoints_does_not_collide(vector):
    """A dependency is directional; if this collided a cycle would be unrepresentable."""
    case = vector["cases"][1]
    f = case["fields"]
    got = dependency_uid(f["project_uid"], f["blocker_uid"], f["blocked_uid"])
    assert got != case["expected_uid_differs_from"]


def test_the_reversed_order_is_also_pinned_to_tracker(vector):
    """Both directions are cross-implementation pins, not just the forward one.

    Asserting only "the reversal differs" would be satisfied by ANY other value,
    including one produced by a field order neither implementation uses. The
    positive value here was derived by Tracker's canonical.py and reported by
    `tracker-manager-0e2462`; it is pinned so a divergence in the reversed
    direction is caught too.
    """
    case = vector["cases"][1]
    f = case["fields"]
    assert dependency_uid(f["project_uid"], f["blocker_uid"], f["blocked_uid"]) == (
        case["expected_uid"]
    )


def test_the_two_orders_really_are_different_inputs(vector):
    """Control for the test above: it is only meaningful if the endpoints differ."""
    a, b = vector["cases"][0]["fields"], vector["cases"][1]["fields"]
    assert a["blocker_uid"] == b["blocked_uid"]
    assert a["blocked_uid"] == b["blocker_uid"]
    assert a["blocker_uid"] != a["blocked_uid"]


def test_helper_agrees_with_the_raw_derivation():
    """The helper is a named field order, not a second algorithm."""
    assert dependency_uid("p", "b1", "b2") == derived_uid("issue_dependency", "p", "b1", "b2")


def test_project_uid_participates():
    """Two projects must not share a dependency uid for the same endpoints."""
    assert dependency_uid("p1", "a", "b") != dependency_uid("p2", "a", "b")


def test_fields_are_nfc_normalised():
    """Inherited from canonical_bytes, asserted here so a change to it fails loudly."""
    composed = unicodedata.normalize("NFC", "café")
    decomposed = unicodedata.normalize("NFD", "café")
    assert composed != decomposed
    assert dependency_uid("p", composed, "b") == dependency_uid("p", decomposed, "b")
