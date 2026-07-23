"""Schema creation DDL for IssueDB.

This module holds the table/index DDL and the built-in template seeding,
extracted from the Database class so the package files stay small. The
runtime behavior is identical to the original inline implementation.
"""

import contextlib
import json
import sqlite3
from typing import Any


def _add_column_if_missing(cursor: Any, table: str, column: str, ddl: str) -> None:
    """Add a column when absent, tolerating the concurrent-migration race.

    Two processes can both observe the column as missing and both issue the
    ALTER; the loser gets "duplicate column name", which means the migration
    is already done and must not crash the caller.
    """
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema if it doesn't exist."""
    cursor = conn.cursor()

    # Detect a fresh database before any DDL runs, so one-time seeding (the
    # built-in templates) happens only on creation and deleted templates are
    # not resurrected on every process start.
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='issues'")
    is_fresh_database = cursor.fetchone()[0] == 0

    # Create issues table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
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
            timestamp TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Create comments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
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

    # At most one running timer per issue: closes the check-then-insert race
    # between concurrent processes. Existing databases that already contain
    # duplicate running timers would make the index creation fail — in that
    # case skip it (the application-level check still applies) rather than
    # breaking every subsequent CLI invocation.
    with contextlib.suppress(sqlite3.OperationalError):
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_time_entries_one_running
            ON time_entries(issue_id) WHERE ended_at IS NULL
        """)

    # Add estimated_hours column to issues table if it doesn't exist
    _add_column_if_missing(cursor, "issues", "estimated_hours", "REAL")

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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE SET NULL
        )
    """)

    # Create tags table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Create issue_tags table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issue_tags (
            issue_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
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
            created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (source_issue_id) REFERENCES issues (id) ON DELETE CASCADE,
            FOREIGN KEY (target_issue_id) REFERENCES issues (id) ON DELETE CASCADE,
            UNIQUE(source_issue_id, target_issue_id, relation_type)
        )
    """)

    # Add due_date column to issues table if it doesn't exist
    _add_column_if_missing(cursor, "issues", "due_date", "TIMESTAMP")

    # Seed built-in templates only on a fresh database so user deletions of
    # the built-ins are respected on subsequent starts.
    if is_fresh_database:
        initialize_builtin_templates(cursor)

    conn.commit()


def initialize_builtin_templates(cursor: Any) -> None:
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
