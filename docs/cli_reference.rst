CLI Reference
=============

This document provides a complete reference for all IssueDB command-line interface commands and options.

Global Options
--------------

These options can be used with any command:

``--db PATH``
    Use a custom database file instead of the default ``./issuedb.sqlite``

``--json``
    Output results in JSON format for scripting and automation

``--prompt``
    Display the LLM agent prompt guide

``--ollama REQUEST``
    Use Ollama to convert natural language to commands

``--ollama-model MODEL``
    Specify the Ollama model to use (default: from environment or llama3.2)

``--ollama-host HOST``
    Ollama server host (default: localhost)

``--ollama-port PORT``
    Ollama server port (default: 11434)

Issue Management Commands
-------------------------

create
~~~~~~

Create a new issue.

.. code-block:: bash

   issuedb-cli create -t "TITLE" [-d "DESCRIPTION"] [--priority PRIORITY] [--status STATUS]

**Arguments:**

- ``-t, --title`` (required): Issue title
- ``-d, --description``: Detailed description
- ``--priority``: Priority level (low, medium, high, critical). Default: medium
- ``--status``: Initial status (open, in-progress, closed). Default: open

**Examples:**

.. code-block:: bash

   # Simple issue
   issuedb-cli create -t "Fix bug"

   # With all options
   issuedb-cli create -t "Critical security fix" -d "SQL injection in login form" --priority critical

   # With JSON output
   issuedb-cli --json create -t "New feature" --priority high

list
~~~~

List issues with optional filters.

.. code-block:: bash

   issuedb-cli list [-s STATUS] [--priority PRIORITY] [-l LIMIT]

**Arguments:**

- ``-s, --status``: Filter by status (open, in-progress, closed)
- ``--priority``: Filter by priority (low, medium, high, critical)
- ``-l, --limit``: Maximum number of issues to return

**Examples:**

.. code-block:: bash

   # List all issues
   issuedb-cli list

   # List open high-priority issues
   issuedb-cli list -s open --priority high

   # Get top 5 issues as JSON
   issuedb-cli --json list -l 5

get
~~~

Get details of a specific issue.

.. code-block:: bash

   issuedb-cli get ID

**Arguments:**

- ``ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli get 42
   issuedb-cli --json get 42

update
~~~~~~

Update an existing issue.

.. code-block:: bash

   issuedb-cli update ID [-t "TITLE"] [-d "DESCRIPTION"] [-s STATUS] [--priority PRIORITY]

**Arguments:**

- ``ID`` (required): Issue ID
- ``-t, --title``: New title
- ``-d, --description``: New description
- ``-s, --status``: New status (open, in-progress, closed)
- ``--priority``: New priority (low, medium, high, critical)

**Examples:**

.. code-block:: bash

   # Update status
   issuedb-cli update 1 -s in-progress

   # Update multiple fields
   issuedb-cli update 1 -t "Updated title" --priority critical -s closed

delete
~~~~~~

Delete an issue. The audit trail is preserved.

.. code-block:: bash

   issuedb-cli delete ID

**Arguments:**

- ``ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli delete 42

get-next
~~~~~~~~

Get the next issue to work on based on priority (FIFO within each priority level).

.. code-block:: bash

   issuedb-cli get-next [-s STATUS]

**Arguments:**

- ``-s, --status``: Filter by status. Default: open

**Behavior:**

- Returns the highest priority issue (critical > high > medium > low)
- Within the same priority, returns the oldest (FIFO)
- **Logs the fetch in the audit trail** with a ``FETCH`` action
- Use ``get-last`` to retrieve fetch history

**Examples:**

.. code-block:: bash

   issuedb-cli get-next
   issuedb-cli --json get-next -s in-progress

get-last
~~~~~~~~

Get the last fetched issue(s) from the fetch history.

.. code-block:: bash

   issuedb-cli get-last [-n NUMBER]

**Arguments:**

- ``-n, --number``: Number of last fetched issues to return. Default: 1

**Behavior:**

- Returns issues in reverse chronological order (most recent first)
- Shows current state of existing issues
- Reconstructs deleted issues from audit log history
- Does not return duplicates (same issue fetched multiple times counts once)

