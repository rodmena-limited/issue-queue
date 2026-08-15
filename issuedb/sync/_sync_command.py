"""``issuedb-cli sync`` — pull from Tracker and, only if asked, apply.

DRY RUN IS THE DEFAULT. A user's first encounter with sync must not be a
mutation: everything else in this package writes into a server with backups,
and this writes into their local issue database, where a defect destroys work
that exists nowhere else.

The plan shown by a dry run and the plan executed by ``--apply`` come from the
same :func:`issuedb.sync._apply.plan` call. A dry run computed by different
code would describe something the apply does not do, which is worse than no
dry run because the user has been shown it and believes it.
"""

from __future__ import annotations

import sqlite3
import sys

from issuedb.sync import _apply
from issuedb.sync._auth_commands import DEFAULT_SERVER
from issuedb.sync._client import SyncClient, SyncError
from issuedb.sync._credentials import load
from issuedb.sync._project import ProjectIdentityError, record_project_uid
from issuedb.sync._state import load as load_state
from issuedb.sync._state import save as save_state


def sync(
    db_path: str,
    server: str = DEFAULT_SERVER,
    do_apply: bool = False,
    env: dict[str, str] | None = None,
) -> int:
    """Pull changes and report them; apply only when do_apply is True."""
    credential = load(server, env)
    if credential is None:
        print(f"Not signed in to {server}.", file=sys.stderr)
        print(f"Run: issuedb-cli signin --server {server}", file=sys.stderr)
        return 1

    client = SyncClient(server, token=credential.token)

    # Preflight BEFORE anything local is touched. A protocol mismatch must be
    # discovered while the database is still untouched.
    try:
        shake = client.handshake()
    except SyncError as exc:
        print(f"Error: handshake failed: {exc}", file=sys.stderr)
        return 1

    if not shake.project_uid:
        print(
            "Error: the server returned no project_uid. An unscoped API key names no "
            "project, and project_uid is required to derive uids.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(db_path)
    try:
        try:
            recorded = record_project_uid(conn, shake.project_uid, server)
        except ProjectIdentityError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if recorded:
            conn.commit()
            print(f"Recorded project {shake.project_uid} for this database.")

        state = load_state(db_path, shake.project_uid, env)
        try:
            pulled = client.pull(state.cursor)
        except SyncError as exc:
            print(f"Error: pull failed: {exc.code} — {exc}", file=sys.stderr)
            return 1

        actions = _apply.plan(conn, pulled.changes)
        print(f"Pulled {len(pulled.changes)} change(s) from cursor {state.cursor}.")
        print()
        print(_apply.render_plan(actions, applying=do_apply))

        if not do_apply:
            return 0

        print()
        result = _apply.apply(conn, actions, state.cursor)
        conn.commit()

        # The cursor is saved AFTER the commit, and only to what was durably
        # applied. Saving it before would let a crash between the two leave a
        # cursor claiming work that never landed.
        save_state(state._replace(cursor=result.cursor), env)

        print(f"Applied {result.applied} change(s). Cursor now {result.cursor}.")
        if result.stopped_at:
            print(f"STOPPED: {result.stopped_at}", file=sys.stderr)
            print(
                "Changes already applied are kept. The cursor has not advanced past "
                "the failure, so re-running will retry from there.",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        conn.close()
