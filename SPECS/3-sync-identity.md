# Sync identity: canonical uids, the sync_row ledger, and the sync_outbox feed

- **Ticket:** issuedb #3
- **Version:** 2.14.0
- **Commits:** `1615d77` (canonical form), `1e7b00c` (prune guard), plus this increment
- **Modules:** `issuedb/sync/_canonical.py`, `issuedb/sync/_ledger.py`, migration 2
- **Tests:** `tests/test_sync_canonical.py`, `tests/test_sync_ledger.py`
- **Contract:** Tracker `contracts/sync/PROTOCOL.md`, frozen canonical form, vectors 01–12

## EARS spec

- The issuedb sync layer shall derive a uid for a set-membership row from its identifying fields using the frozen canonical form: length-prefixed NFC-normalised UTF-8 fields, no separator, prefixed `s256t128:` and truncated to 128 bits of SHA-256.
- Where a relation type is declared symmetric, the issuedb sync layer shall sort the two endpoint uids before deriving the relation uid and before computing its content hash.
- The issuedb sync layer shall read the set of symmetric relation types from the server handshake and shall not hardcode it.
- The issuedb sync layer shall record a uid for every syncable row in a `sync_row` ledger that has no foreign keys, so the ledger survives cascade deletes and can emit tombstones.
- When a syncable row is inserted, updated or deleted by any code path, the issuedb database shall record the change in a `sync_outbox` table by SQLite trigger.
- If a row is deleted, then the issuedb sync layer shall retain its uid in the ledger as a tombstone and shall not remove the ledger entry.
- When the ledger is backfilled over a pre-existing database, the issuedb sync layer shall tolerate two or more rows deriving the same uid and shall report them rather than discarding either.
- If a reference is ambiguous between two or more issues, then issuedb shall present every candidate and shall select none.
- The issuedb sync layer shall depend on the Python standard library only.

## Design decisions

**`sync_row` has no foreign keys.** Every other child table declares
`REFERENCES issues(id) ON DELETE CASCADE`. The ledger must not: an entry has to
*outlive* the row it describes, because the fact that uid X existed and is now
gone is exactly what the server needs. A cascaded-away tombstone is a deletion
that never propagates, and the row returns on the next sync from any replica
that still holds it.

**`sync_row.uid` is not UNIQUE.** This took a live reproduction.
`link_issues(A, B, 'relates_to')` and `link_issues(B, A, 'relates_to')` both
succeed today — `UNIQUE(source, target, type)` does not stop them, the tuples
differ — so a database written before uids existed can already hold two rows
deriving *one* uid under the symmetric rule. A UNIQUE index fails the backfill
on real user data; "fixing" it with `INSERT OR IGNORE` silently drops one of
the two. `find_uid_collisions()` reports them instead, and never merges: merging
means choosing which `created_at` to destroy and which direction the user did
not mean.

**`resolve_uid()` returns a list, deliberately.** Per the manager's frozen rule,
an ambiguous reference presents every candidate and selects none. Handing back
an arbitrary winner is how a reference starts pointing at somebody else's row
with nothing erroring.

**The outbox is fed by triggers, not by the repository layer.** issuedb has four
write paths that share no Python: the CLI, the Flask UI, a user with `sqlite3`,
and an *older installed issuedb* writing to the same file — normal here, since
22 of 42 repos in this estate commit `.issue.db` to git. A trigger fires for all
of them. A Python-maintained outbox is silently incomplete for exactly the writes
nobody remembered to instrument.

## Verification

**Cross-implementation check.** issuedb's canonical form was run against
Tracker's independently authored expected uids at Tracker `c1cb9b5`: **10 of 10
agree**. Two implementations, two repos, two authors, identical bytes. Vectors
vendored into `tests/data/` so the check runs in CI rather than skipping.

Agreement is evidence about the *specification's clarity*, not proof that either
implementation is correct.

**Sensitivity, which the pass rate conceals.** Mutating the implementation:

| Mutation | Derivations caught |
|---|---|
| Separator instead of length prefix | 10 of 10 |
| Casefold reintroduced (the C1 data-loss defect) | **1 of 10** |
| Symmetric sorting dropped | 1 of 10 |

A pass rate is not a sensitivity. Vector 07 is the only entry carrying a
case-variant tag, so it is load-bearing and guarded by a test that fails if it is
pruned — not by a comment, which cannot stop a prune.

**Ledger and trigger mutations:**

| Mutation | Result |
|---|---|
| `uid` made UNIQUE | 4 failed |
| Tombstone deletes instead of marking | 1 failed |
| DELETE triggers dropped | 2 failed |
| `find_uid_collisions` returns nothing | 1 failed |
| `issue_tags` trigger records `rowid` not `issue_id` | **survived — test was vacuous** |

The last one is worth recording. The test asserted `local_id is not None`, which
`rowid` satisfies too: it checked the shape of the container rather than the
value in it. Rewritten to assert the identity, with two issues so the assertion
can discriminate, and it now catches the mutation. `issue_tags` rowids are not
stable across a `VACUUM`, so an outbox row naming one points at nothing
afterwards.

**Behaviours verified live rather than assumed:**

- a write from a raw `sqlite3` connection, never touching issuedb, is captured
- an external UPDATE and DELETE are captured
- **cascade-deleted children fire their triggers** — if they did not, child
  tombstones would never propagate and other replicas would keep rows the server
  believes are gone
- a real pre-ladder database (`user_version` 0, with data) upgrades to version 2
  with data intact, triggers installed, and an **empty outbox** — the migration
  must not fabricate changes

Gates: 700 tests pass, mypy clean over 67 source files, ruff clean, stdlib only.

## Not yet done

No network code exists. Nothing here has been run against Tracker, and Tracker's
`/v1/sync/*` endpoints are not implemented. The ported schema is real in
Tracker's code and **not yet in its production database** — when a client is
first pointed at it, which tables actually exist must be verified before any
claim that sync works.