**Examples:**

.. code-block:: bash

   # Get the last issue you fetched
   issuedb-cli get-last

   # Get the last 5 fetched issues
   issuedb-cli get-last -n 5

   # JSON output for automation
   issuedb-cli --json get-last -n 3

**Use Cases:**

- Track what issues you've recently worked on
- Review fetch history when switching contexts
- Find previously fetched issue that was deleted

search
~~~~~~

Search issues by keyword in title and description.

.. code-block:: bash

   issuedb-cli search -k "KEYWORD" [-l LIMIT]

**Arguments:**

- ``-k, --keyword`` (required): Search keyword
- ``-l, --limit``: Maximum results

**Examples:**

.. code-block:: bash

   issuedb-cli search -k "login"
   issuedb-cli --json search -k "bug" -l 10

Comment Commands
----------------

comment
~~~~~~~

Add a comment to an issue.

.. code-block:: bash

   issuedb-cli comment ISSUE_ID -t "TEXT"

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID
- ``-t, --text`` (required): Comment text

**Examples:**

.. code-block:: bash

   issuedb-cli comment 1 -t "Working on this now"
   issuedb-cli --json comment 1 -t "Fixed by updating config"

list-comments
~~~~~~~~~~~~~

List all comments for an issue.

.. code-block:: bash

   issuedb-cli list-comments ISSUE_ID

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli list-comments 1
   issuedb-cli --json list-comments 1

delete-comment
~~~~~~~~~~~~~~

Delete a comment.

.. code-block:: bash

   issuedb-cli delete-comment COMMENT_ID

**Arguments:**

- ``COMMENT_ID`` (required): Comment ID

**Examples:**

.. code-block:: bash

   issuedb-cli delete-comment 5

Bulk Operations
---------------

bulk-update
~~~~~~~~~~~

Update multiple issues matching filters.

.. code-block:: bash

   issuedb-cli bulk-update [--filter-status STATUS] [--filter-priority PRIORITY] [-s STATUS] [--priority PRIORITY]

**Arguments:**

- ``--filter-status``: Filter by current status
- ``--filter-priority``: Filter by current priority
- ``-s, --status``: New status to set
- ``--priority``: New priority to set

**Examples:**

.. code-block:: bash

   # Close all issues
   issuedb-cli bulk-update -s closed

   # Close all open issues
   issuedb-cli bulk-update --filter-status open -s closed

   # Upgrade all medium priority to high
   issuedb-cli bulk-update --filter-priority medium --priority high

bulk-create
~~~~~~~~~~~

Create multiple issues from JSON input.

.. code-block:: bash

   issuedb-cli bulk-create [-f FILE] [-d DATA]

**Arguments:**

- ``-f, --file``: JSON file path
- ``-d, --data``: Inline JSON data
- If neither provided, reads from stdin

**JSON Format:**

.. code-block:: json

   [
     {"title": "Issue 1", "priority": "high", "description": "Details"},
     {"title": "Issue 2", "priority": "medium"},
     {"title": "Issue 3"}
   ]

**Examples:**

.. code-block:: bash

   # From stdin
   echo '[{"title": "Issue 1"}, {"title": "Issue 2"}]' | issuedb-cli bulk-create

   # From file
   issuedb-cli bulk-create -f issues.json

   # Inline data
   issuedb-cli bulk-create -d '[{"title": "Quick issue", "priority": "low"}]'

bulk-update-json
~~~~~~~~~~~~~~~~

Update multiple specific issues from JSON input.

.. code-block:: bash

   issuedb-cli bulk-update-json [-f FILE] [-d DATA]

**Arguments:**

- ``-f, --file``: JSON file path
- ``-d, --data``: Inline JSON data
- If neither provided, reads from stdin

**JSON Format:**

.. code-block:: json

   [
     {"id": 1, "status": "closed"},
     {"id": 2, "priority": "high", "title": "New title"},
     {"id": 3, "status": "in-progress"}
   ]

**Examples:**

.. code-block:: bash

   echo '[{"id": 1, "status": "closed"}, {"id": 2, "priority": "high"}]' | issuedb-cli bulk-update-json

bulk-close
~~~~~~~~~~

