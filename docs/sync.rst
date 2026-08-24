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

   # Remove the stored key
   issuedb-cli signout

The key is stored in the XDG config directory with ``0600`` permissions.

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

State and identity
------------------

The cursor and replica identity live **outside** the database, keyed to the
project, so a fresh clone of a tracked repo knows which project it belongs to
with zero setup. The project id itself is recorded inside the database and is
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

Known limitation
----------------

The apply path applies issues, relations and dependencies, but not tags — a
sync reports tag changes as ``SKIP — issuedb does not apply entity 'issue_tag'
yet``. The push direction (sending local changes to the server) is not yet
built.
