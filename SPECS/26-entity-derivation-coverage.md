# 26 — Derivation agreement for the three entities #12 did not cover

Tickets: issuedb #12 (closed, tags) · **#25** (the missing helper — closed in v2.30.0).

> Numbering note: this file is `SPECS/26` but the ticket is **#25**. The spec files
> and the ticket ids drifted apart earlier and are not expected to match; the ticket
> id above is the authoritative one.

`tracker-manager-0e2462` asked for `issue`, `issue_relation` and
`issue_dependency`, since each has a different field tuple and nothing about
the tag result transfers.

## `issue` — the question does not apply

`ENTITY_TAGS` holds exactly three entries: `itag`, `idep`, `irel`. **Issue uids
are minted, not derived** (`mint_uid()`, a uuid4). Two replicas creating "the
same" issue have genuinely created two issues, which is the documented
intent — so there is no derivation for the two implementations to agree or
disagree about. Reported as *not applicable* rather than as a pass.

## `issue_dependency` — AGREEMENT ESTABLISHED, 16/16

The 16 live dependencies in the feed all sit between **genuine roadmap
issues** (#2–#7, real titles, 41-char server content hashes), so their uids
were derived by Tracker rather than supplied by a sync client. That provenance
check is what makes the comparison meaningful; without it the match would be
the same tautology the tag round trip hit.

```
(project_uid, blocker, blocked)   16/16 match
(project_uid, blocked, blocker)    0/16 match   <- discrimination control
```

Reversing the endpoints matching **zero** is what rules out a degenerate
derivation. Cross-implementation agreement for `issue_dependency` is measured.

**And issuedb had no helper for it.** Nothing in the repo derived a dependency
uid — no `dependency_uid`, no call site, no vector pinning one. The `idep` tag
was reserved and unused, so whoever built the push direction (#14) would have
had to guess the order.

**Fixed in v2.30.0.** `dependency_uid(project_uid, blocker_uid, blocked_uid)`,
exported from `issuedb.sync`, with
`tests/data/vectors_issuedb/14-dependency-uid-derivation.json` pinning it
against **the uid the server produced** rather than against our own output — a
vector expecting our own value would pass against any field order, including a
wrong one, because both sides of the comparison move together.

Re-verified against the live server after shipping: the released helper
reproduces **16/16** stored uids, the reversed order **0/16**. Proven red by
reversing the order (3 tests fail) and by dropping `project_uid` (3 tests fail).

Scope, honouring `tracker-fbe1b4`: **PROTOCOL.md does not specify this order.**
An observed order is not the contract. The vector records what the counterpart
does today so a divergence becomes visible rather than silent.
Filed as **#25**, and fixed in v2.30.0 — see the closing note below.

## `issue_relation` — INCONCLUSIVE, and it is our debris

Both live relations are typed `x-test-symmetric` and **both endpoints are our
own tombstoned probe issues** (#910013–910016, stub content hashes). They were
pushed by a sync client, so the stored uid is the one the client sent — the
same premise failure as the tag round trip, and the reason a mismatch here
proves nothing.

For the record, none of six candidate tuples reproduced the stored uid, and
**our `relation_content_hash` did not reproduce the stored content hash
either** — consistent with rows written by something that was not implementing
this contract.

The manager suggested the misses were explained by our candidates assuming
sorting for `x-test-symmetric`. **They were not**: the six covered both
orderings explicitly —

```
(P, src, type, tgt)        unsorted        (P, type, src, tgt)
(P, lo,  type, hi)         sorted          (P, src, tgt, type)
(src, type, tgt) no proj   unsorted        (lo, type, hi) no proj   sorted
```

The likelier explanation is simpler and fits the content hash missing too:
**those rows carry uids that were invented rather than derived**, pushed by our
own throwaway apply-verification scripts — the same scripts that produced the 16
orphan issues. Nothing can reconstruct an arbitrary value, so no tuple could
have matched.

Per the manager's own rule, this is **PROBE BROKEN, not a pass**: an entity we
could not test is not an entity that agreed. Settling it needs a relation
created through Tracker's own write surface, where the server derives the uid —
the same move that settled tags, and one only they can make.

### The empty symmetric set: ANSWERED, and it is intentional

We flagged `symmetric_relation_types: []` as a possible trap.
`tracker-manager-0e2462` answered it from their source:

```
canonical.py:47   SYMMETRIC_RELATION_TYPES: Final[frozenset[str]] = frozenset()
live handshake    "symmetric_relation_types": []
```

**Production's symmetric set is deliberately empty**, and `x-test-symmetric` is
symmetric only in the fixtures — the vectors use a provisional type precisely so
they do not exercise a path no production data can reach. Source and served
agree. Closed, not a defect.

### Relations are advertised on the wire and cannot be created

Verified here independently, from the handshake this repo actually receives:

```
entities: ["issue", "issue_tag", "issue_dependency", "issue_relation"]
```

Four advertised. `tracker-manager-0e2462` enumerated all 28 POST/DELETE paths in
their product and found **no relations route** — dependencies have one
(`POST /issues/{key}/dependencies`, the control proving the grep works), relations
do not. The only way a relation can exist in Tracker is a sync push.

That is why the only live relations were our probe rows, and it makes the
`issue_relation` verdict **unresolvable from either side today** rather than
merely untested. Theirs to close; recorded here because it bounds what our
coverage can ever claim.

## Cleanup

The relation rows above were dangling on tombstoned issues, left by our own
sweep. Deleted, with the same two-part discriminator (both endpoints are our
tombstoned probe issues; everything else left alone).

```
dangling live rows pointing at tombstoned issues
  issue_tag 0 · issue_relation 0 · issue_dependency 0 · live issues 209
```

That is the third round of our debris found by re-measuring rather than by
trusting a previous "cleanup complete".

## Independently verified, and the reversed direction is now pinned too (v2.31.1)

`tracker-manager-0e2462` ran both implementations side by side in one process
and checked the frozen vector against Tracker rather than against us:

```
issuedb dependency_uid(proj, a, b)   s256t128:7da4253e7ab609dbba1d3ccb5ae0a76b
Tracker dependency_uid(proj, a, b)   s256t128:7da4253e7ab609dbba1d3ccb5ae0a76b   AGREE
issuedb reversed (b, a)              s256t128:fdd3517cdd41945126d906da1236fc25
Tracker reversed (b, a)              s256t128:fdd3517cdd41945126d906da1236fc25   AGREE
```

Their report carried a value we did not have: **Tracker's own uid for the
reversed order of our vector's case 1**,
`s256t128:daf1cd11f6bd12b9bce749d51dffbd80`. Confirmed equal to ours and pinned.

That closes a real weakness. Case 1 previously asserted only
`expected_uid_differs_from` — **an inequality is satisfied by any other value**,
including one produced by a field order neither implementation uses. Both
directions are now cross-implementation pins.

Proven red: reversing the helper's field order fails 4 tests, including the new
one.

