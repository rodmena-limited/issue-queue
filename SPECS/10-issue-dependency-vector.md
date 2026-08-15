# 10 — Cover `issue_dependency` on the wire with an issuedb-authored vector

Ticket: issuedb #10

## Why

`issue_dependency` is advertised by Tracker's handshake and exercised by **zero**
of the twelve vendored vectors. That is the exact shape of the `issue_tag`
defect: `issue_tags` held `SELECT/INSERT/DELETE` and lacked `UPDATE`, which was
correct until the sync work added `row_version` and `sync_content_hash` and made
the row updatable — and because nothing exercised the path, it surfaced as a
live HTTP 500 the first time a real client pushed one. `issue_dependencies` has
its `UPDATE` grant only by luck of the original migration, and luck is not a
control.

A pull of the whole feed from `c:0` confirmed the gap empirically: 163 `issue`,
15 `issue_relation`, 3 `issue_tag`, and **0** `issue_dependency` rows had ever
existed on the server.

## EARS SPEC

- The issuedb vector replay shall exercise every entity the Tracker handshake
  advertises, including `issue_dependency`.
- When a sync entity is advertised by the server and exercised by no vendored
  vector, the issuedb replay shall carry its own vector for that entity rather
  than leaving the capability silently uncovered.
- The issuedb-authored vectors shall live outside `tests/data/vectors/`, so that
  Tracker's frozen expectations are never confused with issuedb's reading of the
  protocol.
- While replaying, the harness shall label each vector's provenance in its
  output.
- If the vendored vector set is smaller than twelve, then the harness shall
  report `PROBE BROKEN` and refuse to run, and issuedb-authored vectors shall
  not count toward that control.
- The `issue_dependency` vector shall exercise both paths that require an
  `UPDATE` privilege: the upsert content-hash re-stamp and the tombstone write.
- The `issue_dependency` vector shall push the endpoints reversed when testing a
  tombstone response, so that an echoed caller payload and a correctly derived
  one are distinguishable.

## Verification

Against the live server at `b933e47`:

| Step | Result |
|---|---|
| create | `created` v1 |
| replay, same content_hash | `existing` v1 — no spurious bump |
| re-stamp, new content_hash | `updated` v2 — **the UPDATE path that 500'd on `issue_tags`** |
| delete | `deleted` v3 — the tombstone UPDATE path |
| push after tombstone, endpoints **reversed** | `gone`, `deleted`, `restorable`, tombstone payload in the **original** order |
| pull from `c:0` | stored row `deleted=true`, `content_hash=dep-h2` — the refused push wrote nothing |

**Proven able to go red**, not merely green: rewriting step 5's expectation to
encode the echo-the-caller defect makes the vector FAIL on exactly that
assertion, and restoring it makes it pass.

The payload field names (`blocker`, `blocked`) were **learned from the server**
by pushing candidate shapes and keeping the one it accepted — `openapi.yaml`
names the entity in an enum and gives no example. They are independently
corroborated by `tests/data/faketracker.py`, which maps `issue_dependency` to
`("blocker", "blocked")`.
