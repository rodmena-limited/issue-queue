Comments
========

IssueDB supports adding comments to issues, allowing you to track notes, progress updates, and resolution details throughout an issue's lifecycle.

Overview
--------

Comments are a simple but powerful way to:

- Document your progress while working on an issue
- Explain why an issue was closed or reopened
- Add notes for future reference
- Communicate with team members about an issue

Each comment is associated with a specific issue and includes:

- Unique comment ID
- The text content
- Creation timestamp

Adding Comments
---------------

Use the ``comment`` command to add a comment to an issue:

.. code-block:: bash

   issuedb-cli comment ISSUE_ID -t "Your comment text"

**Examples:**

.. code-block:: bash

   # Add a simple comment
   issuedb-cli comment 1 -t "Started investigating this issue"

   # Add a detailed comment
   issuedb-cli comment 1 -t "Found the root cause: the config file was missing a required field"

   # Add with JSON output to get the comment details
   issuedb-cli --json comment 1 -t "Testing the fix"

The JSON output includes the comment ID and timestamp:

.. code-block:: json

   {
     "id": 1,
     "issue_id": 1,
     "text": "Testing the fix",
     "created_at": "2025-01-15T10:30:00"
   }

Viewing Comments
----------------

List all comments for an issue:

.. code-block:: bash

   issuedb-cli list-comments ISSUE_ID

**Example output:**

.. code-block:: text

   --------------------------------------------------
   Comment ID: 1
   Created: 2025-01-15 10:30:00
   Text: Started investigating this issue
   --------------------------------------------------
   Comment ID: 2
   Created: 2025-01-15 11:45:00
   Text: Found the root cause: the config file was missing a required field
   --------------------------------------------------
   Comment ID: 3
   Created: 2025-01-15 14:20:00
   Text: Fix implemented and tested

**JSON output:**

.. code-block:: bash

   issuedb-cli --json list-comments 1

.. code-block:: json

   [
     {
       "id": 1,
       "issue_id": 1,
       "text": "Started investigating this issue",
       "created_at": "2025-01-15T10:30:00"
     },
     {
       "id": 2,
       "issue_id": 1,
       "text": "Found the root cause: the config file was missing a required field",
       "created_at": "2025-01-15T11:45:00"
     }
   ]

Deleting Comments
-----------------

Remove a comment by its ID:

.. code-block:: bash

   issuedb-cli delete-comment COMMENT_ID

**Example:**

.. code-block:: bash

   issuedb-cli delete-comment 2

Common Patterns
---------------

Closing with Resolution Comment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A common pattern is to close an issue and add a resolution comment:

.. code-block:: bash

   issuedb-cli update 1 -s closed && issuedb-cli comment 1 -t "Resolved: Updated the authentication library to v2.0"

Progress Tracking
~~~~~~~~~~~~~~~~~

Track your progress through comments:

.. code-block:: bash

   # Starting work
   issuedb-cli update 1 -s in-progress
   issuedb-cli comment 1 -t "Starting work on this issue"

   # Making progress
   issuedb-cli comment 1 -t "Completed initial investigation, root cause identified"

   # More progress
   issuedb-cli comment 1 -t "Fix implemented, running tests"

   # Completing
   issuedb-cli update 1 -s closed
   issuedb-cli comment 1 -t "All tests passing, fix deployed to production"

Reopening Issues
~~~~~~~~~~~~~~~~

When reopening a closed issue, add a comment explaining why:

.. code-block:: bash

   issuedb-cli update 1 -s open
   issuedb-cli comment 1 -t "Reopening: Bug reappeared after last deployment"

Blocking Notes
~~~~~~~~~~~~~~

Document why an issue is blocked:

.. code-block:: bash

   issuedb-cli comment 1 -t "BLOCKED: Waiting for API documentation from vendor"

Comments and Issue Deletion
---------------------------

When an issue is deleted, all its comments are automatically deleted as well (cascade delete). The audit log preserves a record of the deletion.

Best Practices
--------------

1. **Be descriptive**: Write comments that will make sense to you (or others) weeks later
2. **Add resolution comments**: Always explain why an issue was closed
3. **Document blockers**: Note when and why an issue is blocked
4. **Use timestamps implicitly**: IssueDB automatically timestamps comments, so focus on the content
5. **Keep comments focused**: Each comment should cover one topic or update

API Reference
-------------

For programmatic access, see the :doc:`api/repository` documentation for the ``add_comment()``, ``get_comments()``, and ``delete_comment()`` methods.
