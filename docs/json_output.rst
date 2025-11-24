JSON Output
===========

IssueDB provides comprehensive JSON output support for all commands, making it easy to integrate with scripts, automation tools, and other programs.

Enabling JSON Output
--------------------

Add the ``--json`` flag before the command:

.. code-block:: bash

   issuedb-cli --json COMMAND [ARGS]

**Examples:**

.. code-block:: bash

   issuedb-cli --json list
   issuedb-cli --json get 1
   issuedb-cli --json summary
   issuedb-cli --json create -t "New issue"

Output Formats
--------------

Issues
~~~~~~

Single issue:

.. code-block:: json

   {
     "id": 1,
     "title": "Fix login bug",
     "description": "Users cannot log in with special characters",
     "priority": "high",
     "status": "open",
     "created_at": "2025-01-15T10:30:00.123456",
     "updated_at": "2025-01-15T10:30:00.123456"
   }

Issue list:

.. code-block:: text

   [
     {
       "id": 1,
       "title": "Fix login bug",
       "priority": "high",
       "status": "open",
       ...
     },
     {
       "id": 2,
       "title": "Add dark mode",
       "priority": "medium",
       "status": "in-progress",
       ...
     }
   ]

Comments
~~~~~~~~

Single comment:

.. code-block:: json

   {
     "id": 1,
     "issue_id": 1,
     "text": "Started working on this",
     "created_at": "2025-01-15T11:00:00.123456"
   }

Comment list:

.. code-block:: json

   [
     {
       "id": 1,
       "issue_id": 1,
       "text": "Started working on this",
       "created_at": "2025-01-15T11:00:00.123456"
     },
     {
       "id": 2,
       "issue_id": 1,
       "text": "Found the root cause",
       "created_at": "2025-01-15T12:30:00.123456"
     }
   ]

Summary
~~~~~~~

.. code-block:: json

   {
     "total_issues": 10,
     "by_status": {
       "open": {"count": 5, "percentage": 50.0},
       "in_progress": {"count": 3, "percentage": 30.0},
       "closed": {"count": 2, "percentage": 20.0}
     },
     "by_priority": {
       "critical": {"count": 1, "percentage": 10.0},
       "high": {"count": 3, "percentage": 30.0},
       "medium": {"count": 4, "percentage": 40.0},
       "low": {"count": 2, "percentage": 20.0}
     }
   }

Report
~~~~~~

.. code-block:: text

   {
     "group_by": "status",
     "total_issues": 10,
     "groups": {
       "open": {
         "count": 5,
         "issues": [...]
       },
       "in_progress": {
         "count": 3,
         "issues": [...]
       },
       "closed": {
         "count": 2,
         "issues": [...]
       }
     }
   }

Audit Logs
~~~~~~~~~~

.. code-block:: json

   [
     {
       "id": 1,
       "issue_id": 1,
       "action": "CREATE",
       "field_name": null,
       "old_value": null,
       "new_value": "{...}",
       "timestamp": "2025-01-15T10:30:00"
     },
     {
       "id": 2,
       "issue_id": 1,
       "action": "UPDATE",
       "field_name": "status",
       "old_value": "open",
       "new_value": "in-progress",
       "timestamp": "2025-01-15T11:00:00"
     }
   ]

Bulk Operation Results
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   {
     "message": "Created 3 issue(s)",
     "count": 3,
     "issues": [
       {"id": 1, "title": "Issue 1", ...},
       {"id": 2, "title": "Issue 2", ...},
       {"id": 3, "title": "Issue 3", ...}
     ]
   }

Database Info
~~~~~~~~~~~~~

.. code-block:: json

   {
     "database_path": "/path/to/issuedb.sqlite",
     "total_issues": 25,
     "total_audit_logs": 150,
     "database_size_bytes": 45056
   }

Working with JSON
-----------------

Using jq
~~~~~~~~

`jq <https://stedolan.github.io/jq/>`_ is a powerful command-line JSON processor:

.. code-block:: bash

   # Get issue titles
   issuedb-cli --json list | jq '.[].title'

   # Filter by status
   issuedb-cli --json list | jq '[.[] | select(.status == "open")]'

   # Get count of high priority issues
   issuedb-cli --json list | jq '[.[] | select(.priority == "high")] | length'

   # Extract IDs
   issuedb-cli --json list -s open | jq '[.[].id]'

Using Python
~~~~~~~~~~~~

.. code-block:: python

   import json
   import subprocess

   # Run command
   result = subprocess.run(
       ['issuedb-cli', '--json', 'list', '-s', 'open'],
       capture_output=True,
       text=True
   )

   # Parse JSON
   issues = json.loads(result.stdout)

   # Process
   for issue in issues:
       print(f"#{issue['id']}: {issue['title']}")

Using Node.js
~~~~~~~~~~~~~

.. code-block:: javascript

   const { execSync } = require('child_process');

   // Run command
   const output = execSync('issuedb-cli --json list').toString();

   // Parse JSON
   const issues = JSON.parse(output);

   // Process
   issues.forEach(issue => {
       console.log(`#${issue.id}: ${issue.title}`);
   });

Using Bash
~~~~~~~~~~

.. code-block:: bash

   # Read into variable
   ISSUES=$(issuedb-cli --json list)

   # Use with other tools
   echo "$ISSUES" | python -c "import sys, json; print(len(json.load(sys.stdin)))"

   # Loop through (requires jq)
   issuedb-cli --json list | jq -c '.[]' | while read -r issue; do
       ID=$(echo "$issue" | jq -r '.id')
       TITLE=$(echo "$issue" | jq -r '.title')
       echo "Processing issue #$ID: $TITLE"
   done

Error Handling
--------------

When an error occurs:

- Exit code is non-zero (1)
- Error message goes to stderr
- stdout is empty or contains partial output

.. code-block:: bash

   # Check for errors
   if OUTPUT=$(issuedb-cli --json get 999 2>&1); then
       echo "Success: $OUTPUT"
   else
       echo "Error: $OUTPUT"
   fi

Best Practices
--------------

1. **Always check exit codes**: Don't assume success
2. **Redirect stderr**: Capture errors separately from JSON output
3. **Validate JSON**: Handle malformed JSON gracefully
4. **Use proper parsing**: Don't use string manipulation for JSON
5. **Handle empty results**: Lists may be empty arrays ``[]``

DateTime Format
---------------

All timestamps are in ISO 8601 format:

.. code-block:: text

   YYYY-MM-DDTHH:MM:SS.microseconds

Example: ``2025-01-15T10:30:00.123456``

This format is:

- Sortable as strings
- Parseable by most programming languages
- Unambiguous (always local time)
