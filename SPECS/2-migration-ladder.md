# Forward-only schema migration ladder

- **Ticket:** issuedb #2
- **Status:** closed
- **Version:** 2.13.0
- **Module:** `issuedb/database/_migrations.py`
- **Tests:** `tests/test_migrations.py`

## Why

Before this, `PRAGMA user_version` was 0 and `_add_column_if_missing`
(`issuedb/database/_schema.py:14`) was the only migration tool. That re-derives
"what is missing?" by inspecting the live schema on every open. It can add a
nullable column and nothing else: it cannot express a data backfill, cannot
express a change that must happen exactly once, and has no way to notice that a
database was written by a *newer* issuedb than the code reading it.

This is a prerequisite for the Tracker sync client. Every later increment —
the `sync_row` uid ledger, the `sync_outbox` triggers, signin/signout state —
is a schema change, and there was no mechanism to apply one safely.

## EARS spec

- The issuedb database layer shall record its schema version in `PRAGMA user_version`.
- When a database is opened whose `user_version` is lower than the code's target version, the issuedb database layer shall apply each pending migration in ascending order within a single transaction per migration.
- When a migration completes, the issuedb database layer shall set `PRAGMA user_version` to that migration's number.
- While a database is at the target schema version, the issuedb database layer shall apply no migrations and shall not modify the file.
- If a database is opened whose `user_version` is HIGHER than the code's target version, then the issuedb database layer shall refuse to operate and shall report that the database was written by a newer issuedb.
- If a migration raises, then the issuedb database layer shall roll back that migration's transaction and leave `user_version` at its previous value.
- The issuedb database layer shall treat a pre-existing database with `user_version` 0 that already has the current tables as being at the baseline version, and shall not re-run baseline DDL destructively.
- The issuedb database layer shall depend on the Python standard library only.

## Design decisions

**Forward only.** There is no down-migration. A rollback path that is never
exercised is a rollback path that does not work, and for a single-file SQLite
database, restoring the file is a better answer than replaying inverse DDL.

**A newer database is refused, not tolerated.** `NewerDatabaseError` is raised
rather than proceeding. This matters because 22 of 42 repos in this estate
commit `.issue.db` to git: a shared file plus an older local install is the
normal case, not the exotic one, and opening it read-write with older
assumptions is how it gets silently corrupted.

**Baseline is stamped, never re-applied.** Databases predating the ladder carry
`user_version` 0 while already having every baseline table. They are stamped to
version 1. Re-running baseline DDL over a populated file is the one move here
that could destroy data, so it is the one move `_stamp_baseline` does not make.
A genuinely empty file (no tables) is *not* stamped, or the next open would skip
the DDL that creates them.

**`BEGIN IMMEDIATE`, and the version re-read under the lock.** Two processes
opening the same `.issue.db` at once is normal for this project — a CLI
invocation while the Flask UI runs. IMMEDIATE takes the write lock up front, and
the version is re-read inside it so the loser of a race observes the winner's
work rather than repeating it.

**`SCHEMA_VERSION` is derived from the ladder,** not maintained beside it. A
hand-maintained constant next to a list is a constant that will eventually be
wrong.

## Verification

Each "shall" line above has a test in `tests/test_migrations.py`. The shipped
ladder is empty (baseline only), so tests that check the ladder *does*
something inject their own migrations — otherwise the suite would assert that
nothing happens and pass no matter how broken the machinery was.

The suite was verified to go **red**, not merely green, by mutating the
implementation:

| Mutation | Expected failure | Result |
|---|---|---|
| Drop the `NewerDatabaseError` raise | newer-database refused | 2 failed |
| `COMMIT` instead of `ROLLBACK` on migration failure | rollback leaves version behind | 1 failed |
| Do not sort the ladder | ascending order | 1 failed |
| Stamp baseline even with no tables | empty file not stamped | 1 failed |

Gates: 657 tests pass, `mypy` clean over 64 source files, `ruff` clean, no new
dependencies.

## Related

Version consistency (`tests/test_version_consistency.py`) was added in the same
change: `pyproject.toml` said 2.12.0 while `issuedb/__init__.py` said 2.11.0, so
a bug report quoting either named a release that did not contain the code being
reported. Found by `rodmena-tracker-manager-a12988` while auditing this repo.
All declarations are now 2.13.0 and a test fails if they drift.
