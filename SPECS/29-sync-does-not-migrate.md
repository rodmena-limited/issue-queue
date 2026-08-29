# 29 — Sync crashed on every database created before the sync tables existed

Ticket: issuedb #27 — **FIXED in v2.32.1.** Shipped broken in 2.32.0.

## Reported from the field, against a release published an hour earlier

`todo-app-maker-5c0942`: on a `.issue.db` created by 2.12.0, the first
`issuedb-cli sync` died with `sqlite3.OperationalError: no such table:
sync_project`.

Reproduced exactly — install 2.12.0, create a database, run 2.32.0's sync:

```
2.12.0 database      user_version 0 · 16 tables · sync tables: none
2.32.0 sync          sqlite3.OperationalError: no such table: sync_project
```

**Worse than reported.** Their account said a retry succeeded; here the second
run failed identically, `user_version` stayed 0, and no sync table was ever
created. **It does not self-heal** — sync never migrates, so every retry fails
the same way. Their retry most likely succeeded because some *other* issuedb
command ran in between and migrated the file.

## Root cause

`_sync_command` opened the database with a bare `sqlite3.connect()`. That opens
the file and runs nothing. Every other command goes through `Database`, which
calls `apply_migrations`; **sync was the one path that did not**, and the sync
tables are created by ladder steps 2–4.

```
fresh 2.32.0 database   user_version 4 · sync_outbox, sync_project, sync_row
2.12.0 database         user_version 0 · none of them
```

### Why 906 tests missed it

All of them build their database through the normal path, so the sync tables
were always already present. **The population that hits this — a database
created by an earlier issuedb — was excluded from every test in the suite.**

The same gap sat in the release check: it verified the *package* (version
records consistent, subcommands present) and never ran sync against a database
an existing user would have. Presence of a subcommand was taken as evidence the
feature worked — the substitution this repo's own notes warn about.

## EARS SPEC

- When sync opens a database whose schema predates the sync tables, the sync
  command shall apply the migration ladder before touching any sync table.
- If the database was written by a newer issuedb, then the sync command shall
  report that and exit non-zero rather than migrate.
- While migrating a pre-existing database, the sync command shall preserve
  every existing row.

## The fix, and why it is not just `Database(db_path)`

The first attempt constructed `Database(db_path)` and relied on its
construction side effect. It worked in the CLI and **could not be tested**:
`DatabaseMeta` is a **per-path singleton**, so a second construction in the same
process returns the cached instance and `__init__` never re-runs. The fix
therefore worked only because each CLI invocation is a fresh process — true
today, and not a property to depend on.

`apply_migrations(conn)` is now called explicitly on sync's own connection,
with `NewerDatabaseError` handled. `Database(db_path)` is kept for the case
where sync is the first thing to create the file.

## Verification

`tests/test_sync_migrates_legacy_db.py`, three tests, proven red by removing the
explicit ladder call (2 of 3 fail).

The fixture builds a genuine pre-ladder database and **its own control checks
that it is one** — the first version dropped the sync tables but left the outbox
triggers behind, a state no released issuedb ever produced, which failed
differently. Verified against a database built by a real 2.12.0: 0 triggers,
0 sync tables.

End-to-end on a genuinely 2.12.0-created file: `user_version` 0 → 4, sync tables
created, existing tickets intact.
