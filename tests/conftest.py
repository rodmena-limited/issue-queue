"""Shared pytest fixtures for the issuedb test suite."""

import contextlib
import pathlib
import tempfile

import pytest

from issuedb.database import Database

_TMP = pathlib.Path(tempfile.gettempdir())
_SIDECARS = ("*.db-wal", "*.db-shm", "*.db-journal")


def _sqlite_sidecars() -> set[pathlib.Path]:
    found: set[pathlib.Path] = set()
    for pattern in _SIDECARS:
        found.update(_TMP.glob(pattern))
    return found


@pytest.fixture(autouse=True)
def _sweep_sqlite_sidecars():
    """Remove WAL/SHM files a test leaves in the system temp directory.

    issuedb #18. Seventeen test modules build their database with
    ``NamedTemporaryFile(suffix=".db", delete=False)`` and unlink only the
    ``.db`` — never the ``-wal`` and ``-shm`` SQLite writes beside it. Each run
    of the suite therefore left **318 files, roughly 200 MB**, in ``/tmp``.

    That is not hypothetical tidiness: it filled a 4 GB tmpfs during this
    session and the suite began failing with ``OSError: [Errno 28] No space
    left on device`` — a disk exhaustion presenting as 21 unrelated test
    failures.

    Swept HERE rather than in 28 call sites, because a rule that has to be
    remembered at every new fixture is not a rule. Only files that appear
    DURING the test are removed, so a concurrent process's temp files are never
    touched.
    """
    before = _sqlite_sidecars()
    try:
        yield
    finally:
        for path in _sqlite_sidecars() - before:
            # A file another process is still writing is not ours to force.
            with contextlib.suppress(OSError):
                path.unlink()


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
