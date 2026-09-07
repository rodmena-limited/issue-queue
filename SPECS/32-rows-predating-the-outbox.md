# 32 — Rows predating the outbox triggers were never pushed, silently

Ticket: issuedb #29 — **FIXED in v2.34.0.** Shipped broken in 2.33.0, the
release that introduced push.

## How it was found: the operator asked whether the tool had been tested

It had not been, in the way that mattered. Every sync test in this repo builds a
**fresh** database, and the live end-to-end was one issue created seconds
earlier. Running against this repository's own accumulated `.issue.db` — which
had been sitting in the working directory the whole time — took one command:

```
issues in table          28
issues in the outbox     26
issues with NO outbox row  [1, 2]
  #1 created 2026-07-25    #2 created 2026-08-15 01:51
earliest outbox row       2026-08-15 02:31
```

Sync reported `WOULD PUSH 26` and said nothing about the other two.

## The defect

**The outbox is not the record of what the server has seen — the ledger is.**
The outbox is an event log written by triggers, so it holds only rows touched
*since those triggers were installed*. Every row that existed before the sync
migration ran has no outbox entry, and a push driven purely by the outbox skips
it forever while reporting a healthy count.

That is every existing user's entire backlog, because sync shipped after their
databases did. A row is rescued only if it happens to be edited later, which is
why 26 of 28 survived here and 2 did not.

**No test in this suite could have caught it.** A fixture creates every row
*after* the triggers exist, so the shape cannot occur. It occurs only in a
database that predates the feature.

## EARS SPEC

- When a local row has never been pushed and has no outbox entry, the sync
  command shall still offer it to the server, so that issues predating the sync
  migration are not stranded.
- The push builder shall treat the ledger, not the outbox, as the record of
  what the server has seen.
- If a row cannot be pushed, then the sync command shall report it rather than
  omit it silently.

## The fix

`unsent_rows()` enumerates pushable rows with **no ledger entry** — a complete
criterion for "the server has never seen this" — and `build_entries` backfills
them after the outbox pass, skipping any already covered.

The outbox still matters for **deletes**: a deleted row has no local row to
enumerate, so existence-based backfill cannot see it. Ledger for existence,
outbox for change.

## Verification

Same real database, same command:

```
before the fix   WOULD PUSH 26 local change(s)   (28 issues present)
after the fix    WOULD PUSH 29 local change(s)   (29 issues present)
```

Two tests, proven red by removing the backfill. The first constructs the shape
explicitly — insert a row, then delete every trace the triggers left, so it
looks like one written by an issuedb that had no outbox — with a control
asserting the outbox really is empty, or the test would pass against the broken
build for the wrong reason. The second is the counter-control: a row already in
the ledger must **not** be offered twice, so the backfill does not re-push
everything on every sync.
