Changelog
=========

All notable changes to IssueDB are documented here.

The format is based on `Keep a Changelog <https://keepachangelog.com/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/>`_.

[2.10.0] - 2026-06-21
---------------------

Fixed
~~~~~

- **``create --tag`` did nothing**: the documented ``create --tag`` flag was never
  implemented; ``create`` now accepts repeatable ``--tag`` options and attaches them.
- **Due date / estimate never displayed**: ``_row_to_issue`` used ``"col" in row``,
  but ``sqlite3.Row`` membership tests values not column names, so ``due_date`` and
  ``estimated_hours`` were stored but never read back onto an ``Issue``. Now fixed
  (uses ``row.keys()``), so ``get``/``list`` show due dates again.
- **Cannot clear a field**: ``update -d ""`` / ``--due-date ""`` now clears the field
  (previously the empty value was silently ignored).
- **Redundant due-date audit entries**: re-setting the same due date is now a true
  no-op (dates are normalised before comparison).
- **Time report dropped estimated issues**: ``get_time_report`` kept its time
  predicates in ``WHERE``, silently turning the ``LEFT JOIN`` into an ``INNER JOIN``;
  issues with an estimate but no logged time in the period are no longer dropped.
- **Non-atomic operations**: ``add_dependency`` now checks for cycles inside the same
  transaction as the insert (rolling back on a cycle), and ``start_issue``/``stop_issue``
  apply the workspace and status changes together; ``get_last_fetched`` no longer opens
  a nested connection mid-iteration.
- **Unreachable CLI commands**: the ``find-similar`` and ``dedupe`` subparsers were
  registered *after* ``parse_args()`` and could never be invoked; the time-tracking
  (``timer-start``, ``timer-stop``, ``timer-status``, ``estimate``, ``time-log``,
  ``time-report``), code-reference (``attach``, ``detach``, ``refs``, ``affected``)
  and pattern bulk commands (``bulk-close-pattern``, ``bulk-update-pattern``,
  ``bulk-delete-pattern``) had implementations but were never wired to the parser or
  dispatcher. All of these are now registered and dispatched.
- **``report`` crash**: ``get_report(group_by="status")`` raised ``KeyError`` for any
  issue with the valid ``wont-do`` status. ``wont_do`` is now grouped correctly.
- **Wrong database returned**: the ``Database`` singleton was keyed on a single global
  instance, so a request for the default database could return a previously-opened
  custom path (and concurrent web requests with ``?db=`` could clobber each other).
  Instances are now cached per resolved path.
- **``--json`` error output**: errors are now emitted as JSON (``{"error": ...}``) when
  ``--json`` is set instead of plain text.
- **``summary``/``report``/``info``**: human-readable output no longer leaks raw Python
  ``dict`` reprs for nested values.
- **Thread pragmas**: ``PRAGMA synchronous=NORMAL`` is now applied to every connection
  instead of only the first thread's.
- **``clear``**: now clears all data tables, not just ``issues`` and ``audit_logs``.
- **Similarity performance**: long descriptions no longer trigger an O(n·m) character
  Levenshtein blow-up; token similarity is used past a length cap and for very uneven
  lengths (which also improves short-query-in-long-text matching).
- **Git integration**: all ``git`` subprocess calls now use a timeout, an explicit
  ``utf-8``/``replace`` decode, and ``--`` / leading-dash guards against argument
  injection.

Security
~~~~~~~~

- **CSRF**: state-changing web requests from a cross-origin ``Origin``/``Referer`` are
  now rejected; a secret key is always set.
- **Stored XSS**: the linked-issue delete button no longer interpolates the
  user-controlled relation type into an inline ``onclick`` handler.
- **Command injection**: the Ollama helper no longer runs model-generated commands
  through ``shell=True``; commands are parsed with ``shlex`` and must start with
  ``issuedb-cli``.
- **Input validation**: invalid ``status``/``priority`` and malformed JSON bodies in the
  web API now return ``400`` instead of ``500``.
- **Safer default bind**: ``issuedb-cli web`` now binds to ``127.0.0.1`` by default
  (pass ``--host 0.0.0.0`` to expose it on the network).
- **CSS injection**: tag colours are validated against a hex pattern before being
  rendered into inline ``style`` attributes (invalid values fall back to a default).
- **Open redirect**: the comment-delete endpoint redirects to a server-built URL
  instead of the client-supplied ``Referer``.
- **Resource limits**: the Ollama helper truncates oversized requests and caps the
  response read.

Changed
~~~~~~~

- ``bulk-update`` refuses to update **all** issues unless a filter is given or the new
  ``--all`` flag is passed.
- ``Status.from_string`` now accepts underscore and space separators
  (e.g. ``in_progress``) in addition to the canonical hyphenated form.

[2.5.0] - 2025-11-29
--------------------

Added
~~~~~

- **Memory System**: Persistent storage for AI agents and general knowledge

  - ``memory`` command to add, list, update, and delete memory items
  - ``Memory`` model and database table
  - Web UI integration at ``/memory``

