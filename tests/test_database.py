"""Tests for database module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from issuedb.database import Database, get_database


class TestDatabase:
    """Test Database class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        yield path
        # Cleanup
        Path(path).unlink(missing_ok=True)

    def test_initialization_creates_database(self, temp_db_path):
        """Test that initialization creates database and tables."""
        db = Database(temp_db_path)

        # Check that database file exists
        assert Path(temp_db_path).exists()

        # Check that tables exist
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check issues table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='issues'")
            assert cursor.fetchone() is not None

            # Check audit_logs table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'"
            )
            assert cursor.fetchone() is not None

    def test_default_path(self):
        """Test that default path is used when not specified."""
        # Reset the singleton to test default path behavior
        # Note: _instance is stored on Database class, not DatabaseMeta
        old_instance = Database._instance  # type: ignore[attr-defined]
        Database._instance = None  # type: ignore[attr-defined]
        try:
            db = Database()
            expected_path = Path(".issue.db")
            assert db.db_path == expected_path
        finally:
            # Restore the singleton and cleanup
            Database._instance = old_instance  # type: ignore[attr-defined]
            Path(".issue.db").unlink(missing_ok=True)

    def test_indexes_created(self, temp_db_path):
        """Test that all required indexes are created."""
        db = Database(temp_db_path)

        expected_indexes = [
            "idx_issues_status",
            "idx_issues_priority",
            "idx_issues_created_at",
            "idx_audit_logs_issue_id",
            "idx_audit_logs_timestamp",
        ]

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

            for index_name in expected_indexes:
                assert index_name in indexes

    def test_get_connection_context_manager(self, temp_db_path):
        """Test that get_connection works as a context manager."""
        db = Database(temp_db_path)

        with db.get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

            # Test that we can execute queries
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_transaction_rollback_on_error(self, temp_db_path):
        """Test that transactions are rolled back on error."""
        db = Database(temp_db_path)

        # Insert a test row
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO issues (title) VALUES (?)",
                ("Test",),
            )

        # Try to insert with error (violating NOT NULL constraint)
        with pytest.raises(sqlite3.IntegrityError), db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO issues (title) VALUES (NULL)")

        # Check that first insert was committed
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM issues")
            assert cursor.fetchone()[0] == 1

    def test_clear_database(self, temp_db_path):
        """Test clearing the database."""
        db = Database(temp_db_path)

        # Insert test data
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO issues (title) VALUES (?)",
                ("Test",),
            )
            cursor.execute(
                "INSERT INTO audit_logs (issue_id, action) VALUES (?, ?)",
                (1, "CREATE"),
            )

        # Try to clear without confirmation
        with pytest.raises(ValueError, match="Must set confirm=True"):
            db.clear_database()

        # Clear with confirmation
        db.clear_database(confirm=True)

        # Check that tables are empty
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM issues")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM audit_logs")
            assert cursor.fetchone()[0] == 0

    def test_get_database_info(self, temp_db_path):
        """Test getting database information."""
        db = Database(temp_db_path)

        # Insert test data
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO issues (title) VALUES (?)",
                ("Test1",),
            )
            cursor.execute(
                "INSERT INTO issues (title) VALUES (?)",
                ("Test2",),
            )
            cursor.execute(
                "INSERT INTO audit_logs (issue_id, action) VALUES (?, ?)",
                (1, "CREATE"),
            )

        info = db.get_database_info()

        assert info["database_path"] == str(temp_db_path)
        assert info["issue_count"] == 2
        assert info["audit_log_count"] == 1
        assert info["database_size_bytes"] > 0


class TestGetDatabase:
    """Test get_database function."""

    def test_singleton_instance(self):
        """Test that get_database returns the same instance."""
        db1 = get_database()
        db2 = get_database()
        assert db1 is db2

    def test_different_path_creates_new_instance(self):
        """Test that different path creates new instance."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f1:  # noqa: SIM117
            with tempfile.NamedTemporaryFile(suffix=".db") as f2:
                db1 = get_database(f1.name)
                db2 = get_database(f2.name)
                assert db1 is not db2
                assert str(db1.db_path) == f1.name
                assert str(db2.db_path) == f2.name
