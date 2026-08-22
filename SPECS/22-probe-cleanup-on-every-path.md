# 22 — The NFC probe wrote to a peer's production database and cleaned up on no path

Ticket: issuedb #22 — **FIXED and verified by counting.**

## Why

`tracker-fbe1b4` found that `process.exit()` skips JavaScript `finally` blocks,
so in their four browser probes the **INCONCLUSIVE exit was the only path that
leaked** — 104 headless Chrome processes, presenting as unrelated probes timing
out. Pass cleaned up. Fail cleaned up. Refusing to conclude did not.

Checked ours for the same shape. Python's `sys.exit` *does* run `finally`, so
the mechanism does not transfer — **but the outcome was worse.**
`audit/evaluations/nfc_cross_impl.py` had **no cleanup on any path at all**, and
the rows it creates are not local temp files: they are issues and tags in
**Tracker's production database**.

Measured through the sync pull API (not the DB):

```
entity mix    issue 443 · issue_tag 223 · issue_dependency 17 · issue_relation 3
probe issues       2   live 0   tombstoned 2
probe tag rows     4   live 0   tombstoned 4
```

Six rows, all already tombstoned — **a peer cleaned up after us.** The debris
was real and someone else paid for it.

Theirs was asymmetric and local; ours was total and in someone else's data. The
lesson generalises past the language: *the exit that admits it learned nothing
is the one whose cleanup nobody exercises.*

## EARS SPEC

- The NFC cross-implementation probe shall delete every row it created on the
  server, on every exit path, so that an inconclusive run leaves no more debris
  than a conclusive one.
- If a cleanup delete does not return the `deleted` outcome, then the probe
  shall report the failure on stderr rather than exit silently.
- Where a probe writes to a server it does not own, the probe shall record what
  it created at the moment the server confirms the write, so that cleanup
  covers rows created before the failure point.

## The fix

`_probe()` threads a `created` ledger and appends **when the server confirms**,
not when the request is sent. `main()` is a `try/finally` around it; `_shed()`
deletes in reverse order and prints failures to stderr.

The rows cannot be reused between runs — the probe needs a uid the server has
never seen, or the "was the first push novel?" control is vacuous — so
idempotent fixed uids were not an option for the tags. Cleanup was.

## Verification — a known positive, then both directions

`op: "delete"` was **not** an op this codebase had ever emitted (only `upsert`,
6 occurrences). Established before relying on it:

```
create            -> outcome "created"   number 910024
op "delete"       -> outcome "deleted"
op "tombstone"    -> SyncError invalid_request   <- a typo fails LOUDLY
op "remove"       -> SyncError invalid_request
pull afterwards   -> deleted=True seq=1110       <- the EFFECT, not the return code
```

Then the leaking path itself, forced by mangling the final push outcome so the
run exits `PROBE BROKEN` **after** three rows exist:

```
                              live probe debris   control (live issues)
before                                        0                     225
forced PROBE BROKEN, cleanup ON               0                     225   cleanup: 2/2
forced PROBE BROKEN, cleanup OFF              2                     226   <- goes RED
after sweeping                                0                     225
real run, verdict AGREE                       0                     225   cleanup: 3/3
```

**The counter was shown to go red before it was trusted to say zero.** With
cleanup disabled it reports 2; with it enabled, 0.

## What this does not cover

`first_contact_probe.py`, `schema_drift.py` and `vector_replay.py` were checked
for `push` calls and create nothing server-side, so they have nothing to shed.
That is a **read of the code**, not a measured zero — the counter above would
catch them if it were run around each, and it has not been.