Close multiple issues by ID.

.. code-block:: bash

   issuedb-cli bulk-close [-f FILE] [-d DATA]

**Arguments:**

- ``-f, --file``: JSON file path containing array of IDs
- ``-d, --data``: Inline JSON array of IDs
- If neither provided, reads from stdin

**JSON Format:**

.. code-block:: json

   [1, 2, 3, 4, 5]

**Examples:**

.. code-block:: bash

   echo '[1, 2, 3]' | issuedb-cli bulk-close
   issuedb-cli bulk-close -d '[5, 7, 9]'

Reporting Commands
------------------

summary
~~~~~~~

Show aggregate statistics.

.. code-block:: bash

   issuedb-cli summary

**Examples:**

.. code-block:: bash

   issuedb-cli summary
   issuedb-cli --json summary

**Output includes:**

- Total issue count
- Breakdown by status (count and percentage)
- Breakdown by priority (count and percentage)

report
~~~~~~

Show detailed report of issues.

.. code-block:: bash

   issuedb-cli report [--group-by {status,priority}]

**Arguments:**

- ``--group-by``: Group by status or priority. Default: status

**Examples:**

.. code-block:: bash

   issuedb-cli report
   issuedb-cli report --group-by priority
   issuedb-cli --json report

info
~~~~

Show database information and statistics.

.. code-block:: bash

   issuedb-cli info

**Examples:**

.. code-block:: bash

   issuedb-cli info
   issuedb-cli --json info

audit
~~~~~

View audit logs.

.. code-block:: bash

   issuedb-cli audit [-i ISSUE_ID]

**Arguments:**

- ``-i, --issue-id``: Filter by issue ID

**Examples:**

.. code-block:: bash

   # All audit logs
   issuedb-cli audit

   # Logs for specific issue
   issuedb-cli audit -i 1

   # JSON output
   issuedb-cli --json audit

Dependency Commands
-------------------

block
~~~~~

Mark an issue as blocked by another issue.

.. code-block:: bash

   issuedb-cli block ISSUE_ID --by BLOCKER_ID

**Arguments:**

- ``ISSUE_ID`` (required): ID of the issue being blocked
- ``--by`` (required): ID of the blocking issue

**Examples:**

.. code-block:: bash

   issuedb-cli block 5 --by 3
   issuedb-cli --json block 5 --by 3

unblock
~~~~~~~

Remove blocker(s) from an issue.

.. code-block:: bash

   issuedb-cli unblock ISSUE_ID [--by BLOCKER_ID]

**Arguments:**

- ``ISSUE_ID`` (required): ID of the blocked issue
- ``--by``: Specific blocker to remove (if omitted, removes all blockers)

**Examples:**

.. code-block:: bash

   # Remove specific blocker
   issuedb-cli unblock 5 --by 3

   # Remove all blockers
   issuedb-cli unblock 5

deps
~~~~

Show dependency graph for an issue.

.. code-block:: bash

   issuedb-cli deps ISSUE_ID

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli deps 5
   issuedb-cli --json deps 5

blocked
~~~~~~~

List all blocked issues.

.. code-block:: bash

   issuedb-cli blocked [-s STATUS]

**Arguments:**

- ``-s, --status``: Filter by status

**Examples:**

.. code-block:: bash

   issuedb-cli blocked
   issuedb-cli --json blocked -s open

Code Reference Commands
-----------------------

attach
~~~~~~

Attach a code reference to an issue.

.. code-block:: bash

   issuedb-cli attach ISSUE_ID --file "FILE_PATH[:LINE[-END_LINE]]" [--note "NOTE"]

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID
- ``--file`` (required): File path with optional line number(s)
- ``--note``: Optional note about the reference

**Examples:**

.. code-block:: bash

   # Attach file
   issuedb-cli attach 5 --file "src/auth.py"

   # With line number
   issuedb-cli attach 5 --file "src/auth.py:42"

   # With line range
   issuedb-cli attach 5 --file "src/auth.py:42-50"

   # With note
   issuedb-cli attach 5 --file "src/auth.py:42" --note "Bug location"

detach
~~~~~~

Remove a code reference from an issue.

