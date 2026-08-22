# 18 — Test fixtures leak SQLite WAL files (11.2 GB accumulated)

Ticket: issuedb #18 — **OPEN, NOT STARTED.**

## Measured

```
pytest TMPDIR total                 13 GB
  .db-wal   18,444 files        11.21 GB
  .db-shm   18,444 files         0.56 GB
  .db        2,878 files         0.68 GB
sampled 2000 .db-wal: 2000 had NO matching .db
span: 2026-08-15 → 2026-08-22   (accumulates every run)
```

## Mechanism, proven not assumed

SQLite checkpoints and **removes** the `-wal`/`-shm` on a clean close:

```
connection OPEN   ->  leak.db, leak.db-shm, leak.db-wal
after close()     ->  leak.db
```

So a fixture that never closes leaves both behind; when the temp dir is reaped
piecemeal the `.db` goes and the WAL persists — which is exactly the orphan
signature above.

**14 test files** construct an `IssueRepository` and never call
`close_connection`: `test_get_last`, `test_workspace`, `test_bulk_pattern`,
`test_repository`, `test_comments`, `test_review_fixes`, `test_enhanced_search`,
`test_dependencies`, `test_audit_regressions`, `test_git_integration`,
`test_code_refs`, `test_templates`, `test_web`, `test_duplicates`.

Direct `sqlite3.connect` calls in tests are all balanced (10 connect / 10
close) — the leak is via the `Database` singleton.

## EARS SPEC

- When a test fixture opens an `IssueRepository`, it shall close the database
  connection during teardown.
- The test suite shall leave no `.db-wal` or `.db-shm` files behind after a
  completed run.
- If a test opens a database connection outside a fixture, then it shall close
  it before the test returns.

## Why it matters beyond disk

**An unclosed connection holds a lock.** This is the same shape as Tracker's
probe holding a fixed Chrome profile directory: one run's untidy exit changes a
later run's result, and it surfaces as a symptom that points somewhere else.

It has already bitten this repo — `test_sync_apply_edges` hung on its first run
until a `conn.commit()` was added to release the write lock before `apply`'s
`BEGIN IMMEDIATE`.
