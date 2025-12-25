"""Database connection and initialization for IssueDB."""

import contextlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Generator, Optional


class DatabaseMeta(type):
    """Singleton metaclass for Database.

    Ensures only one Database instance exists, unless a new path is provided.
    """
    _instance: Optional["Database"] = None

    def __call__(cls, db_path: Optional[str] = None) -> "Database":
        # Create new instance if none exists or if a different path is provided
        if cls._instance is None or (
            db_path and str(cls._instance.db_path) != db_path
        ):
            cls._instance = super().__call__(db_path)

        return cls._instance


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
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Default path: ./.issue.db in current directory
            self.db_path = Path(".issue.db")

        # Create parent directory if it doesn't exist (for custom paths)
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Thread-local storage for connections
        self._local = threading.local()
        # Track if WAL mode has been set (only needs to be done once per db file)
        self._wal_initialized = False

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

            # Create comments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE CASCADE
                )
            """)

            # Create code_references table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS code_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    note TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE CASCADE
                )
            """)

            # Create workspace_state table (single-row table)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspace_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    active_issue_id INTEGER,
                    started_at TIMESTAMP,
                    FOREIGN KEY (active_issue_id) REFERENCES issues (id) ON DELETE SET NULL
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

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_issue_id
                ON comments(issue_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_created_at
                ON comments(created_at)
            """)

            # Create indexes for code_references
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_code_references_issue_id
                ON code_references(issue_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_code_references_file_path
                ON code_references(file_path)
            """)

            # Create saved_searches table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    query_json TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for saved_searches
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_saved_searches_name
                ON saved_searches(name)
            """)

            # Create issue_dependencies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blocker_id INTEGER NOT NULL,
                    blocked_id INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (blocker_id) REFERENCES issues (id) ON DELETE CASCADE,
                    FOREIGN KEY (blocked_id) REFERENCES issues (id) ON DELETE CASCADE,
                    UNIQUE(blocker_id, blocked_id)
                )
            """)

            # Create indexes for issue_dependencies
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dependencies_blocker_id
                ON issue_dependencies(blocker_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dependencies_blocked_id
                ON issue_dependencies(blocked_id)
            """)

            # Create time_entries table for time tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS time_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    ended_at TIMESTAMP,
                    duration_seconds INTEGER,
                    note TEXT,
                    FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE CASCADE
                )
            """)

            # Create indexes for time_entries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_time_entries_issue_id
                ON time_entries(issue_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_time_entries_started_at
                ON time_entries(started_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_time_entries_ended_at
                ON time_entries(ended_at)
            """)

            # Add estimated_hours column to issues table if it doesn't exist
            # Check if column exists first
            cursor.execute("PRAGMA table_info(issues)")
            columns = [row[1] for row in cursor.fetchall()]
            if "estimated_hours" not in columns:
                cursor.execute("ALTER TABLE issues ADD COLUMN estimated_hours REAL")

            # Create issue_templates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    title_prefix TEXT,
                    default_priority TEXT,
                    default_status TEXT,
                    required_fields TEXT,
                    field_prompts TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for templates
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_name
                ON issue_templates(name)
            """)

            # Create issue_links table for git integration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER NOT NULL,
                    link_type TEXT NOT NULL,
                    reference TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE CASCADE,
                    UNIQUE(issue_id, link_type, reference)
                )
            """)

            # Create indexes for issue_links
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issue_links_issue_id
                ON issue_links(issue_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issue_links_link_type
                ON issue_links(link_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issue_links_reference
                ON issue_links(reference)
            """)

            # --- New Features ---

            # Create memory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_key
                ON memory(key)
            """)

            # Create lessons_learned table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons_learned (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER,
                    lesson TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE SET NULL
                )
            """)

            # Create tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create issue_tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_tags (
                    issue_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE,
                    PRIMARY KEY (issue_id, tag_id)
                )
            """)

            # Create issue_relations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_issue_id INTEGER NOT NULL,
                    target_issue_id INTEGER NOT NULL,
                    relation_type TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_issue_id) REFERENCES issues (id) ON DELETE CASCADE,
                    FOREIGN KEY (target_issue_id) REFERENCES issues (id) ON DELETE CASCADE,
                    UNIQUE(source_issue_id, target_issue_id, relation_type)
                )
            """)

            # Add due_date column to issues table if it doesn't exist
            cursor.execute("PRAGMA table_info(issues)")
            columns = [row[1] for row in cursor.fetchall()]
            if "due_date" not in columns:
                cursor.execute("ALTER TABLE issues ADD COLUMN due_date TIMESTAMP")

            # Initialize built-in templates if they don't exist
            self._initialize_builtin_templates(cursor)

            conn.commit()

    def _initialize_builtin_templates(self, cursor: Any) -> None:
        """Initialize built-in templates if they don't exist.

        Args:
            cursor: Database cursor to use for operations.
        """
        # Define built-in templates
        builtin_templates = [
            {
                "name": "bug",
                "title_prefix": "[BUG]",
                "default_priority": "high",
                "default_status": "open",
                "required_fields": json.dumps(["description"]),
                "field_prompts": json.dumps(
                    {"description": "Describe the bug (steps to reproduce, expected vs actual)"}
                ),
            },
            {
                "name": "feature",
                "title_prefix": "[FEATURE]",
                "default_priority": "medium",
                "default_status": "open",
                "required_fields": json.dumps(["description"]),
                "field_prompts": json.dumps(
                    {"description": "Describe the feature request and its benefits"}
                ),
            },
            {
                "name": "task",
                "title_prefix": "[TASK]",
                "default_priority": "low",
                "default_status": "open",
                "required_fields": json.dumps([]),
                "field_prompts": json.dumps({}),
            },
        ]

        # Insert templates if they don't exist
        for template in builtin_templates:
            cursor.execute(
                """
                INSERT OR IGNORE INTO issue_templates
                (name, title_prefix, default_priority, default_status,
                 required_fields, field_prompts)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    template["name"],
                    template["title_prefix"],
                    template["default_priority"],
                    template["default_status"],
                    template["required_fields"],
                    template["field_prompts"],
                ),
            )

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
            conn.row_factory = sqlite3.Row

            # Set connection-level pragmas (only once per connection)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")

            # Set WAL mode (persists in database file, but we set it to be sure)
            if not self._wal_initialized:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                self._wal_initialized = True

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

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM issues")
            cursor.execute("DELETE FROM audit_logs")
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
