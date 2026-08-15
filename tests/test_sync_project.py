"""The project identity recorded in .issue.db.

The property that matters is not "it stores a string". It is that a MISSING
project id STOPS a derivation rather than silently changing what every uid
means: project_uid is field 1 of the canonical form, so deriving with an empty
string produces uids the server will never agree with, and the rows fail to
converge with nothing erroring.
"""

from __future__ import annotations

import sqlite3

import pytest

from issuedb.database import Database
from issuedb.repository import IssueRepository
from issuedb.sync._project import (
    ProjectIdentityError,
    get_project_uid,
    get_server_url,
    record_project_uid,
    require_project_uid,
)

PROJECT = "01M01SXNCCXGWQHT1E5K8VZGAZ"
OTHER = "01M0OTHERPROJECTZZZZZZZZZZ"
SERVER = "https://tracker.rodmena.co.uk"


@pytest.fixture
def repo(tmp_path):
    repository = IssueRepository(str(tmp_path / ".issue.db"))
    yield repository
    repository.db.close_connection()
    Database._instances.clear()


@pytest.fixture
def conn(repo):
    connection = sqlite3.connect(str(repo.db.db_path))
    yield connection
    connection.close()


def test_the_table_exists_after_migration(repo, conn):
    """Control: without it every test below would exercise nothing."""
    assert repo.db.schema_version >= 4
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sync_project'"
    ).fetchone()
    assert row[0] == 1


def test_an_unsynced_database_has_no_project(conn):
    assert get_project_uid(conn) is None


def test_recording_and_reading_back(conn):
    assert record_project_uid(conn, PROJECT, SERVER) is True
    conn.commit()
    assert get_project_uid(conn) == PROJECT
    assert get_server_url(conn) == SERVER


def test_recording_the_same_project_twice_is_not_an_error(conn):
    """A second sync must not fail; it just has nothing to record."""
    assert record_project_uid(conn, PROJECT, SERVER) is True
    assert record_project_uid(conn, PROJECT, SERVER) is False
    conn.commit()
    assert get_project_uid(conn) == PROJECT


def test_a_different_project_is_refused(conn):
    """Adopting a new project id would merge two projects' rows.

    Happens when a path is reused, a clone is repointed, or a key is swapped.
    Overwriting would be silent; the rows of two projects would then share one
    identity and no error would ever be raised.
    """
    record_project_uid(conn, PROJECT, SERVER)
    conn.commit()

    with pytest.raises(ProjectIdentityError, match="belongs to project"):
        record_project_uid(conn, OTHER, SERVER)

    assert get_project_uid(conn) == PROJECT, "the recorded project was overwritten"


def test_an_empty_project_uid_is_refused(conn):
    """An unscoped key gets no project_uid; recording '' would poison every uid."""
    with pytest.raises(ProjectIdentityError, match="empty project_uid"):
        record_project_uid(conn, "", SERVER)
    assert get_project_uid(conn) is None


# --- the guard that protects uid derivation -------------------------------


def test_require_refuses_rather_than_returning_a_placeholder(conn):
    """The load-bearing behaviour.

    `get_project_uid(conn) or ""` is the natural thing to write and it is
    catastrophic: an empty field 1 hashes happily and yields a uid the server
    never agrees with. The failure has to be loud here or it is silent forever.
    """
    with pytest.raises(ProjectIdentityError, match="field 1 of every derived uid"):
        require_project_uid(conn)


def test_require_returns_the_recorded_project(conn):
    record_project_uid(conn, PROJECT, SERVER)
    conn.commit()
    assert require_project_uid(conn) == PROJECT


def test_a_derived_uid_actually_changes_with_the_project(conn):
    """Proves field 1 is not decorative.

    If the project id did not affect the hash, all of the above would be
    bookkeeping and an empty value would be harmless.
    """
    from issuedb.sync import derived_uid

    assert derived_uid("issue_tag", PROJECT, "i1", "bug") != derived_uid(
        "issue_tag", OTHER, "i1", "bug"
    )
    assert derived_uid("issue_tag", "", "i1", "bug") != derived_uid(
        "issue_tag", PROJECT, "i1", "bug"
    )


# --- it is safe to commit --------------------------------------------------


def test_the_recorded_identity_contains_no_secret(repo, conn):
    """It lives in a file many repos commit to git, so this is not cosmetic."""
    record_project_uid(conn, PROJECT, SERVER)
    conn.commit()

    from issuedb.sync._credentials import parse_token

    key_id, secret = parse_token("trk_somekeyid_supersecretvalue")
    raw = (repo.db.db_path).read_bytes()
    assert secret.encode() not in raw
    assert key_id.encode() not in raw


def test_only_one_project_row_can_exist_even_via_raw_sql(conn):
    """Enforced by CHECK (id = 1), not by convention.

    A direct sqlite3 write is a supported way to touch this file, so the
    single-project rule has to hold against one.
    """
    record_project_uid(conn, PROJECT, SERVER)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sync_project (id, project_uid, server_url) VALUES (2, ?, ?)",
            (OTHER, SERVER),
        )
