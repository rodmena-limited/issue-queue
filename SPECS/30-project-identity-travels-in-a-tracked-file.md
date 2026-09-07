# 30 — Project identity travels in a tracked file, not in the database

Ticket: issuedb #28 — **RESOLVED in v2.33.0.**

## The contradiction

`_project.py` promised: *"it is the same for every clone forever … So being
committed is a FEATURE — a fresh clone of a tracked repo knows which project it
belongs to with zero setup."*

That assumed `.issue.db` was itself committed. Measured:

```
README + docs, "commit .issue.db"     ZERO hits
this repo's .gitignore, line 65       .issue.db   (under "runtime artifacts")
```

**The promise was never kept for anybody**, and the repository actively
contradicted the design. Found because `tracker-fbe1b4` asked whether the
database carries a lineage identity they could put on the wire, rather than
proposing a design.

## The decision: keep the goal, change the mechanism

`.issue.db` **stays ignored.** Committing it was wrong on its own terms — it is
a binary SQLite file, so two developers each creating an issue produce a
conflict git cannot merge and a human cannot resolve; and sharing issues is what
sync is *for*, so a committed database and a synced one race over the same rows.

The identity moves to `.issuedb-project.json`, beside the database, committed:

```json
{ "project_uid": "01M0…", "server_url": "https://tracker.rodmena.co.uk" }
```

Text, merge-friendly, reviewable in a diff, carrying nothing secret — the same
reasoning `_project.py` already applied to `project_uid` itself.

## It closes a hole the database could not defend

`tracker-fbe1b4`'s case: two checkouts, one API key. The database's write-once
guard fires only when a *different* uid is already recorded, so a **fresh**
database has nothing to defend and adopts whatever the key names.

The tracked file is what a clone defends with:

```
first sync        writes .issuedb-project.json, prints "COMMIT THIS FILE"
clone + fresh db  server names a different project -> REFUSES, database left unbound
clone + agreement -> syncs normally            (control: the refusal is not unconditional)
unreadable file   -> STOPS. Unreadable must not degrade to absent, which would
                     adopt whatever the key names — the exact failure it prevents.
```

**Not fixed by this:** two genuinely *different* repositories sharing one key.
Neither has a file, so both adopt what the key names. That is Tracker's #32, and
this file is the value their protocol change needs on the wire.

## Verification

`tests/test_sync_project_file.py`, six tests. Proven red by removing the
mismatch check: `test_a_clone_refuses_a_server_naming_a_different_project`
fails. The refusal has a control — a clone whose server agrees must still sync —
so it is not a check that always refuses.

Also corrected: the `_project.py` docstring that made the wrong promise,
`docs/sync.rst` (a new "What to commit" section), `.gitignore` (a note saying
the project file is deliberately not ignored), and `PROMPT.txt`.
