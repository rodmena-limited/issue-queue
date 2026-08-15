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

from issuedb.sync import _apply, _coverage
from issuedb.sync._auth_commands import DEFAULT_SERVER
from issuedb.sync._client import SyncClient, SyncError
from issuedb.sync._credentials import load
from issuedb.sync._project import ProjectIdentityError, record_project_uid
from issuedb.sync._state import load as load_state
from issuedb.sync._state import save as save_state

# Bound on the paginated pull walk, so a server that never lowers has_more
# cannot spin forever. Reaching it is reported to the user as a partial run,
# never rounded up to a complete one.
MAX_PULL_PAGES = 200


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

        # PULL IS PAGINATED. Reading one page was correct while every feed fit
        # in one, and it fails silently the moment one does not: the user is
        # told "Pulled 200 change(s)" and nothing at all about the rest, and a
        # dry run then describes a fraction of what --apply would do. The
        # server says so plainly in has_more; the client simply was not asking.
        cursor = state.cursor
        changes: list[dict[str, object]] = []
        pages = 0
        truncated = False
        while True:
            try:
                pulled = client.pull(cursor)
            except SyncError as exc:
                print(f"Error: pull failed: {exc.code} — {exc}", file=sys.stderr)
                return 1
            pages += 1
            changes.extend(pulled.changes)
            if not pulled.has_more or not pulled.changes or pulled.cursor == cursor:
                cursor = pulled.cursor
                break
            cursor = pulled.cursor
            if pages >= MAX_PULL_PAGES:
                truncated = True
                break

        # The server's advertised entity list, so "the server does not support
        # tags yet" is distinguishable from "issuedb does not apply tags yet".
        actions = _apply.plan(conn, changes, server_entities=shake.entities)
        page_note = "" if pages == 1 else f" over {pages} pages"
        print(f"Pulled {len(changes)} change(s){page_note} from cursor {state.cursor}.")
        if truncated:
            print(
                f"WARNING: stopped after {MAX_PULL_PAGES} pages with more still "
                f"available. This run covers only part of the feed; re-run to continue.",
                file=sys.stderr,
            )
        print()
        print(_apply.render_plan(actions, applying=do_apply))

        # Stated on EVERY sync, dry run included: data that cannot move is the
        # thing a user is least likely to discover on their own, because it
        # produces no output anywhere else.
        gaps = _coverage.uncovered(conn, shake.entities)
        report = _coverage.render(gaps, shake.entities)
        if report:
            print()
            print(report)

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
