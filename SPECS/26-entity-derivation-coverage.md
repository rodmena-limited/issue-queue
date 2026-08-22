# 26 — Derivation agreement for the three entities #12 did not cover

Tickets: issuedb #12 (closed, tags) · #26 (new, the missing helper).

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

**And issuedb has no helper for it.** Nothing in the entire repo derives a
dependency uid — no `dependency_uid`, no call site, no vector pinning one. The
`idep` tag is reserved and unused. The field order above works and is written
down nowhere, so whoever builds the push direction (#14) has to guess it.
Filed as #26.

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

Per the manager's own rule, this is **PROBE BROKEN, not a pass**: an entity we
could not test is not an entity that agreed. Settling it needs a relation
created through Tracker's own write surface, where the server derives the uid —
the same move that settled tags, and one only they can make.

### A live trap noticed on the way

`symmetric_relation_types` comes back **empty** from the handshake, while both
existing relations are typed `x-test-symmetric`. `relation_uid` sorts endpoints
only for types in that set, so if the server treats a type as symmetric and the
handshake does not advertise it, the two sides derive different uids for the
same fact. The contract docstring warns about exactly this — *"one side's
symmetric set contained a test type and the other's did not"* — and the
handshake is currently advertising nothing at all. Worth confirming that empty
is intentional before push is built.

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
