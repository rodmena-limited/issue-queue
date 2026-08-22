# 24 — Ten files breach the 550-line hard cap

Ticket: issuedb #24 — **OPEN, NOT STARTED.** Filed, not fixed: nine refactors
is a scoped piece of work, not a drive-by.

## Why

The standing rule is **500 lines soft, 550 hard** for source files, excluding
generated artifacts, fixtures, lockfiles and data blobs. Measured across
`issuedb/`, `audit/` and `tests/`:

```
922  tests/data/faketracker.py            <- FIXTURE, exempt
746  audit/evaluations/first_contact_probe.py
676  tests/test_git_integration.py
615  tests/test_similarity.py
598  issuedb/sync/_apply.py                <- shipped package
593  issuedb/cli/_main.py                  <- shipped package
591  tests/test_sync_apply.py
575  tests/test_web.py
561  tests/test_time_tracking.py
554  tests/test_code_refs.py
```

Nine files over the hard cap once the fixture is excluded, **two of them inside
the shipped package**. All pre-date this session; `first_contact_probe.py` was
718 lines before the cleanup fix pushed it to 746.

## EARS SPEC

- The repository shall keep every source file at or below 550 lines, so that no
  file crosses the project's hard cap.
- Where a file exceeds 500 lines, the repository shall record it as due for
  refactoring before it is extended further.
- If a source file would cross 550 lines, then the change shall split or
  extract instead of appending.

## Note on splitting the probe

`first_contact_probe.py` has been split once before in this session and the
split was wrong twice — both attempts printed `ROUND TRIP FAILED` against a
working server because the extracted boundaries cut through shared state. Any
split of that file needs the round trip re-run against the live server
afterwards, not just an import check.

## Suggested enforcement

A test asserting the cap would keep this from recurring, and unlike the audit
above it would run on every commit. It must be written with a known-positive:
a cap test that reports zero because its glob matched nothing looks exactly
like a clean repository (see `SPECS/verification-gaps.md`, entry 14).
