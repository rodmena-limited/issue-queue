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

Known limitation
----------------

The apply path applies issues, relations and dependencies, but not tags — a
sync reports tag changes as ``SKIP — issuedb does not apply entity 'issue_tag'
yet``. The push direction (sending local changes to the server) is not yet
built.