- **Lessons Learned**: Track knowledge gained from resolved issues

  - ``lesson`` command to add and list lessons
  - ``LessonLearned`` model and database table
  - Web UI integration at ``/lessons``

- **Tagging**: Flexible categorization for issues

  - ``tag`` command to add, remove, and list tags
  - ``--tag`` flag in ``create`` and ``list`` commands
  - Tag filtering in CLI and Web UI

- **Due Dates**: Set deadlines for issues

  - ``--due-date`` flag in ``create`` and ``update`` commands
  - Due date display in CLI and Web UI

- **Linked Issues**: Connect related issues

  - ``link`` and ``unlink`` commands to manage relationships
  - Relationship types (e.g., "related", "blocks")
  - Web UI support for linking issues

- **Web UI Enhancements**:

  - New Memory and Lessons pages
  - Linked Issues section in Issue Detail
  - Improved sidebar layout

[2.4.0] - 2025-11-26
--------------------

Added
~~~~~

- **Issue Dependencies**: Track blocking relationships between issues

  - ``block`` command to mark issues as blocked by others
  - ``unblock`` command to remove blockers
  - ``deps`` command to view dependency graph
  - ``blocked`` command to list all blocked issues

- **Code References**: Link issues to specific code locations

  - ``attach`` command to link files/lines to issues
  - ``detach`` command to remove code references
  - ``refs`` command to list references for an issue
  - ``affected`` command to find issues referencing a file

- **Time Tracking**: Track time spent on issues

  - ``timer-start`` and ``timer-stop`` commands
  - ``timer-status`` to check active timers
  - ``set-estimate`` to set estimated hours
  - ``time-log`` to view time entries
  - ``time-report`` for time summaries (all/week/month)

- **Workspace Awareness**: Track current working context

  - ``workspace`` command for status overview
  - ``start`` command to begin working (sets active + starts timer)
  - ``stop`` command to finish working (with optional --close)
  - ``active`` command to show current issue

- **Issue Context**: Comprehensive context for LLM agents

  - ``context`` command returns issue + comments + history + related + suggestions
  - ``--compact`` flag for minimal context

- **Duplicate Detection**: Find similar issues

  - ``find-similar`` command with configurable threshold
  - ``find-duplicates`` to find duplicate groups
  - ``--check-duplicates`` flag for create command
  - Similarity algorithms: Levenshtein and Jaccard

- **Issue Templates**: Predefined issue templates

  - ``templates`` command to list available templates
  - ``--template`` flag for create command
  - Built-in templates: bug, feature, task

- **Bulk Pattern Operations**: Pattern-based bulk operations

  - ``bulk-close-pattern`` for closing by pattern
  - ``bulk-update-pattern`` for updating by pattern
  - ``bulk-delete-pattern`` for deleting by pattern
  - Support for glob and regex patterns
  - ``--dry-run`` flag for preview

- **Database schema**: New tables for dependencies, code_references, time_entries, workspace_state, issue_templates

- **Tests**: 501 tests covering all new functionality

Changed
~~~~~~~

- Updated LLM agent prompt (PROMPT.txt) with all new commands
- Updated README.md with new features
- Updated CLI reference documentation
- Improved type annotations (mypy clean)
- Code style improvements (ruff clean)

[2.3.1] - 2025-11-25
--------------------

Fixed
~~~~~

- **--ollama flag now accepts unquoted multi-word requests**

  - Before: ``issuedb-cli --ollama "create a high priority bug"``
  - After: ``issuedb-cli --ollama create a high priority bug``
  - Note: ``--ollama-model``, ``--ollama-host``, ``--ollama-port`` must come BEFORE ``--ollama``

- 4 new tests for argparse behavior (now 136 total)

[2.3.0] - 2025-11-25
--------------------

Added
~~~~~

- **Fetch History Tracking**: Track which issues were fetched via ``get-next``

  - ``get-next`` now logs a ``FETCH`` action in the audit trail
  - ``get-last`` command to view last fetched issue(s)
  - ``-n/--number`` flag to get last N fetched issues (default: 1)
  - Shows current state of existing issues or reconstructs deleted issues from audit log
  - Example: ``issuedb-cli get-last -n 5`` to see last 5 fetched issues

- **Repository methods**: ``get_last_fetched(limit)``

- **API parameter**: ``log_fetch`` in ``get_next_issue()`` to control logging

- **Tests**: 16 new tests for get-last functionality (now 132 total)

Changed
~~~~~~~

- Updated LLM agent prompt with get-last examples
- Full documentation update

[2.2.0] - 2025-11-24
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

From 2.2 to 2.3
~~~~~~~~~~~~~~~

No migration needed. New fetch history tracking is additive:

1. ``get-next`` will start logging ``FETCH`` actions automatically
2. ``get-last`` command will return results after issues are fetched
3. Historical fetches are not retroactively logged
