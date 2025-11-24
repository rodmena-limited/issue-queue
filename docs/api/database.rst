Database API
============

The database module handles SQLite connection management and schema setup.

.. module:: issuedb.database

Connection Management
---------------------

.. py:function:: get_connection(db_path: Optional[str] = None) -> sqlite3.Connection

   Get a database connection.

   :param db_path: Optional path to database file. If None, uses default path ``~/.issuedb/issuedb.sqlite``
   :returns: SQLite connection object with foreign keys enabled
   :raises sqlite3.Error: If connection fails

   **Features:**

   - Automatically creates the database directory if it doesn't exist
   - Enables foreign key constraints
   - Returns a connection ready for transactions

   **Example:**

   .. code-block:: python

      from issuedb.database import get_connection

      # Use default database
      conn = get_connection()

      # Use custom database
      conn = get_connection("/path/to/custom.db")

      # Use in-memory database for testing
      conn = get_connection(":memory:")

Schema Setup
------------

.. py:function:: setup_database(conn: sqlite3.Connection) -> None

   Initialize the database schema.

   :param conn: SQLite connection object
   :raises sqlite3.Error: If schema creation fails

   This function creates all required tables and indexes if they don't exist:

   **Tables created:**

   - ``issues`` - Main issue tracking table
   - ``comments`` - Comments linked to issues
   - ``audit_log`` - Immutable audit trail

   **Example:**

   .. code-block:: python

      from issuedb.database import get_connection, setup_database

      conn = get_connection()
      setup_database(conn)

Database Schema
---------------

Issues Table
~~~~~~~~~~~~

.. code-block:: sql

   CREATE TABLE issues (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       title TEXT NOT NULL,
       description TEXT,
       priority TEXT NOT NULL DEFAULT 'medium',
       status TEXT NOT NULL DEFAULT 'open',
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   )

**Columns:**

- ``id``: Auto-incrementing primary key
- ``title``: Issue title (required)
- ``description``: Detailed description (optional)
- ``priority``: One of: low, medium, high, critical
- ``status``: One of: open, in-progress, closed
- ``created_at``: Creation timestamp
- ``updated_at``: Last modification timestamp

**Indexes:**

- ``idx_issues_status`` on ``status``
- ``idx_issues_priority`` on ``priority``
- ``idx_issues_created_at`` on ``created_at``

Comments Table
~~~~~~~~~~~~~~

.. code-block:: sql

   CREATE TABLE comments (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       issue_id INTEGER NOT NULL,
       text TEXT NOT NULL,
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (issue_id) REFERENCES issues (id) ON DELETE CASCADE
   )

**Columns:**

- ``id``: Auto-incrementing primary key
- ``issue_id``: Foreign key to issues table
- ``text``: Comment content (required)
- ``created_at``: Creation timestamp

**Behavior:**

- Comments are automatically deleted when their parent issue is deleted (CASCADE)

**Indexes:**

- ``idx_comments_issue_id`` on ``issue_id``

Audit Log Table
~~~~~~~~~~~~~~~

.. code-block:: sql

   CREATE TABLE audit_log (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       issue_id INTEGER NOT NULL,
       action TEXT NOT NULL,
       field_name TEXT,
       old_value TEXT,
       new_value TEXT,
       timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   )

**Columns:**

- ``id``: Auto-incrementing primary key
- ``issue_id``: Reference to the affected issue (preserved after deletion)
- ``action``: Type of operation (CREATE, UPDATE, DELETE, BULK_CREATE, BULK_UPDATE)
- ``field_name``: Name of the changed field (for UPDATE operations)
- ``old_value``: Previous value (JSON for CREATE/DELETE, string for UPDATE)
- ``new_value``: New value (JSON for CREATE, string for UPDATE)
- ``timestamp``: When the change occurred

**Note:** Audit logs are immutable and preserved even when issues are deleted.

**Indexes:**

- ``idx_audit_log_issue_id`` on ``issue_id``
- ``idx_audit_log_timestamp`` on ``timestamp``

Default Database Location
-------------------------

The default database is stored at:

.. code-block:: text

   ~/.issuedb/issuedb.sqlite

On first run, IssueDB automatically:

1. Creates the ``~/.issuedb/`` directory if it doesn't exist
2. Creates the SQLite database file
3. Initializes all tables and indexes

Custom Database Paths
---------------------

You can specify a custom database path:

**Environment variable (planned):**

.. code-block:: bash

   export ISSUEDB_PATH=/path/to/custom.db

**Command line:**

.. code-block:: bash

   issuedb-cli --db /path/to/custom.db list

**Python API:**

.. code-block:: python

   from issuedb.repository import IssueRepository

   repo = IssueRepository("/path/to/custom.db")

In-Memory Database
------------------

For testing, you can use an in-memory database:

.. code-block:: python

   from issuedb.repository import IssueRepository

   # Create in-memory database
   repo = IssueRepository(":memory:")

   # Use normally - data is lost when connection closes
   issue = repo.create_issue(Issue(title="Test"))

Transaction Safety
------------------

IssueDB uses SQLite transactions for data integrity:

- All write operations are wrapped in transactions
- Audit logs are created atomically with data changes
- Foreign key constraints are enforced
- Rollback on error ensures consistency

**Example of transaction safety:**

.. code-block:: python

   # If any part of bulk_create fails, all changes are rolled back
   try:
       repo.bulk_create_issues(issues_data)
   except ValueError:
       # Database remains unchanged
       pass

Backup and Restore
------------------

**Backup:**

.. code-block:: bash

   # Simple file copy (ensure no active connections)
   cp ~/.issuedb/issuedb.sqlite ~/.issuedb/backup-$(date +%Y%m%d).sqlite

   # Using SQLite backup command
   sqlite3 ~/.issuedb/issuedb.sqlite ".backup backup.sqlite"

**Restore:**

.. code-block:: bash

   cp backup.sqlite ~/.issuedb/issuedb.sqlite

**Export to SQL:**

.. code-block:: bash

   sqlite3 ~/.issuedb/issuedb.sqlite .dump > backup.sql

Performance Considerations
--------------------------

The database is optimized for:

- **Fast lookups**: Indexes on commonly filtered columns
- **Quick listing**: Status and priority indexes
- **Audit queries**: Timestamp index on audit_log

For large datasets (10,000+ issues), consider:

- Using ``limit`` and ``offset`` for pagination
- Adding custom indexes for specific query patterns
- Periodic archival of closed issues
