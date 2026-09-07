"""The project identity as a TRACKED file beside the database.

``_project.py`` says the project id being committed is a feature: "it is the
same for every clone forever ... a fresh clone of a tracked repo knows which
project it belongs to with zero setup." That is the right goal and the wrong
mechanism, because it assumed ``.issue.db`` itself was committed. Nothing ever
told users to commit it, and issuedb's own ``.gitignore`` forbids it (issuedb
#28), so the promise was never kept for anybody.

Committing the database is also the wrong answer on its own terms. It is a
binary SQLite file: two developers each creating an issue produce a conflict
git cannot merge and a human cannot resolve by hand. And it is redundant —
sharing issues is what sync is FOR, so a committed database and a synced one
are two mechanisms racing over the same rows.

So the database stays ignored and the identity moves to a tiny tracked file:

    .issuedb-project.json   {"project_uid": ..., "server_url": ...}

Text, one line, merge-friendly, obviously reviewable in a diff, and it carries
nothing secret — the same reasoning ``_project.py`` already applies to
``project_uid`` itself.

WHAT THIS BUYS, beyond keeping a promise. `tracker-fbe1b4` reported that two
repositories sharing one API key silently merge into one backlog, because the
server answers "which project" from the key and a fresh database has no
identity to defend. This file gives a CLONE the identity to defend: it arrives
with the checkout, so the second developer's fresh database already knows which
project it belongs to and refuses a server that names a different one.

It does not fix two genuinely different repos sharing one key — neither has a
file, so both adopt what the key names. That is Tracker's to fix, and this file
is the value their protocol change needs on the wire.

Standard library only.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

PROJECT_FILE_NAME = ".issuedb-project.json"


class ProjectFileError(Exception):
    """The tracked project file exists and cannot be trusted."""


def project_file_path(db_path: str) -> pathlib.Path:
    """Where the tracked identity lives for a given database.

    Beside the database, not inside a dot-directory: one file is easier to
    notice in a diff and needs no explanation in a README.
    """
    return pathlib.Path(db_path).resolve().parent / PROJECT_FILE_NAME


def read_project_file(db_path: str) -> str | None:
    """The project uid this checkout is committed to, or None if untracked.

    A malformed file RAISES rather than returning None. Treating unreadable as
    absent would silently adopt whatever the server names, which is the exact
    failure this file exists to prevent.
    """
    path = project_file_path(db_path)
    if not path.exists():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectFileError(f"{path} is unreadable: {exc}") from None
    if not isinstance(data, dict):
        raise ProjectFileError(f"{path} does not contain a JSON object")
    uid = data.get("project_uid")
    if uid is None:
        raise ProjectFileError(f"{path} has no project_uid")
    if not isinstance(uid, str) or not uid:
        raise ProjectFileError(f"{path} has a non-string or empty project_uid")
    return uid


def write_project_file(db_path: str, project_uid: str, server_url: str) -> pathlib.Path:
    """Record the identity for every future clone. Never overwrites a different uid."""
    if not project_uid:
        raise ProjectFileError("refusing to write an empty project_uid")
    path = project_file_path(db_path)
    existing = read_project_file(db_path)
    if existing is not None and existing != project_uid:
        raise ProjectFileError(
            f"{path} names project {existing}, not {project_uid}. Refusing to overwrite: "
            f"this checkout belongs to a different project."
        )
    path.write_text(
        json.dumps(
            {"project_uid": project_uid, "server_url": server_url},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
