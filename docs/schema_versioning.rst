Schema versioning
=================

Every ``.issue.db`` records the schema version it was written at, in SQLite's
``PRAGMA user_version``. issuedb applies pending schema changes on open, in
ascending order, and refuses to open a database written by a newer issuedb than
the installed one.

Why it matters
--------------

A ``.issue.db`` is a single file, and in practice that file gets shared: it is
committed to git in many projects, copied between machines, and opened by a CLI
invocation while the web UI is running. Without a recorded version there is no
way for issuedb to tell a database it fully understands from one written by a
later release whose schema it does not.

Checking the version
--------------------

.. code-block:: python

   from issuedb.database import Database

   db = Database(".issue.db")
   db.schema_version            # what this file records
   db.supported_schema_version  # the highest this build understands

From the shell:

.. code-block:: bash

   sqlite3 .issue.db 'PRAGMA user_version'

Behaviour on open
-----------------

**Older database.** Pending migrations are applied in ascending order. Each runs
in its own transaction together with the version bump, so a crash leaves the
database at a version that is true — never half-applied.

**Database predating versioning.** Files created before schema versioning
existed report version ``0`` while already having every table. They are stamped
to the baseline version. Baseline DDL is *not* re-run, so existing issues,
comments and history are untouched.

**Current database.** Nothing is applied and the file is not modified.

**Newer database.** issuedb raises ``NewerDatabaseError`` and refuses to
continue::

   This database is at schema version 4, but this issuedb supports up to 2.
   It was written by a newer issuedb. Upgrade issuedb (pip install -U issuedb)
   rather than continuing: writing to it with older assumptions can lose data.

This is deliberate. If your team shares a ``.issue.db`` through git and one
machine has an older install, that machine must upgrade rather than write to a
schema it cannot interpret.

**Failed migration.** The transaction is rolled back and the recorded version
stays where it was, so the version never describes a change that did not land.
issuedb raises ``MigrationError`` naming the migration that failed.

Forward only
------------

There are no down-migrations. A rollback path that is never exercised is a
rollback path that does not work, and for a single-file SQLite database,
restoring the file from git or a backup is both simpler and more reliable than
replaying inverse DDL.

Concurrency
-----------

Migrations take SQLite's write lock up front (``BEGIN IMMEDIATE``) and re-read
the version inside it. When two processes open the same database at once, the
loser of the race observes the winner's work instead of repeating it.
