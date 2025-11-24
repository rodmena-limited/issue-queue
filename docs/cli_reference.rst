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

**Examples:**

.. code-block:: bash

   issuedb-cli get-next
   issuedb-cli --json get-next -s in-progress

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
