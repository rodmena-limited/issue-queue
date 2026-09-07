"""The project identity must survive a clone, without committing the database.

issuedb #28: `_project.py` promised "a fresh clone of a tracked repo knows which
project it belongs to with zero setup", and that promise assumed `.issue.db` was
committed. Nothing told users to commit it and this repo's own `.gitignore`
forbids it, so the promise was never kept.

The database stays ignored — it is binary and unmergeable, and sharing issues is
what sync is for. The identity moves to a tracked `.issuedb-project.json`.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from issuedb.database import Database
from issuedb.sync import _sync_command
from issuedb.sync._credentials import Credential
from issuedb.sync._project import get_project_uid
from issuedb.sync._project_file import (
    PROJECT_FILE_NAME,
    ProjectFileError,
    project_file_path,
    read_project_file,
    write_project_file,
)
from tests.test_sync_pagination import PROJECT, FakePagingClient


@pytest.fixture
def wired(monkeypatch, tmp_path):
    monkeypatch.setattr(
        _sync_command,
        "load",
        lambda server, env=None: Credential(
            server_url=server, key_id="01testkeyid00000000000000", secret="s3cr3t"
        ),
    )
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / ".issue.db"
    Database(str(path))
    return str(path)


def _sync(db, wired, monkeypatch, project=PROJECT):
    client = FakePagingClient(total=2, size=200)
    monkeypatch.setattr(client, "project_uid", project, raising=False)
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)
    return _sync_command.sync(db, "https://example.invalid", do_apply=False, env=wired)


def test_first_sync_writes_the_tracked_file(db, wired, monkeypatch, capsys):
    assert not project_file_path(db).exists()
    assert _sync(db, wired, monkeypatch) == 0

    path = project_file_path(db)
    assert path.exists(), "first sync did not record the project for future clones"
    assert json.loads(path.read_text())["project_uid"] == PROJECT
    assert "COMMIT THIS FILE" in capsys.readouterr().out


def test_a_clone_refuses_a_server_naming_a_different_project(tmp_path, wired, monkeypatch, capsys):
    """The case the database's write-once guard cannot defend.

    A clone has the committed file and an EMPTY database. Without the file the
    server names the project and the checkout adopts it, which is how two repos
    sharing one API key merge into one backlog.
    """
    clone = tmp_path / "clone"
    clone.mkdir()
    db = str(clone / ".issue.db")
    Database(db)
    write_project_file(db, "01PROJECT-THIS-REPO-BELONGS-TO", "https://example.invalid")

    # The database is fresh: it has nothing of its own to defend.
    conn = sqlite3.connect(db)
    try:
        assert get_project_uid(conn) is None
    finally:
        conn.close()

    rc = _sync(db, wired, monkeypatch, project="01A-DIFFERENT-PROJECT-ENTIRELY")

    assert rc == 1, "sync adopted a project this checkout does not belong to"
    assert "committed to project" in capsys.readouterr().err
    conn = sqlite3.connect(db)
    try:
        assert get_project_uid(conn) is None, "a refused sync still bound the database"
    finally:
        conn.close()


def test_a_clone_syncs_normally_when_the_server_agrees(tmp_path, wired, monkeypatch):
    """Control: the refusal above must not be a check that always refuses."""
    clone = tmp_path / "clone2"
    clone.mkdir()
    db = str(clone / ".issue.db")
    Database(db)
    write_project_file(db, PROJECT, "https://example.invalid")

    assert _sync(db, wired, monkeypatch) == 0
    conn = sqlite3.connect(db)
    try:
        assert get_project_uid(conn) == PROJECT
    finally:
        conn.close()


def test_an_unreadable_file_stops_the_sync(db, wired, monkeypatch, capsys):
    """Unreadable must not degrade to absent — that would adopt whatever the key names."""
    project_file_path(db).write_text("{ not json", encoding="utf-8")
    assert _sync(db, wired, monkeypatch) == 1
    assert "unreadable" in capsys.readouterr().err


def test_write_refuses_to_overwrite_a_different_project(db):
    write_project_file(db, "01FIRST", "https://example.invalid")
    with pytest.raises(ProjectFileError, match="Refusing to overwrite"):
        write_project_file(db, "01SECOND", "https://example.invalid")
    assert read_project_file(db) == "01FIRST"


def test_the_file_sits_beside_the_database(db):
    assert project_file_path(db).name == PROJECT_FILE_NAME
    assert project_file_path(db).parent == project_file_path(db).parent
