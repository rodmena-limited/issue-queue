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

from issuedb.database import Database, NewerDatabaseError, apply_migrations
from issuedb.sync import _apply, _coverage, _render
from issuedb.sync import _client as _client_module
from issuedb.sync._auth_commands import DEFAULT_SERVER
from issuedb.sync._client import SyncClient, SyncError
from issuedb.sync._credentials import load
from issuedb.sync._project import ProjectIdentityError, record_project_uid
from issuedb.sync._project_file import (
    PROJECT_FILE_NAME,
    ProjectFileError,
    project_file_path,
    read_project_file,
    write_project_file,
)
from issuedb.sync._push import BLOCKED, build_entries
from issuedb.sync._state import SyncState
from issuedb.sync._state import load as load_state
from issuedb.sync._state import save as save_state

# Bound on the paginated pull walk, so a server that never lowers has_more
# cannot spin forever. Reaching it is reported to the user as a partial run,
# never rounded up to a complete one.
MAX_PULL_PAGES = 200


def _outbox_high_water(conn: sqlite3.Connection) -> int:
    """The newest outbox seq, or 0 when the outbox is empty."""
    row = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM sync_outbox").fetchone()
    return int(row[0])


def _finish_push(
    conn: sqlite3.Connection,
    state: SyncState,
    cursor: str,
    env: dict[str, str] | None,
) -> None:
    """Advance the outbox mark past this sync's own echoes.

    APPLYING A SERVER CHANGE WRITES TO A LOCAL TABLE, AND THE OUTBOX TRIGGERS
    FIRE ON THAT WRITE. So every row pulled from the server immediately looks
    like a local change and is offered straight back on the next sync — a
    feedback loop that costs a round trip and bumps the server's version on
    rows nobody edited. `tracker-fbe1b4` measured it from the other side as 34
    rows "moved" when nothing should move.

    It is not a duplicate, because the uid is the server's own and the push is
    idempotent. It is churn, and churn that makes a real edit indistinguishable
    from an echo in the version history.

    By this point everything in the outbox is one of two things: a local change
    we have just pushed, or an echo of a change we have just applied. Neither
    needs sending again, so the mark moves to the current high-water line.
    """
    save_state(
        state._replace(cursor=cursor, last_pushed_seq=_outbox_high_water(conn)), env
    )


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

    # MIGRATE BEFORE CONNECTING. `sqlite3.connect` opens the file and nothing
    # else — it does not run the ladder — so on a database created before the
    # sync tables existed this used to reach the first INSERT and die with
    # "no such table: sync_project". Every other command goes through
    # `Database`, which runs `apply_migrations`; sync was the one path that did
    # not, and the failure was NOT self-healing: sync never migrates, so every
    # retry failed identically.
    #
    # Invisible to the whole suite because every test builds its database
    # through the normal path, so the tables were always already there. The
    # population that hits this — databases created by an EARLIER issuedb — was
    # excluded from all of them. Reported from the field on 2.32.0 by
    # `todo-app-maker-5c0942`.
    # `Database` creates the file and its baseline schema when sync is the
    # first thing to touch it. It is a PER-PATH SINGLETON, though, so in a
    # process that has already built one for this path the constructor is a
    # no-op — which is why the ladder is then run explicitly on our own
    # connection below rather than left to a construction side effect.
    try:
        Database(db_path)
    except NewerDatabaseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    # RUN THE LADDER BEFORE ANY SYNC TABLE IS TOUCHED. `sqlite3.connect` opens
    # the file and nothing else, so on a database created before the sync
    # tables existed this used to reach the first INSERT and die with
    # "no such table: sync_project". Every other command reaches the ladder
    # through `Database`; sync was the one path that did not, and the failure
    # did not self-heal — sync never migrated, so every retry failed the same
    # way. Shipped in 2.32.0, reported from the field by
    # `todo-app-maker-5c0942`.
    try:
        apply_migrations(conn)
    except NewerDatabaseError as exc:
        conn.close()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    try:
        # THE TRACKED FILE OUTRANKS THE SERVER. A clone arrives with
        # `.issuedb-project.json` and an empty database, so without this the
        # server would name the project and the checkout would adopt whatever
        # the API key points at — which is how two repositories sharing one key
        # merge into one backlog (reported by `tracker-fbe1b4`). The database's
        # own write-once guard cannot help there: a fresh database has nothing
        # to defend. The committed file is what it defends with.
        try:
            committed = read_project_file(db_path)
        except ProjectFileError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if committed is not None and committed != shake.project_uid:
            print(
                f"Error: this checkout is committed to project {committed} "
                f"({project_file_path(db_path).name}), but the server reported "
                f"{shake.project_uid}. Refusing to sync: the API key names a different "
                f"project than this repository belongs to.",
                file=sys.stderr,
            )
            return 1

        try:
            recorded = record_project_uid(conn, shake.project_uid, server)
        except ProjectIdentityError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if recorded:
            conn.commit()
            print(f"Recorded project {shake.project_uid} for this database.")

        # Establish the lineage for every future clone. Written after the
        # database agrees, so a refusal above never leaves a file behind.
        if committed is None:
            try:
                written = write_project_file(db_path, shake.project_uid, server)
            except (ProjectFileError, OSError) as exc:
                print(f"Warning: could not write {PROJECT_FILE_NAME}: {exc}", file=sys.stderr)
            else:
                print(
                    f"Wrote {written.name} — COMMIT THIS FILE so every clone of this "
                    f"repository syncs to the same project."
                )

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
        print(_render.render_plan(actions, applying=do_apply))

        # Stated on EVERY sync, dry run included: data that cannot move is the
        # thing a user is least likely to discover on their own, because it
        # produces no output anywhere else.
        gaps = _coverage.uncovered(conn, shake.entities)
        report = _coverage.render(gaps, shake.entities)
        if report:
            print()
            print(report)

        # THE SEND HALF. Built before --apply is honoured so a dry run shows
        # both directions: what would come in AND what would go out. Sync that
        # only ever reported the inbound half is how "no issue can ever leave a
        # laptop" survived unnoticed (#14).
        entries, outbox_seq, skipped = build_entries(
            conn, shake.project_uid, state.last_pushed_seq,
            server_entities=shake.entities,
        )
        # COMMIT THE MINTED UIDS BEFORE ANYTHING ELSE TOUCHES THIS CONNECTION.
        # `build_entries` writes to the ledger, which opens an implicit
        # transaction. `apply` then issues its own BEGIN IMMEDIATE and sqlite
        # raises "cannot start a transaction within a transaction" — the whole
        # apply is rolled back, taking the ledger writes with it. So:
        #
        #   * NOTHING WAS EVER APPLIED on any sync that also had something to
        #     push, while the run still reported "Pushed N";
        #   * the ledger stayed empty, so the next push MINTED FRESH UIDS for
        #     the same rows and the server grew a duplicate set every time.
        #
        # `tracker-fbe1b4` measured both: two pushes of one local row produced
        # two server rows and left `sync_row` at 0. Recording BEFORE the send
        # is also the safe order — a crash between send and record would
        # otherwise duplicate on the next run.
        conn.commit()
        print()
        if entries:
            counts: dict[str, int] = {}
            for entry in entries:
                counts[entry["entity"]] = counts.get(entry["entity"], 0) + 1
            shape = " · ".join(f"{n} {name}" for name, n in sorted(counts.items()))
            verb = "Pushing" if do_apply else "WOULD PUSH"
            print(f"{verb} {len(entries)} local change(s): {shape}")
        else:
            print("Nothing local to push.")
        # SAY WHOSE LIMITATION EACH SKIP IS. `tracker-fbe1b4` pointed out that
        # the coverage report four lines below states the server "advertises
        # ['issue', ..., 'issue_tag']", so a reader seeing "SKIP issue_tags"
        # nearby could reasonably conclude the server refuses them. It does not
        # — WE do, and for a reason in our schema. Attributing our own
        # limitation to the counterparty is the kind of thing that gets
        # reported to the wrong team.
        for reason, (count, kind) in sorted(skipped.items()):
            note = BLOCKED.get(reason)
            if note:
                print(
                    f"  HELD BACK BY ISSUEDB: {count} {reason} — {note}.\n"
                    f"    The server DOES accept this entity; this is our limitation, "
                    f"not Tracker's."
                )
            elif kind == "unbuildable":
                print(
                    f"  SKIP {count} {reason} — the local row is gone, or its issue has "
                    f"not been pushed yet; retried on the next sync"
                )
            elif kind == "held":
                # The server advertises it and WE cannot build it. Saying "no
                # entity on the wire" here would blame the server for our gap —
                # in the same output that lists the entity as advertised.
                print(
                    f"  HELD BACK BY ISSUEDB: {count} {reason} — the server advertises "
                    f"this entity; issuedb does not build it yet."
                )
            else:
                print(f"  SKIP {count} {reason} — no sync entity on the wire")

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

        # PUSH AFTER APPLY. The inbound half runs first so a local row that the
        # server already knows is reconciled before we offer it back, and the
        # mark advances only on entries the server ACCEPTED — a per-uid
        # rejection inside a 200 is not success, and advancing past it would
        # lose the change with nothing erroring.
        if entries:
            try:
                results = client.push(entries, replica_id=state.replica_id)
            except SyncError as exc:
                print(f"Error: push failed: {exc.code} — {exc}", file=sys.stderr)
                print("Nothing local was marked as sent; re-running retries it.", file=sys.stderr)
                return 1
            # Deliberately the REAL protocol helper, reached through the module
            # rather than through the module-level `SyncClient` name a test may
            # have substituted. What counts as "rejected" is part of the wire
            # contract; a stand-in client must not get to redefine it, or the
            # test proves only that the double agrees with itself.
            # `gone` is NOT a failure. An upsert against a tombstoned row comes
            # back gone/restorable, and a client that treats it as an error —
            # or worse, retries it — resurrects deleted rows. Tracker shipped
            # exactly that branch and found it by pushing at their own
            # production server; they warned us before comments started
            # travelling. It means "stop pushing this", so the mark advances.
            gone = [r for r in results if r.get("outcome") == "gone"]
            if gone:
                print(
                    f"  {len(gone)} row(s) are deleted on the server; not resurrecting them."
                )
            rejected = _client_module.SyncClient.rejected(results)
            accepted = len(results) - len(rejected)
            print(f"Pushed {accepted} change(s).")
            for item in rejected:
                print(
                    f"  REJECTED {item.get('uid')}: {item.get('reason')}", file=sys.stderr
                )
            if rejected:
                print(
                    "The outbox mark has NOT advanced past a rejected entry, so those "
                    "changes are retried on the next sync.",
                    file=sys.stderr,
                )
                return 1
            _finish_push(conn, state, result.cursor, env)

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
