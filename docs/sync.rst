Sync with Tracker
=================

IssueDB can synchronise issues, tags, dependencies and relations with a Tracker
server. Sync is **dry run by default** — nothing is written to your local
database until you pass ``--apply``.

Signing in
----------

A Tracker API key is stored once per machine. No database is created by these
commands; they are statements about the machine, not about a project.

.. code-block:: bash

   # Store a key (omit --token to be prompted; a token on the command line
   # lands in your shell history)
   issuedb-cli signin --token trk_...

   # See which key is stored (the secret is never printed)
   issuedb-cli whoami

   # Remove the stored key. Prints the store path BEFORE removing anything —
   # on a shared machine this is not private cleanup, and the path is the only
   # way to see whose credential you are about to delete.
   issuedb-cli signout

The key is stored in the XDG config directory with ``0600`` permissions.

To isolate a test from your real credential, set **XDG_CONFIG_HOME** — that is
the only override this tool honours. Then check the path each command prints:
an env var it does not read fails silently, and the first sign that your
isolation did not work is a path you did not expect.

Running a sync
--------------

.. code-block:: bash

   # Dry run — pull and show what WOULD happen, write nothing
   issuedb-cli sync

   # Apply the changes
   issuedb-cli sync --apply

What a sync does, in order:

1. **Handshake** — confirms the server's protocol range and project identity
   *before* anything local is touched. A protocol mismatch stops the sync with
   the database untouched.
2. **Pull** — reads the whole feed, following pagination until the server
   reports no more. The printed count is the full feed, not the first page.
3. **Plan** — renders every change as ``CREATE`` / ``UPDATE`` / ``DELETE`` /
   ``SKIP`` with a reason. A dry run and ``--apply`` compute the same plan, so
   what you are shown is what would be done.
4. **Apply** (only with ``--apply``) — applies each change in its own
   transaction, then advances the cursor only to what was durably committed.
   A failure mid-apply keeps the cursor before the failure, so re-running
   retries from there.
5. **Coverage** — states which local data has no sync entity to travel on
   (e.g. comments, audit logs), so "everything synced" is never silently
   assumed.

What to commit
--------------

.. code-block:: text

   .issuedb-project.json    COMMIT THIS   the project this repository belongs to
   .issue.db                DO NOT COMMIT  your local replica

``.issue.db`` is a binary SQLite file. Two developers each creating an issue
produce a conflict git cannot merge, and sharing issues is what sync is *for* —
a committed database and a synced one race over the same rows. Keep it in
``.gitignore``.

``.issuedb-project.json`` is written on your first successful sync and holds
only the project id and server URL — nothing secret. **Commit it.** It is what
makes a fresh clone sync to the same project with no setup, and it is what makes
a clone REFUSE a server that names a different project: an API key pointing at
somebody else's project would otherwise be adopted silently by a fresh
database, merging two backlogs.

State and identity
------------------

The cursor and replica identity live **outside** the database, keyed to the
project. The project id itself is recorded inside the database and is
write-once: if the server ever reports a different project for a database that
already holds one, sync refuses rather than merge two projects' rows.

Derived identity
----------------

Rows that have no identity of their own — a tag on an issue, a dependency
between two issues — get a **derived** uid, so two replicas that independently
record the same fact converge with no conflict machinery. Issues get a
**minted** uid (a random one), because two replicas writing "the same" issue
have genuinely written two.

.. code-block:: python

   from issuedb.sync import derived_uid, dependency_uid, relation_uid, mint_uid

   derived_uid("issue_tag", project_uid, issue_uid, tag_name)
   dependency_uid(project_uid, blocker_uid, blocked_uid)
   relation_uid(project_uid, source_uid, rel_type, target_uid, symmetric_types)

``symmetric_types`` is read from the handshake rather than hardcoded: if a
relation type means the same thing both ways round, its endpoints are sorted so
both directions derive one uid. Dependencies are never sorted — they are
directional, and reversing them must give a different uid or a cycle could not
be represented.

.. note::

   The ``dependency_uid`` field order is **specified** by
   ``contracts/sync/PROTOCOL.md`` line 150 --
   ``"idep", project_uid, blocker_uid, blocked_uid`` -- committed 2026-08-15,
   a week before issuedb derived its first dependency uid.

   It is independently confirmed: all 16 server-derived dependencies in
   Tracker's live feed match that order and none match the reverse. The frozen
   vector at ``tests/data/vectors_issuedb/14-dependency-uid-derivation.json``
   pins the uid **the server produced**, not issuedb's own output, so a
   divergence from the specified order fails a test rather than silently
   forking a row.

Pushing local changes
---------------------

``sync`` is bidirectional. A dry run reports **both** directions — what would
come in and what would go out — and ``--apply`` does both, pulling first so a
local row the server already knows is reconciled before it is offered back.

.. code-block:: text

   $ issuedb-cli sync
   Pulled 12 change(s) from cursor c:0.
   ...
   WOULD PUSH 3 local change(s): 1 issue_dependency · 2 issue

   $ issuedb-cli sync --apply
   Applied 12 change(s). Cursor now c:14.
   Pushed 3 change(s).

What travels, and what does not:

``issues``
   uid **minted** on first push and remembered in the ledger, so editing an
   issue never changes its identity.

``issue_dependencies``, ``issue_relations``
   uid **derived** from the frozen canonical form, so two replicas that
   independently record the same edge converge with no conflict machinery.

``comments``
   uid **minted** per local comment and remembered, like an issue. A comment is
   not its text: two people writing "+1" on one issue have written two
   comments, so deriving from ``(project, issue, text)`` would collapse them
   into one row and lose one with nothing erroring.

``issue_tags``
   **refused by issuedb, on purpose — not by the server.** The outbox trigger
   records ``issue_id`` as the local id and the ledger is keyed ``(entity,
   local_id)``, so two tags on one issue would collide on one key and one tag
   would be sent under another's identity. Tracker *does* accept ``issue_tag``;
   this is our limitation. Sync says so in those words, because the coverage
   report a few lines later lists ``issue_tag`` among the entities the server
   advertises, and the two together could otherwise read as the server refusing
   it. Fixing it needs a schema change (issuedb #13).

everything else
   comments, templates, time entries and the rest have no entity on the wire.
   The coverage report names them on every sync rather than dropping them
   silently.

A per-uid rejection inside a ``200`` is **not** success: the outbox mark does
not advance past a rejected entry, so the change is offered again next sync
rather than lost.

Known limitation
----------------

The apply path applies issues, relations and dependencies, but not tags — a
sync reports tag changes as ``SKIP — issuedb does not apply entity 'issue_tag'
yet`` — see "Pushing local changes" above for why tags are held back.
Comments travel in **both** directions as of 2.36.0.
