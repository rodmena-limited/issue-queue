"""Shared pytest fixtures for the issuedb test suite."""

import pytest

from issuedb.database import Database


@pytest.fixture(autouse=True)
def _isolate_cwd_and_db_registry(tmp_path, monkeypatch):
    """Run every test in its own temporary directory.

    issuedb uses a per-directory database model: ``Database()`` with no path
    opens ``.issue.db`` in the current working directory. Without this guard a
    test that touches the default path would open, migrate, or delete a real
    project database in whatever directory pytest was launched from.

    Also gives each test a fresh ``Database._instances`` registry so singleton
    state (and its thread-local connections) cannot leak between tests, and
    closes any connections the test opened before its temp directory is
    discarded.
    """
    monkeypatch.chdir(tmp_path)
    saved_instances = Database._instances
    Database._instances = {}
    try:
        yield
    finally:
        for instance in Database._instances.values():
            instance.close_connection()
        Database._instances = saved_instances
