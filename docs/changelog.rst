Changelog
=========

All notable changes to IssueDB are documented here.

The format is based on `Keep a Changelog <https://keepachangelog.com/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/>`_.

[2.2.0] - 2025-01-XX
--------------------

Added
~~~~~

- **Comment system**: Add comments to issues for tracking notes, progress, and resolutions

  - ``comment`` command to add comments to issues
  - ``list-comments`` command to view all comments on an issue
  - ``delete-comment`` command to remove comments
  - Comments are automatically deleted when their parent issue is deleted (CASCADE)

- **CLI methods**: ``add_comment()``, ``list_comments()``, ``delete_comment()``

- **Repository methods**: ``add_comment()``, ``get_comments()``, ``delete_comment()``

- **Comment model**: New ``Comment`` dataclass with ``to_dict()`` method

- **Database schema**: New ``comments`` table with foreign key to issues

- **Tests**: 19 new tests for comment functionality

Changed
~~~~~~~

- Enabled SQLite foreign key constraints for data integrity
- Updated documentation with comment examples

[2.1.0] - 2025-01-XX
--------------------

Added
~~~~~

- **Bulk operations**: Efficiently manage multiple issues at once

  - ``bulk-create`` command: Create multiple issues from JSON
  - ``bulk-update-json`` command: Update multiple issues from JSON
  - ``bulk-close`` command: Close multiple issues by ID

- **Input options**: Both file (``-f``) and direct data (``-d``) input for bulk operations

- **Repository methods**:

  - ``bulk_create_issues()``
  - ``bulk_update_issues_from_json()``
  - ``bulk_close_issues()``

- **Audit logging**: Bulk operations logged with BULK_CREATE and BULK_UPDATE actions

- **Tests**: Comprehensive tests for all bulk operations

Changed
~~~~~~~

- Fixed datetime handling for Python 3.12+ compatibility (no more deprecation warnings)
- Improved type annotations throughout codebase

[2.0.0] - 2025-01-XX
--------------------

Added
~~~~~

- **Audit logging**: Full transactional audit trail

  - All issue changes logged immutably
  - Audit logs preserved even after issue deletion
  - ``audit`` command to view audit history

- **Reporting**: New summary and report commands

  - ``summary`` command for aggregate statistics
  - ``report`` command for grouped issue lists

- **Search**: ``search`` command for keyword-based issue lookup

- **Database info**: ``info`` command showing database statistics

Changed
~~~~~~~

- Enhanced JSON output format
- Improved error messages
- Better validation for all inputs

[1.1.0] - 2025-01-XX
--------------------

Added
~~~~~

- **Filtering**: Filter issues by status and priority
- **Pagination**: ``--limit`` option for list commands
- **Next issue**: ``next`` command for FIFO queue processing

Changed
~~~~~~~

- Improved table formatting for human-readable output
- Better handling of empty results

[1.0.0] - 2025-01-XX
--------------------

Initial release.

Added
~~~~~

- **Core functionality**:

  - Create issues with title, description, priority, status
  - List all issues
  - Get issue details by ID
  - Update issue fields
  - Delete issues

- **CLI**: Full command-line interface via ``issuedb-cli``

- **JSON output**: ``--json`` flag for all commands

- **SQLite storage**: Local database at ``~/.issuedb/issuedb.sqlite``

- **Priority levels**: low, medium, high, critical

- **Status values**: open, in-progress, closed

- **Python API**: Programmatic access via ``IssueRepository`` class

Migration Notes
---------------

From 1.x to 2.x
~~~~~~~~~~~~~~~

Version 2.0 added the audit_log table. When upgrading:

1. The database schema will be updated automatically on first run
2. Existing issues are preserved
3. Historical audit logs are not retroactively created

From 2.0 to 2.1
~~~~~~~~~~~~~~~

No migration needed. New bulk operation features are additive.

From 2.1 to 2.2
~~~~~~~~~~~~~~~

Version 2.2 adds the comments table:

1. Schema updates automatically on first run
2. Foreign key constraints are now enabled
3. Existing data is preserved
