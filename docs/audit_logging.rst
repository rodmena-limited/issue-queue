Audit Logging
=============

IssueDB maintains a complete, immutable audit trail of all changes made to issues. This enables full traceability and accountability.

Overview
--------

Every operation that modifies data is logged:

- Issue creation
- Issue updates (each field change)
- Issue deletion
- Bulk operations
- Issue fetches (via ``get-next``)

Audit logs are:

- **Immutable**: Once written, logs cannot be modified or deleted
- **Complete**: Every change is recorded with before/after values
- **Timestamped**: Each entry includes when the change occurred
- **Preserved**: Logs persist even when issues are deleted

Viewing Audit Logs
------------------

View all audit logs:

.. code-block:: bash

   issuedb-cli audit

View logs for a specific issue:

.. code-block:: bash

   issuedb-cli audit -i ISSUE_ID

JSON output:

.. code-block:: bash

   issuedb-cli --json audit
   issuedb-cli --json audit -i 1

Audit Log Structure
-------------------

Each audit log entry contains:

- ``id``: Unique log entry ID
- ``issue_id``: The issue that was modified
- ``action``: Type of action (CREATE, UPDATE, DELETE, FETCH, BULK_CREATE, BULK_UPDATE)
- ``field_name``: Which field was changed (for updates)
- ``old_value``: Previous value (for updates/deletes)
- ``new_value``: New value (for creates/updates)
- ``timestamp``: When the change occurred

**Example JSON output:**

.. code-block:: json

   [
     {
       "id": 1,
       "issue_id": 1,
       "action": "CREATE",
       "field_name": null,
       "old_value": null,
       "new_value": "{\"id\": 1, \"title\": \"Fix bug\", ...}",
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
     },
     {
       "id": 3,
       "issue_id": 1,
       "action": "UPDATE",
       "field_name": "status",
       "old_value": "in-progress",
       "new_value": "closed",
       "timestamp": "2025-01-15T14:30:00"
     }
   ]

Action Types
------------

CREATE
~~~~~~

Logged when a new issue is created. The ``new_value`` contains the full issue data as JSON.

UPDATE
~~~~~~

Logged for each field that changes during an update. Individual entries are created for each field.

DELETE
~~~~~~

Logged when an issue is deleted. The ``old_value`` contains the full issue data as JSON, preserving the issue's state at deletion time.

FETCH
~~~~~

Logged when an issue is retrieved via ``get-next``. The ``new_value`` contains the full issue data as JSON at the time of fetch. This enables tracking which issues were fetched and when, accessible via the ``get-last`` command.

BULK_CREATE
~~~~~~~~~~~

Logged for issues created via ``bulk-create``. Similar to CREATE but indicates bulk operation.

BULK_UPDATE
~~~~~~~~~~~

Logged for issues updated via ``bulk-update``. Each affected issue and field gets its own entry.

Use Cases
---------

Compliance and Auditing
~~~~~~~~~~~~~~~~~~~~~~~

Track who changed what and when:

.. code-block:: bash

   # Export full audit trail
   issuedb-cli --json audit > audit-trail.json

   # Analyze changes to critical issues
   issuedb-cli --json audit -i 42 | jq '.[] | select(.action == "UPDATE")'

Debugging
~~~~~~~~~

Understand how an issue evolved:

.. code-block:: bash

   # See all changes to issue #1
   issuedb-cli audit -i 1

Recovering Deleted Issues
~~~~~~~~~~~~~~~~~~~~~~~~~

Find details of deleted issues:

.. code-block:: bash

   # Find DELETE actions
   issuedb-cli --json audit | jq '.[] | select(.action == "DELETE")'

   # Get the old_value which contains the full issue data
   issuedb-cli --json audit | jq '.[] | select(.action == "DELETE") | .old_value | fromjson'

Change Frequency Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~

Analyze how often issues change:

.. code-block:: bash

   # Count changes per issue
   issuedb-cli --json audit | jq 'group_by(.issue_id) | map({issue_id: .[0].issue_id, changes: length})'

Tracking Fetch History
~~~~~~~~~~~~~~~~~~~~~~

Review which issues were fetched via ``get-next``:

.. code-block:: bash

   # Get last fetched issue
   issuedb-cli get-last

   # Get last 5 fetched issues
   issuedb-cli --json get-last -n 5

   # See all FETCH actions in audit log
   issuedb-cli --json audit | jq '.[] | select(.action == "FETCH")'

Database Storage
----------------

Audit logs are stored in the ``audit_logs`` table in the same SQLite database as issues. The table is indexed for efficient querying.

.. note::

   Audit logs grow over time. For very active databases, consider periodic export and archival of old logs.

Best Practices
--------------

1. **Regular exports**: Periodically export audit logs for backup and compliance
2. **Monitor growth**: Watch audit log size in long-running projects
3. **Include in backups**: Always backup the full database including audit logs
4. **Use JSON output**: For analysis and integration, use ``--json`` flag

Limitations
-----------

- Audit logs do not track who made changes (no user authentication)
- Logs are stored locally, not synced across machines
- No built-in log rotation or archival

For enterprise-grade auditing needs, consider integrating IssueDB with external logging systems.
