"""Database connection and initialization for IssueDB."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional


class Database:
    """Manages database connections and initialization."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize database connection manager.

        Args:
            db_path: Optional path to database file. If not provided, uses default.
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Default path: ./.issue.db in current directory
            self.db_path = Path(".issue.db")

        # Create parent directory if it doesn't exist (for custom paths)
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database on first use
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database schema if it doesn't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create issues table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create audit_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issues_status
                ON issues(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issues_priority
                ON issues(priority)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issues_created_at
                ON issues(created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_logs_issue_id
                ON audit_logs(issue_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp
                ON audit_logs(timestamp)
            """)

            conn.commit()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with transaction support.

        Yields:
            sqlite3.Connection: Database connection object.

        Note:
            This is a context manager that automatically handles commits and rollbacks.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def clear_database(self, confirm: bool = False) -> None:
        """Clear all data from the database.

        Args:
            confirm: Safety flag to prevent accidental data loss.

        Raises:
            ValueError: If confirm is not True.
        """
        if not confirm:
            raise ValueError("Must set confirm=True to clear database")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM issues")
            cursor.execute("DELETE FROM audit_logs")
            conn.commit()

    def get_database_info(self) -> dict:
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


# Global database instance
_db: Optional[Database] = None


def get_database(db_path: Optional[str] = None) -> Database:
    """Get or create the global database instance.

    Args:
        db_path: Optional path to database file.

    Returns:
        Database: The database instance.
    """
    global _db
    if _db is None or (db_path and str(_db.db_path) != db_path):
        _db = Database(db_path)
    return _db
