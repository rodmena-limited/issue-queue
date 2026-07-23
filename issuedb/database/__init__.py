"""Database connection and initialization for IssueDB."""

import contextlib
import sqlite3
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, Optional

from issuedb.database._schema import initialize_schema


class DatabaseMeta(type):
    """Singleton metaclass for Database.

    Maintains a registry of Database instances keyed by the resolved absolute
    path of the database file. Each distinct path gets its own isolated
    instance, and a default-path request always returns the default instance.
    """

    _instances: dict[str, "Database"] = {}
    _instances_lock = threading.Lock()

    def __call__(cls, db_path: Optional[str] = None) -> "Database":
        # Compute a registry key from the resolved absolute path so that
        # equivalent paths (relative vs absolute, symlinks, etc.) map to the
        # same instance, and distinct paths stay isolated.
        key = str(Path(db_path).resolve()) if db_path else str(Path(".issue.db").resolve())

        # Double-checked locking: construction runs schema init, which must
        # not happen twice concurrently in-process.
        instance = cls._instances.get(key)
        if instance is None:
            with cls._instances_lock:
                instance = cls._instances.get(key)
                if instance is None:
                    instance = super().__call__(db_path)
                    cls._instances[key] = instance

        return instance


class Database(metaclass=DatabaseMeta):
    """Manages database connections and initialization.

    Uses a persistent connection per thread for performance, with WAL mode
    for better concurrency in multi-threaded environments like web servers.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize database connection manager.

        Args:
            db_path: Optional path to database file. If not provided, uses default.
        """
        # Resolve to an absolute path immediately: connections are opened
        # lazily per thread, so a later os.chdir() would otherwise silently
        # point new threads at a different database file.
        if db_path:
            self.db_path = Path(db_path).resolve()
        else:
            # Default path: ./.issue.db in current directory
            self.db_path = Path(".issue.db").resolve()

        # Create parent directory if it doesn't exist (for custom paths)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Thread-local storage for connections
        self._local = threading.local()

        # Initialize database on first use
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database schema if it doesn't exist.

        Retries on "database is locked": when several processes open a fresh
        database at once, the loser of the journal-mode/DDL race gets
        SQLITE_BUSY that busy_timeout does not always cover.
        """
        last_error: Optional[sqlite3.OperationalError] = None
        for attempt in range(5):
            try:
                with self.get_connection() as conn:
                    initialize_schema(conn)
                return
            except sqlite3.OperationalError as e:
                if "locked" not in str(e) and "busy" not in str(e):
                    raise
                last_error = e
                # Drop the possibly half-configured connection and back off.
                self.close_connection()
                time.sleep(0.05 * (2**attempt))
        assert last_error is not None
        raise last_error

    def _get_thread_connection(self) -> sqlite3.Connection:
        """Get or create a persistent connection for the current thread.

        Returns:
            sqlite3.Connection: Thread-local database connection.
        """
        conn = getattr(self._local, "connection", None)
        if conn is None:
            # Create new connection for this thread
            # check_same_thread=False is safe because we use thread-local storage
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            try:
                conn.row_factory = sqlite3.Row

                # Set connection-level pragmas (only once per connection)
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA busy_timeout = 30000")
                conn.execute("PRAGMA cache_size = 10000")
                conn.execute("PRAGMA temp_store = MEMORY")

                # Set WAL mode and synchronous level on every new connection.
                # journal_mode=WAL persists in the database file, but synchronous
                # is a per-connection setting, so it must be applied for each
                # thread's connection, not just the first one. The mode change
                # needs a moment of exclusive access, so retry briefly on
                # SQLITE_BUSY instead of crashing when several processes open a
                # fresh database at the same time.
                for attempt in range(5):
                    try:
                        conn.execute("PRAGMA journal_mode = WAL")
                        break
                    except sqlite3.OperationalError as e:
                        if "locked" not in str(e) and "busy" not in str(e):
                            raise
                        if attempt == 4:
                            raise
                        time.sleep(0.05 * (2**attempt))
                conn.execute("PRAGMA synchronous = NORMAL")
            except BaseException:
                with contextlib.suppress(Exception):
                    conn.close()
                raise

            self._local.connection = conn

        return conn

    @contextlib.contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with transaction support.

        Yields:
            sqlite3.Connection: Database connection object.

        Note:
            This is a context manager that automatically handles commits and rollbacks.
            Uses a persistent thread-local connection for performance.
        """
        conn = self._get_thread_connection()

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        # Note: We don't close the connection - it's reused for the thread

    def close_connection(self) -> None:
        """Close the thread-local connection if it exists.

        Call this when you're done with database operations in a thread,
        such as at the end of a web request or when shutting down.
        """
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
            self._local.connection = None

    def clear_database(self, confirm: bool = False) -> None:
        """Clear all data from the database.

        Args:
            confirm: Safety flag to prevent accidental data loss.

        Raises:
            ValueError: If confirm is not True.
        """
        if not confirm:
            raise ValueError("Must set confirm=True to clear database")

        # Delete from child/dependent tables before parent tables so the
        # operation is safe even though foreign-key cascade is enabled.
        tables = [
            "issue_tags",
            "issue_links",
            "issue_dependencies",
            "issue_relations",
            "code_references",
            "time_entries",
            "comments",
            "audit_logs",
            "lessons_learned",
            "workspace_state",
            "saved_searches",
            "issue_templates",
            "memory",
            "tags",
            "issues",
        ]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            conn.commit()

    def get_database_info(self) -> dict[str, Any]:
        """Get information about the database.

        Returns:
            Dictionary with database statistics.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get issue count
            cursor.execute("SELECT COUNT(*) as count FROM issues")
            issue_count = cursor.fetchone()["count"]

            # Get audit log count
            cursor.execute("SELECT COUNT(*) as count FROM audit_logs")
            audit_count = cursor.fetchone()["count"]

            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "database_path": str(self.db_path),
                "issue_count": issue_count,
                "audit_log_count": audit_count,
                "database_size_bytes": db_size,
            }


def get_database(db_path: Optional[str] = None) -> Database:
    """Get or create the global database instance.

    Args:
        db_path: Optional path to database file.

    Returns:
        Database: The database instance.
    """
    return Database(db_path)
