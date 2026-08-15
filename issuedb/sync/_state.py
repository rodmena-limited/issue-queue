"""Mutable sync state, deliberately stored OUTSIDE the database.

The pull cursor, the replica id and the last-pushed position live in
``$XDG_CONFIG_HOME/issuedb/sync-state.json``, keyed by the absolute path of
the database they describe. Putting them inside ``.issue.db`` would be the
obvious choice and it is wrong for two independent reasons:

* **A cursor in a tracked file time-travels with the branch.** 22 of the 42
  repos here commit ``.issue.db``. Rolled BACKWARD by a checkout the cursor
  causes a harmless re-pull; rolled FORWARD it silently SKIPS server changes
  this replica never applied. The second is undetectable from the inside —
  the client believes it is up to date and is missing rows nobody will ever
  notice are absent.

* **A replica id in a tracked file is not unique.** Every clone of the repo
  would come up claiming the same replica identity, and two machines would
  interleave their cursors under one name. That alone settles it, and it is
  the reason this cannot be fixed by "just don't commit the cursor column".

Keying by path is not sufficient on its own, because paths are reused: a repo
deleted and a different one cloned to the same directory would inherit a
cursor describing somebody else's project. So the stored state records the
``project_uid`` and :func:`load` DISCARDS the cursor when it does not match.
A wasted re-pull is free if application is idempotent by uid; a misapplied
cursor is silent data loss.

Standard library only.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, NamedTuple

from issuedb.sync._credentials import CONFIG_DIR_MODE, config_dir

STATE_FILENAME = "sync-state.json"
INITIAL_CURSOR = "c:0"


class SyncState(NamedTuple):
    """Per-database sync position."""

    db_path: str
    project_uid: str
    replica_id: str
    cursor: str
    last_pushed_seq: int


def state_path(env: dict[str, str] | None = None) -> Path:
    return config_dir(env) / STATE_FILENAME


def _key(db_path: str | os.PathLike[str]) -> str:
    """Absolute, resolved path — so ./x and /full/x are one entry."""
    return str(Path(db_path).resolve())


def _load_all(env: dict[str, str] | None = None) -> dict[str, Any]:
    path = state_path(env)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        # Corrupt state is recoverable: the cursor is a cache, and losing it
        # costs a re-pull rather than data. Silently ignoring a corrupt
        # CREDENTIAL file would be wrong; here it is the safe direction.
        return {}
    return data if isinstance(data, dict) else {}


def _write_all(data: dict[str, Any], env: dict[str, str] | None = None) -> None:
    path = state_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(CONFIG_DIR_MODE)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".sync-state-")
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def new_replica_id() -> str:
    """A fresh replica identity for this machine and this checkout.

    Deliberately random rather than derived from hostname or path: a derived
    id would collide across clones on one machine, and a hostname leaks who
    and where to every other replica through the server.
    """
    return uuid.uuid4().hex


def load(
    db_path: str | os.PathLike[str],
    project_uid: str,
    env: dict[str, str] | None = None,
) -> SyncState:
    """The stored state for this database, or a fresh one.

    The cursor is DISCARDED when the stored ``project_uid`` does not match the
    one passed in — the path was reused by a different project, and applying
    its cursor would skip changes that were never seen.
    """
    entry = _load_all(env).get(_key(db_path))

    if not isinstance(entry, dict) or entry.get("project_uid") != project_uid:
        return SyncState(
            db_path=_key(db_path),
            project_uid=project_uid,
            replica_id=new_replica_id(),
            cursor=INITIAL_CURSOR,
            last_pushed_seq=0,
        )

    return SyncState(
        db_path=_key(db_path),
        project_uid=project_uid,
        replica_id=str(entry.get("replica_id") or new_replica_id()),
        cursor=str(entry.get("cursor") or INITIAL_CURSOR),
        last_pushed_seq=int(entry.get("last_pushed_seq") or 0),
    )


def save(state: SyncState, env: dict[str, str] | None = None) -> None:
    """Persist state. Call only after changes are DURABLY applied.

    Advancing the cursor past work that was not committed locally is how a
    replica silently skips rows: the server considers them delivered and the
    client never asked again.
    """
    data = _load_all(env)
    data[state.db_path] = {
        "project_uid": state.project_uid,
        "replica_id": state.replica_id,
        "cursor": state.cursor,
        "last_pushed_seq": state.last_pushed_seq,
    }
    _write_all(data, env)


def reset(
    db_path: str | os.PathLike[str], env: dict[str, str] | None = None
) -> bool:
    """Forget the cursor for a database, forcing a full re-seed.

    Returns whether anything was removed, so a caller can tell "reset" from
    "there was nothing to reset".
    """
    data = _load_all(env)
    key = _key(db_path)
    if key not in data:
        return False
    del data[key]
    _write_all(data, env)
    return True