.. code-block:: bash

   issuedb-cli detach ISSUE_ID --file "FILE_PATH"

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID
- ``--file`` (required): File path to remove

**Examples:**

.. code-block:: bash

   issuedb-cli detach 5 --file "src/auth.py"

refs
~~~~

List code references for an issue.

.. code-block:: bash

   issuedb-cli refs ISSUE_ID

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli refs 5
   issuedb-cli --json refs 5

affected
~~~~~~~~

List issues that reference a specific file.

.. code-block:: bash

   issuedb-cli affected --file "FILE_PATH"

**Arguments:**

- ``--file`` (required): File path to search for

**Examples:**

.. code-block:: bash

   issuedb-cli affected --file "src/auth.py"
   issuedb-cli --json affected --file "config.py"

Time Tracking Commands
----------------------

timer-start
~~~~~~~~~~~

Start tracking time on an issue.

.. code-block:: bash

   issuedb-cli timer-start ISSUE_ID

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli timer-start 5

timer-stop
~~~~~~~~~~

Stop the active timer.

.. code-block:: bash

   issuedb-cli timer-stop [ISSUE_ID]

**Arguments:**

- ``ISSUE_ID``: Issue ID (optional if only one timer running)

**Examples:**

.. code-block:: bash

   issuedb-cli timer-stop
   issuedb-cli --json timer-stop 5

timer-status
~~~~~~~~~~~~

Show active timers.

.. code-block:: bash

   issuedb-cli timer-status

**Examples:**

.. code-block:: bash

   issuedb-cli timer-status
   issuedb-cli --json timer-status

set-estimate
~~~~~~~~~~~~

Set time estimate for an issue.

.. code-block:: bash

   issuedb-cli set-estimate ISSUE_ID --hours HOURS

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID
- ``--hours`` (required): Estimated hours

**Examples:**

.. code-block:: bash

   issuedb-cli set-estimate 5 --hours 4

time-log
~~~~~~~~

View time entries for an issue.

.. code-block:: bash

   issuedb-cli time-log ISSUE_ID

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli time-log 5
   issuedb-cli --json time-log 5

time-report
~~~~~~~~~~~

Generate time reports.

.. code-block:: bash

   issuedb-cli time-report [--period {all,week,month}] [--issue ISSUE_ID]

**Arguments:**

- ``--period``: Report period (all, week, month). Default: all
- ``--issue``: Filter by issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli time-report
   issuedb-cli time-report --period week
   issuedb-cli --json time-report --period month

Workspace Commands
------------------

workspace
~~~~~~~~~

Show workspace status.

.. code-block:: bash

   issuedb-cli workspace

**Examples:**

.. code-block:: bash

   issuedb-cli workspace
   issuedb-cli --json workspace

start
~~~~~

Start working on an issue (sets active and starts timer).

.. code-block:: bash

   issuedb-cli start ISSUE_ID

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID

**Examples:**

.. code-block:: bash

   issuedb-cli start 5
   issuedb-cli --json start 5

stop
~~~~

Stop working on active issue.

.. code-block:: bash

   issuedb-cli stop [--close]

**Arguments:**

- ``--close``: Also close the issue

**Examples:**

.. code-block:: bash

   issuedb-cli stop
   issuedb-cli stop --close
   issuedb-cli --json stop

active
~~~~~~

Show currently active issue.

.. code-block:: bash

   issuedb-cli active

**Examples:**

.. code-block:: bash

   issuedb-cli active
   issuedb-cli --json active

context
~~~~~~~

Get comprehensive context for an issue (for LLM agents).

.. code-block:: bash

   issuedb-cli context ISSUE_ID [--compact]

**Arguments:**

- ``ISSUE_ID`` (required): Issue ID
- ``--compact``: Return minimal context

**Output includes:**

- Issue details
- Comments
- Recent audit history
- Related issues
- Git information
- Suggested actions

**Examples:**

.. code-block:: bash

   issuedb-cli context 5
   issuedb-cli --json context 5
   issuedb-cli context 5 --compact

Duplicate Detection Commands
----------------------------

find-similar
~~~~~~~~~~~~

Find issues similar to given text.

