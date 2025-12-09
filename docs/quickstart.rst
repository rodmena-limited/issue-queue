Quickstart Guide
================

This guide will get you up and running with IssueDB in just a few minutes. We'll cover the basics of creating issues, managing them, and using key features.

Your First Issue
----------------

Navigate to your project directory and create your first issue:

.. code-block:: bash

   cd ~/my-project
   issuedb-cli create --title "Fix login bug" --description "Users cannot log in with special characters" --priority high

You'll see output like:

.. code-block:: text

   ID: 1
   Title: Fix login bug
   Status: open
   Priority: high
   Description: Users cannot log in with special characters
   Created: 2025-01-15 10:30:00
   Updated: 2025-01-15 10:30:00

Listing Issues
--------------

View all issues in your project:

.. code-block:: bash

   # List all issues
   issuedb-cli list

   # List only open issues
   issuedb-cli list --status open

   # List high priority issues
   issuedb-cli list --priority high

   # Combine filters
   issuedb-cli list --status open --priority critical

Working on Issues
-----------------

Update an issue's status as you work on it:

.. code-block:: bash

   # Mark issue #1 as in-progress
   issuedb-cli update 1 --status in-progress

   # Add a comment about what you're doing
   issuedb-cli comment 1 -t "Investigating the character encoding issue"

Getting the Next Issue
----------------------

Get the next issue to work on (highest priority, oldest first):

.. code-block:: bash

   issuedb-cli get-next

This follows FIFO ordering within each priority level, so critical issues are returned before high priority ones, etc.

Adding Comments
---------------

Add comments to track progress, notes, or resolution details:

.. code-block:: bash

   # Add a comment
   issuedb-cli comment 1 -t "Found the issue - special chars not being escaped"

   # View all comments on an issue
   issuedb-cli list-comments 1

   # Get comments in JSON format
   issuedb-cli --json list-comments 1

Closing Issues
--------------

When you're done with an issue, close it with a resolution comment:

.. code-block:: bash

   # Close the issue
   issuedb-cli update 1 --status closed

   # Add a resolution comment
   issuedb-cli comment 1 -t "Fixed: Added proper escaping for special characters in login form"

Or do both in one line:

.. code-block:: bash

   issuedb-cli update 1 -s closed && issuedb-cli comment 1 -t "Resolved: Updated auth library to v2.0"

Marking Issues as Won't Do
---------------------------

For issues that you decide not to implement, use the ``wont-do`` status:

.. code-block:: bash

   # Mark as won't do
   issuedb-cli update 1 --status wont-do

   # Add an explanation comment
   issuedb-cli comment 1 -t "Won't implement: Out of scope for current project goals"

Searching Issues
----------------

Find issues by keyword:

.. code-block:: bash

   # Search for issues containing "login"
   issuedb-cli search -k "login"

   # Limit results
   issuedb-cli search -k "bug" -l 5

JSON Output
-----------

All commands support JSON output for scripting and automation:

.. code-block:: bash

   # List issues as JSON
   issuedb-cli --json list

   # Get issue details as JSON
   issuedb-cli --json get 1

   # Summary statistics as JSON
   issuedb-cli --json summary

Example JSON output:

.. code-block:: json

   [
     {
       "id": 1,
       "title": "Fix login bug",
       "description": "Users cannot log in with special characters",
       "priority": "high",
       "status": "closed",
       "created_at": "2025-01-15T10:30:00",
       "updated_at": "2025-01-15T14:45:00"
     }
   ]

Viewing Statistics
------------------

Get a summary of your issues:

.. code-block:: bash

   # Quick summary
   issuedb-cli summary

   # Detailed report grouped by status
   issuedb-cli report

   # Group by priority instead
   issuedb-cli report --group-by priority

Audit Trail
-----------

View the complete history of changes:

.. code-block:: bash

   # View all audit logs
   issuedb-cli audit

   # View logs for a specific issue
   issuedb-cli audit -i 1

Deleting Issues
---------------

Delete an issue (the audit trail is preserved):

.. code-block:: bash

   issuedb-cli delete 1

Clearing All Issues
-------------------

To clear all issues (requires confirmation):

.. code-block:: bash

   issuedb-cli clear --confirm

.. warning::

   This permanently deletes all issues in the current database. The audit log is preserved for traceability.

Complete Workflow Example
-------------------------

Here's a typical workflow from start to finish:

.. code-block:: bash

   # Create a new project and navigate to it
   mkdir my-awesome-project
   cd my-awesome-project

   # Create some issues
   issuedb-cli create -t "Set up project structure" --priority high
   issuedb-cli create -t "Implement user authentication" --priority critical
   issuedb-cli create -t "Add unit tests" --priority medium
   issuedb-cli create -t "Write documentation" --priority low

   # View all issues
   issuedb-cli list

   # Get the next issue to work on (will be the critical one)
   issuedb-cli get-next

   # Start working on it
   issuedb-cli update 2 -s in-progress
   issuedb-cli comment 2 -t "Starting OAuth2 implementation"

   # Complete it
   issuedb-cli update 2 -s closed
   issuedb-cli comment 2 -t "OAuth2 implemented with Google and GitHub providers"

   # Check summary
   issuedb-cli summary

   # Get the next issue
   issuedb-cli get-next

What's Next?
------------

Now that you've completed the quickstart, you can:

- Read the :doc:`cli_reference` for all available commands and options
- Learn about :doc:`comments` for tracking issue progress
- Explore :doc:`bulk_operations` for managing multiple issues at once
- Set up :doc:`llm_agents` for AI-powered issue management
- Check out :doc:`automation` for CI/CD integration
