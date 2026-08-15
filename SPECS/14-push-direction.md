# 14 — Build the push direction (outbox to server)

Ticket: issuedb #14 — **OPEN, NOT STARTED.**

## Why

Sync is currently pull-only. `issuedb-cli sync` pulls changes from Tracker and
applies them locally, but nothing sends local changes back. `_client.py` has a
`push()` HTTP method, but **nothing builds entries from the outbox** — there is
no push command, no outbox consumer, and no CLI push.

The outbox (`sync_outbox`) is fed by triggers on every write, so the data to
push exists. What is missing is the builder that turns outbox rows into push
entries with derived uids.

## EARS SPEC

- The sync command shall push local changes to the server, so that changes made
  locally reach Tracker.
- The push shall read the `sync_outbox` and build entries for each change,
  deriving uids from the canonical form.
- The push shall send issues, tags, dependencies and relations.
- The push shall be idempotent: re-pushing an already-synced change shall not
  duplicate it.
