# Sync client: handshake, push, pull, and cursor state

- **Ticket:** issuedb #5
- **Version:** 2.16.0
- **Modules:** `issuedb/sync/_client.py`, `issuedb/sync/_state.py`
- **Tests:** `tests/test_sync_client.py`, `tests/test_sync_state.py`
- **Contract:** Tracker `contracts/sync/PROTOCOL.md`, vectors 01–12, `faketracker.py`

## EARS spec

- Before writing anything locally, the issuedb sync client shall call `GET /v1/sync/handshake` and send `X-IssueDB-Protocol`.
- If the server's protocol range does not include the client's protocol version, then the issuedb sync client shall abort with `409 protocol_unsupported` and shall not write any local change.
- The issuedb sync client shall read the symmetric relation type set from the handshake and shall not hardcode it.
- The issuedb sync client shall store its pull cursor and replica id in `$XDG_CONFIG_HOME/issuedb/`, keyed by database path, and never inside `.issue.db`.
- If a stored cursor's project uid does not match the project uid recorded in the database, then the issuedb sync client shall discard the cursor and re-seed from zero rather than applying it.
- When a push is replayed, the issuedb sync client shall treat an `existing` outcome as success and shall not report a conflict.
- If the server responds `401 invalid_api_key` mid-sync, then the issuedb sync client shall stop, leave already-applied changes in place, and advance the cursor only to what was durably applied.
- If the server responds `409 cursor_too_old`, then the issuedb sync client shall discard its cursor and perform a full re-seed rather than a partial apply.
- If the server responds `429 rate_limited`, then the issuedb sync client shall honour `Retry-After` and shall not invent its own backoff.
- The issuedb sync client shall depend on the Python standard library only (`urllib`).

## Design decisions

**Errors branch on `code`, not on status.** Two different 409s mean opposite
things: `protocol_unsupported` means stop, `cursor_too_old` means re-seed. A
client keying on the status alone conflates them.

**The client checks the advertised range itself**, not only the server's 409. A
server that advertises a range without enforcing it would otherwise wave an
incompatible client straight through, and it would then write local rows under
a contract it does not understand.

**The client performs no local writes.** It fetches and returns parsed results;
applying them is the caller's job. That keeps the network layer testable
without a database and keeps "what was applied" a decision made in one place.

**Cursor state lives outside `.issue.db`.** A cursor in a tracked file
time-travels with the branch: rolled backward it causes a harmless re-pull;
rolled *forward* it silently skips server changes this replica never applied,
undetectably. And a replica id in a tracked file is not unique — every clone
would claim one identity.

**Keyed by path, validated by project uid.** Paths get reused. The stored state
records the `project_uid` and the cursor is discarded on mismatch: a wasted
re-pull is free if application is idempotent by uid; a misapplied cursor is
silent data loss.

## Verification

**Driven against Tracker's real FakeTracker over HTTP, with no mock transport.**
A mocked server would agree with whatever this repo believes the protocol is —
the self-confirming test this collaboration exists to prevent. FakeTracker and
all twelve vectors are vendored into `tests/data/` so the tests run rather than
skip when the Tracker checkout is absent.

All **12 vectors** replay green against the vendored fixture. **20 client tests
and 16 state tests** pass.

### A wrong assumption of mine, corrected by the fixture

Three tests failed on first run. The code was right and **my assumptions were
wrong**: I had assumed `/v1/sync/handshake` requires authentication. It is
deliberately unauthenticated, and FakeTracker documents why — a client must be
able to discover a protocol mismatch *before* it has a usable credential, or
"your issuedb is too old" becomes indistinguishable from "your key is bad" and
the user is sent to fix the wrong thing.

The auth assertions moved to push and pull, where they belong, plus a test
naming the handshake's unauthenticated design so it is not later read as a gap.

### Mutations

| Mutation | Result |
|---|---|
| Cursor kept when `project_uid` differs | 1 failed |
| Client skips its own range check | 1 failed |
| `cursor_too_old` mapped to a generic error | 2 failed |
| `Retry-After` ignored | 1 failed |

Gates: 771 tests pass, mypy clean over 71 source files, ruff clean, stdlib only.

## What the client can actually see through the live API

Asked and answered as a **separate question** from "does the schema exist",
because those come apart and the gap between them is where a green run means
nothing.

Probed live at 2026-08-15:

```
GET /_build             -> 200   {"commit":"d233c33b…"}
GET /_design            -> 200
GET /healthz            -> 200
GET /                   -> 200     <- control: the probe works
GET /v1/sync/handshake  -> 404
GET /v1/sync/pull       -> 404
GET /v1/sync/push       -> 404
```

The client itself, not curl, gets `SyncError code='http_404' status=404` on
handshake against the live server.

**Tracker's ported schema is in production; its sync API is not.** The control
endpoints returning 200 through the identical invocation are what make the 404s
evidence rather than a broken probe.

So: **this client has never successfully talked to Tracker, and cannot yet.** A
green test run here means "the fixture agrees" — nothing more.
