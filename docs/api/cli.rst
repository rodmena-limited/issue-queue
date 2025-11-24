CLI API
=======

The CLI module provides both the command-line interface and a Python API for programmatic access.

.. module:: issuedb.cli

CLI Class
---------

.. py:class:: CLI(db_path: Optional[str] = None)

   Command-line interface for IssueDB.

   :param db_path: Optional path to database file

   **Example:**

   .. code-block:: python

      from issuedb.cli import CLI

      cli = CLI()  # Use default database
      cli = CLI("/path/to/custom.db")  # Use custom database

Issue Methods
~~~~~~~~~~~~~

.. py:method:: CLI.create_issue(title: str, description: Optional[str] = None, priority: str = "medium", status: str = "open", as_json: bool = False) -> str

   Create a new issue.

   :param title: Issue title
   :param description: Issue description
   :param priority: Priority level
   :param status: Initial status
   :param as_json: Return JSON output
   :returns: Formatted output string

   **Example:**

   .. code-block:: python

      output = cli.create_issue(
          "Fix bug",
          description="Details here",
          priority="high"
      )
      print(output)

      # JSON output
      json_output = cli.create_issue("Fix bug", as_json=True)

.. py:method:: CLI.list_issues(status: Optional[str] = None, priority: Optional[str] = None, limit: Optional[int] = None, as_json: bool = False) -> str

   List issues with optional filters.

   :param status: Filter by status
   :param priority: Filter by priority
   :param limit: Maximum results
   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.get_issue(issue_id: int, as_json: bool = False) -> str

   Get details of a specific issue.

   :param issue_id: Issue ID
   :param as_json: Return JSON output
   :returns: Formatted output string
   :raises ValueError: If issue not found

.. py:method:: CLI.update_issue(issue_id: int, as_json: bool = False, **updates) -> str

   Update an issue.

   :param issue_id: Issue ID
   :param as_json: Return JSON output
   :param updates: Fields to update
   :returns: Formatted output string
   :raises ValueError: If issue not found

   **Example:**

   .. code-block:: python

      cli.update_issue(1, status="closed", priority="low")

.. py:method:: CLI.delete_issue(issue_id: int, as_json: bool = False) -> str

   Delete an issue.

   :param issue_id: Issue ID
   :param as_json: Return JSON output
   :returns: Formatted output string
   :raises ValueError: If issue not found

.. py:method:: CLI.get_next_issue(status: str = "open", as_json: bool = False) -> str

   Get the next issue to work on.

   :param status: Status filter
   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.search_issues(keyword: str, limit: Optional[int] = None, as_json: bool = False) -> str

   Search issues by keyword.

   :param keyword: Search keyword
   :param limit: Maximum results
   :param as_json: Return JSON output
   :returns: Formatted output string

Comment Methods
~~~~~~~~~~~~~~~

.. py:method:: CLI.add_comment(issue_id: int, text: str, as_json: bool = False) -> str

   Add a comment to an issue.

   :param issue_id: Issue ID
   :param text: Comment text
   :param as_json: Return JSON output
   :returns: Formatted output string
   :raises ValueError: If issue not found or text empty

   **Example:**

   .. code-block:: python

      cli.add_comment(1, "Working on this now")

.. py:method:: CLI.list_comments(issue_id: int, as_json: bool = False) -> str

   List all comments for an issue.

   :param issue_id: Issue ID
   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.delete_comment(comment_id: int, as_json: bool = False) -> str

   Delete a comment.

   :param comment_id: Comment ID
   :param as_json: Return JSON output
   :returns: Formatted output string
   :raises ValueError: If comment not found

Bulk Methods
~~~~~~~~~~~~

.. py:method:: CLI.bulk_create(json_input: str, as_json: bool = False) -> str

   Bulk create issues from JSON.

   :param json_input: JSON string containing list of issues
   :param as_json: Return JSON output
   :returns: Formatted output string
   :raises ValueError: If JSON invalid

   **Example:**

   .. code-block:: python

      json_data = '[{"title": "Issue 1"}, {"title": "Issue 2"}]'
      output = cli.bulk_create(json_data, as_json=True)

.. py:method:: CLI.bulk_update_json(json_input: str, as_json: bool = False) -> str

   Bulk update issues from JSON.

   :param json_input: JSON string with list of updates
   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.bulk_close(json_input: str, as_json: bool = False) -> str

   Bulk close issues from JSON.

   :param json_input: JSON string with list of issue IDs
   :param as_json: Return JSON output
   :returns: Formatted output string

Reporting Methods
~~~~~~~~~~~~~~~~~

.. py:method:: CLI.get_summary(as_json: bool = False) -> str

   Get aggregate statistics.

   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.get_report(group_by: str = "status", as_json: bool = False) -> str

   Get detailed report.

   :param group_by: "status" or "priority"
   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.get_info(as_json: bool = False) -> str

   Get database information.

   :param as_json: Return JSON output
   :returns: Formatted output string

.. py:method:: CLI.get_audit_logs(issue_id: Optional[int] = None, as_json: bool = False) -> str

   Get audit logs.

   :param issue_id: Optional filter by issue
   :param as_json: Return JSON output
   :returns: Formatted output string

Administrative Methods
~~~~~~~~~~~~~~~~~~~~~~

.. py:method:: CLI.clear_all(confirm: bool = False, as_json: bool = False) -> str

   Clear all issues.

   :param confirm: Must be True to proceed
   :param as_json: Return JSON output
   :returns: Formatted output string
   :raises ValueError: If confirm is False

Utility Methods
~~~~~~~~~~~~~~~

.. py:method:: CLI.format_output(data, as_json: bool = False) -> str

   Format data for output.

   :param data: Data to format (Issue, list, dict, etc.)
   :param as_json: Return JSON format
   :returns: Formatted string

Main Function
-------------

.. py:function:: main()

   Main entry point for the CLI application.

   This is called when running ``issuedb-cli`` from the command line.

   **Example:**

   .. code-block:: python

      from issuedb.cli import main

      # Run CLI (typically not called directly)
      main()

Usage Example
-------------

Using CLI class programmatically:

.. code-block:: python

   from issuedb.cli import CLI
   import json

   # Initialize
   cli = CLI("./project.db")

   # Create an issue
   result = cli.create_issue("New feature", priority="high", as_json=True)
   issue = json.loads(result)
   print(f"Created issue #{issue['id']}")

   # Add comment
   cli.add_comment(issue['id'], "Started working on this")

   # Update status
   cli.update_issue(issue['id'], status="in-progress")

   # Get summary
   summary = json.loads(cli.get_summary(as_json=True))
   print(f"Total issues: {summary['total_issues']}")

   # List all issues
   issues = json.loads(cli.list_issues(as_json=True))
   for i in issues:
       print(f"#{i['id']}: {i['title']} [{i['status']}]")

   # Close with comment
   cli.update_issue(issue['id'], status="closed")
   cli.add_comment(issue['id'], "Completed and deployed")
