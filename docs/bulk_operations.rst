Bulk Operations
===============

IssueDB provides powerful bulk operations for managing multiple issues at once. This is especially useful for automation, CI/CD pipelines, and LLM agents.

Overview
--------

There are four bulk operation commands:

1. **bulk-update**: Update all issues matching filters
2. **bulk-create**: Create multiple issues from JSON
3. **bulk-update-json**: Update specific issues by ID from JSON
4. **bulk-close**: Close multiple issues by ID

All bulk operations:

- Support JSON input (stdin, file, or inline)
- Provide JSON output with ``--json`` flag
- Are fully transactional (all or nothing)
- Generate audit log entries

Bulk Update (Filter-Based)
--------------------------

Update multiple issues that match certain criteria.

**Syntax:**

.. code-block:: bash

   issuedb-cli bulk-update [--filter-status STATUS] [--filter-priority PRIORITY] [-s STATUS] [--priority PRIORITY]

**Examples:**

Close all issues:

.. code-block:: bash

   issuedb-cli bulk-update -s closed

Close all open issues:

.. code-block:: bash

   issuedb-cli bulk-update --filter-status open -s closed

Upgrade all medium-priority issues to high:

.. code-block:: bash

   issuedb-cli bulk-update --filter-priority medium --priority high

Close all critical issues:

.. code-block:: bash

   issuedb-cli bulk-update --filter-priority critical -s closed

Bulk Create
-----------

Create multiple issues from JSON input.

**Input Formats:**

1. **Stdin**: Pipe JSON to the command
2. **File**: Use ``-f`` or ``--file`` flag
3. **Inline**: Use ``-d`` or ``--data`` flag

**JSON Format:**

.. code-block:: json

   [
     {
       "title": "Issue 1",
       "description": "Description here",
       "priority": "high",
       "status": "open"
     },
     {
       "title": "Issue 2",
       "priority": "medium"
     },
     {
       "title": "Issue 3"
     }
   ]

Only ``title`` is required. Other fields default to:

- ``priority``: medium
- ``status``: open
- ``description``: null

**Examples:**

From stdin:

.. code-block:: bash

   echo '[
     {"title": "Set up CI/CD", "priority": "high"},
     {"title": "Write documentation", "priority": "medium"},
     {"title": "Add unit tests", "priority": "high"}
   ]' | issuedb-cli --json bulk-create

From file:

.. code-block:: bash

   # Create a file with issues
   cat > issues.json << 'EOF'
   [
     {"title": "Issue 1", "priority": "critical", "description": "Urgent fix needed"},
     {"title": "Issue 2", "priority": "high"},
     {"title": "Issue 3", "priority": "low"}
   ]
   EOF

   # Import the issues
   issuedb-cli --json bulk-create -f issues.json

Inline data:

.. code-block:: bash

   issuedb-cli --json bulk-create -d '[{"title": "Quick issue", "priority": "low"}]'

**Output:**

.. code-block:: text

   {
     "message": "Created 3 issue(s)",
     "count": 3,
     "issues": [
       {
         "id": 1,
         "title": "Set up CI/CD",
         "priority": "high",
         "status": "open",
         ...
       },
       ...
     ]
   }

Bulk Update (JSON)
------------------

Update specific issues by ID with different changes for each.

**JSON Format:**

.. code-block:: json

   [
     {"id": 1, "status": "closed", "description": "Updated description"},
     {"id": 2, "priority": "critical"},
     {"id": 3, "title": "New title", "status": "in-progress"}
   ]

Each object must have an ``id`` field plus at least one field to update.

**Examples:**

Close multiple specific issues with different updates:

.. code-block:: bash

   echo '[
     {"id": 1, "status": "closed"},
     {"id": 2, "status": "closed"},
     {"id": 5, "status": "closed"}
   ]' | issuedb-cli --json bulk-update-json

Mixed updates:

.. code-block:: bash

   echo '[
     {"id": 1, "priority": "critical", "status": "in-progress"},
     {"id": 2, "title": "Updated: Fix login bug"},
     {"id": 3, "description": "Additional context added"}
   ]' | issuedb-cli --json bulk-update-json

Bulk Close
----------

Simple way to close multiple issues by their IDs.

**JSON Format:**

.. code-block:: json

   [1, 2, 3, 5, 7]

Just an array of issue IDs.

**Examples:**

From stdin:

.. code-block:: bash

   echo '[1, 2, 3]' | issuedb-cli --json bulk-close

Inline:

.. code-block:: bash

   issuedb-cli --json bulk-close -d '[5, 7, 9, 12]'

From file:

.. code-block:: bash

   echo '[10, 11, 12, 13, 14]' > close-these.json
   issuedb-cli --json bulk-close -f close-these.json

**Output:**

.. code-block:: text

   {
     "message": "Closed 5 issue(s)",
     "count": 5,
     "issues": [
       {"id": 10, "title": "...", "status": "closed", ...},
       ...
     ]
   }

Error Handling
--------------

Bulk operations are transactional. If any operation fails:

1. The entire batch is rolled back
2. An error message is displayed
3. No partial changes are made

**Common errors:**

- Issue not found (for update/close operations)
- Missing required fields (like title for create)
- Invalid JSON format
- Invalid field values (like unknown priority)

**Example error:**

.. code-block:: bash

   $ echo '[{"id": 999, "status": "closed"}]' | issuedb-cli bulk-update-json
   Error: Issue 999 not found

Use Cases
---------

Sprint Cleanup
~~~~~~~~~~~~~~

Close all completed issues at the end of a sprint:

.. code-block:: bash

   # Get IDs of issues to close
   ISSUE_IDS=$(issuedb-cli --json list -s in-progress | jq '[.[].id]')

   # Close them all
   echo "$ISSUE_IDS" | issuedb-cli --json bulk-close

Import from External System
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Import issues from another system:

.. code-block:: bash

   # Export from external system to JSON
   external-tool export --format json > external-issues.json

   # Transform to IssueDB format (example with jq)
   cat external-issues.json | jq '[.[] | {title: .name, description: .body, priority: .severity}]' > issues.json

   # Import
   issuedb-cli --json bulk-create -f issues.json

CI/CD Integration
~~~~~~~~~~~~~~~~~

Create issues for failing tests:

.. code-block:: bash

   # Run tests and capture failures
   pytest --json-report --json-report-file=test-results.json || true

   # Create issues for failures
   cat test-results.json | jq '[.tests[] | select(.outcome == "failed") | {title: ("Test failure: " + .nodeid), priority: "high", description: .longrepr}]' | issuedb-cli --json bulk-create

Scheduled Maintenance
~~~~~~~~~~~~~~~~~~~~~

Create recurring maintenance issues:

.. code-block:: bash

   # weekly-maintenance.json
   [
     {"title": "Weekly backup verification", "priority": "medium"},
     {"title": "Review error logs", "priority": "low"},
     {"title": "Update dependencies", "priority": "medium"}
   ]

   # Cron job or scheduled task
   issuedb-cli --json bulk-create -f weekly-maintenance.json

Performance
-----------

Bulk operations are optimized for efficiency:

- All operations run in a single database transaction
- Minimal overhead compared to individual commands
- Audit logging is batched where possible

For very large batches (thousands of issues), consider splitting into smaller chunks.
