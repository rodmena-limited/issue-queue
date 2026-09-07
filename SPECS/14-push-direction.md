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

---

## Protocol input from Tracker (2026-09-07) — the client must send its project_uid

`tracker-fbe1b4` pushed back on a claim we made, and they were right. We said a
database already carrying a project will not silently adopt another, so the
"two repos, one key, one merged backlog" case is constrained. **It is not.**

Verified in our own code rather than reasoned about:

```
record_project_uid()   the guard is `if existing is not None:` — it raises only when the
                       database ALREADY holds a different uid. On a FRESH database
                       `existing is None`, so it records whatever the server supplied.
handshake()            a bare GET with NO client-supplied parameters. The client sends
                       nothing, so the server can only answer from the API key.
```

Their case, which our write-once property cannot touch:

```
repo A  synced, sync_project holds project P
repo B  FRESH .issue.db, no sync_project row, same trk_ key
        B syncs -> server answers P (the key names it) -> B records P write-once
```

**B is permanently bound to A's backlog and nothing errors on either side**,
because B had nothing to defend. Write-once protects an *existing* binding, not
a *first* one — a local guarantee where an end-to-end one is needed.

### What push must therefore carry

Requested by Tracker, to be built with push and not before:

- the client **sends** `sync_project.project_uid` on handshake or push, and
  **omits it when it has none**;
- the server honours it when present, mints and returns one when absent, and
  refuses when it names a project the key may not touch.

That turns our write-once property into an end-to-end guarantee. It is a client
change too: `handshake()` currently sends nothing at all.

**Blocked on #28.** Whether `project_uid` even survives a clone depends on
whether `.issue.db` is committed, which nothing documents and this repo's
`.gitignore` forbids. Settle #28 before designing the wire format, or the
identity being put on the wire may not be the one that persists.
