"""Sync must migrate a database created before the sync tables existed.

Shipped broken in 2.32.0 and reported from the field by
`todo-app-maker-5c0942`: on a `.issue.db` created by 2.12.0, the first
`issuedb-cli sync` died with `sqlite3.OperationalError: no such table:
sync_project`, and **it never healed** — sync does not migrate, so every retry
failed identically.

`_sync_command` called `sqlite3.connect()` directly. That opens the file and
runs nothing; every other command goes through `Database`, which applies the
ladder. Sync was the one path that did not.

WHY 903 TESTS MISSED IT: they all build their database through the normal path,
so the sync tables were always already present. The population that hits this —
a database created by an EARLIER issuedb — was excluded from every one of them.
This test constructs that population explicitly.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.sync import _sync_command
from issuedb.sync._credentials import Credential
from tests.test_sync_pagination import FakePagingClient

PRE_LADDER_TABLES = ("sync_row", "sync_outbox", "sync_project")


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Point sync at a fake credential and an isolated state store."""
    monkeypatch.setattr(
        _sync_command,
        "load",
        lambda server, env=None: Credential(
            server_url=server, key_id="01testkeyid00000000000000", secret="s3cr3t"
        ),
    )
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}


@pytest.fixture
def legacy_db(tmp_path):
    """A database shaped like one from before the ladder: no sync tables, v0."""
    path = tmp_path / "legacy.db"
    Database(str(path))  # build the current schema...
    conn = sqlite3.connect(path)
    try:
        # A real pre-ladder database has NO triggers either — the outbox
        # triggers arrived with the sync tables. Dropping the tables alone
        # leaves triggers that reference them, which is a state no released
        # issuedb ever produced, and it fails differently. Verified against a
        # database built by a real 2.12.0: 0 triggers, 0 sync tables.
        for trigger in [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        ]:
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        for table in PRE_LADDER_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()
    return str(path)


def _tables(path: str) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()


def _user_version(path: str) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def test_the_fixture_really_is_a_pre_ladder_database(legacy_db):
    """Control: if the fixture already had the tables, the test below is vacuous."""
    assert _user_version(legacy_db) == 0
    assert not (_tables(legacy_db) & set(PRE_LADDER_TABLES)), (
        "the fixture still has sync tables; it is not a pre-ladder database"
    )
    conn = sqlite3.connect(legacy_db)
    try:
        triggers = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        ]
    finally:
        conn.close()
    assert triggers == [], f"a pre-ladder database has no triggers; found {triggers}"


def test_sync_migrates_a_pre_ladder_database_before_touching_it(legacy_db, wired, monkeypatch):
    """The bug: sync reached its first INSERT against tables that did not exist."""
    client = FakePagingClient(total=3, size=200)
    monkeypatch.setattr(_sync_command, "SyncClient", lambda *a, **k: client)

    rc = _sync_command.sync(legacy_db, "https://example.invalid", do_apply=False, env=wired)

    assert rc == 0, "sync failed on a database created before the sync tables existed"
    assert set(PRE_LADDER_TABLES) <= _tables(legacy_db)
    assert _user_version(legacy_db) == 4


def test_existing_rows_survive_the_migration(legacy_db, wired, monkeypatch):
    """A migration that loses the user's issues would also make the test above pass."""
    conn = sqlite3.connect(legacy_db)
    try:
        conn.execute("INSERT INTO issues (title) VALUES ('legacy ticket')")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        _sync_command, "SyncClient", lambda *a, **k: FakePagingClient(total=3, size=200)
    )
    _sync_command.sync(legacy_db, "https://example.invalid", do_apply=False, env=wired)

    conn = sqlite3.connect(legacy_db)
    try:
        titles = [r[0] for r in conn.execute("SELECT title FROM issues")]
    finally:
        conn.close()
    assert "legacy ticket" in titles