.. code-block:: bash

   issuedb-cli find-similar "QUERY" [--threshold THRESHOLD] [--limit LIMIT]

**Arguments:**

- ``QUERY`` (required): Text to search for
- ``--threshold``: Similarity threshold 0.0-1.0. Default: 0.6
- ``--limit``: Maximum results. Default: 10

**Examples:**

.. code-block:: bash

   issuedb-cli find-similar "login bug"
   issuedb-cli --json find-similar "authentication" --threshold 0.7

find-duplicates
~~~~~~~~~~~~~~~

Find potential duplicate groups in database.

.. code-block:: bash

   issuedb-cli find-duplicates [--threshold THRESHOLD]

**Arguments:**

- ``--threshold``: Similarity threshold. Default: 0.7

**Examples:**

.. code-block:: bash

   issuedb-cli find-duplicates
   issuedb-cli --json find-duplicates --threshold 0.8

Template Commands
-----------------

templates
~~~~~~~~~

List available issue templates.

.. code-block:: bash

   issuedb-cli templates

**Examples:**

.. code-block:: bash

   issuedb-cli templates
   issuedb-cli --json templates

**Creating from templates:**

.. code-block:: bash

   issuedb-cli create --template bug -t "Login crash" -d "App crashes"
   issuedb-cli create --template feature -t "Dark mode"
   issuedb-cli create --template task -t "Update deps"

Bulk Pattern Commands
---------------------

bulk-close-pattern
~~~~~~~~~~~~~~~~~~

Close issues matching a pattern.

.. code-block:: bash

   issuedb-cli bulk-close-pattern --title "PATTERN" [--desc "PATTERN"] [--regex] [--dry-run]

**Arguments:**

- ``--title``: Pattern to match against title
- ``--desc``: Pattern to match against description
- ``--regex``: Treat patterns as regex (default: glob)
- ``--dry-run``: Preview without making changes

**Examples:**

.. code-block:: bash

   issuedb-cli bulk-close-pattern --title "*test*"
   issuedb-cli bulk-close-pattern --title "temp.*" --regex
   issuedb-cli bulk-close-pattern --title "*WIP*" --dry-run

bulk-update-pattern
~~~~~~~~~~~~~~~~~~~

Update issues matching a pattern.

.. code-block:: bash

   issuedb-cli bulk-update-pattern --title "PATTERN" [-s STATUS] [--priority PRIORITY] [--regex] [--dry-run]

**Arguments:**

- ``--title``: Pattern to match against title
- ``--desc``: Pattern to match against description
- ``-s, --status``: New status
- ``--priority``: New priority
- ``--regex``: Treat patterns as regex
- ``--dry-run``: Preview without making changes

**Examples:**

.. code-block:: bash

   issuedb-cli bulk-update-pattern --title "*bug*" --priority high
   issuedb-cli bulk-update-pattern --title ".*urgent.*" --regex -s in-progress

bulk-delete-pattern
~~~~~~~~~~~~~~~~~~~

Delete issues matching a pattern.

.. code-block:: bash

   issuedb-cli bulk-delete-pattern --title "PATTERN" --confirm [--regex] [--dry-run]

**Arguments:**

- ``--title``: Pattern to match against title
- ``--desc``: Pattern to match against description
- ``--confirm``: Required unless using --dry-run
- ``--regex``: Treat patterns as regex
- ``--dry-run``: Preview without making changes

**Examples:**

.. code-block:: bash

   issuedb-cli bulk-delete-pattern --title "*temp*" --confirm
   issuedb-cli bulk-delete-pattern --title "test.*" --regex --dry-run

Administrative Commands
-----------------------

clear
~~~~~

Clear all issues from the database. Requires confirmation.

.. code-block:: bash

   issuedb-cli clear --confirm

**Arguments:**

- ``--confirm`` (required): Safety flag to prevent accidental deletion

.. warning::

   This permanently deletes all issues. The audit log is preserved.

**Examples:**

.. code-block:: bash

   issuedb-cli clear --confirm

Exit Codes
----------

IssueDB uses the following exit codes:

- ``0``: Success
- ``1``: Error (invalid arguments, issue not found, etc.)

Errors are printed to stderr, and successful output is printed to stdout.
