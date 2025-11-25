Repository API
==============

The repository layer handles all database operations for IssueDB.

.. module:: issuedb.repository

IssueRepository
---------------

.. py:class:: IssueRepository(db_path: Optional[str] = None)

   Handles all issue-related database operations.

   :param db_path: Optional path to database file. If None, uses ``./issuedb.sqlite``

   **Example:**

   .. code-block:: python

      from issuedb.repository import IssueRepository

      # Use default database
      repo = IssueRepository()

      # Use custom database
      repo = IssueRepository("/path/to/custom.db")

Issue Operations
~~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.create_issue(issue: Issue) -> Issue

   Create a new issue.

   :param issue: Issue object to create (id should be None)
   :returns: Created issue with id populated
   :raises ValueError: If title is missing

   **Example:**

   .. code-block:: python

      from issuedb.models import Issue, Priority

      issue = Issue(
          title="Fix bug",
          description="Detailed description",
          priority=Priority.HIGH
      )
      created = repo.create_issue(issue)
      print(f"Created issue #{created.id}")

.. py:method:: IssueRepository.get_issue(issue_id: int) -> Optional[Issue]

   Get an issue by ID.

   :param issue_id: Issue ID
   :returns: Issue object or None if not found

   **Example:**

   .. code-block:: python

      issue = repo.get_issue(1)
      if issue:
          print(f"Found: {issue.title}")
      else:
          print("Issue not found")

.. py:method:: IssueRepository.update_issue(issue_id: int, **updates) -> Optional[Issue]

   Update an issue.

   :param issue_id: Issue ID
   :param updates: Field updates (title, description, priority, status)
   :returns: Updated issue or None if not found
   :raises ValueError: If invalid field name provided

   **Example:**

   .. code-block:: python

      updated = repo.update_issue(1,
          status="in-progress",
          priority="high"
      )

.. py:method:: IssueRepository.delete_issue(issue_id: int) -> bool

   Delete an issue. Preserves audit trail.

   :param issue_id: Issue ID
   :returns: True if deleted, False if not found

   **Example:**

   .. code-block:: python

      if repo.delete_issue(1):
          print("Issue deleted")
      else:
          print("Issue not found")

.. py:method:: IssueRepository.list_issues(status: Optional[str] = None, priority: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Issue]

   List issues with optional filters.

   :param status: Filter by status
   :param priority: Filter by priority
   :param limit: Maximum number of results
   :param offset: Number of results to skip
   :returns: List of issues

   **Example:**

   .. code-block:: python

      # All open issues
      open_issues = repo.list_issues(status="open")

      # High priority issues, first 10
      urgent = repo.list_issues(priority="high", limit=10)

.. py:method:: IssueRepository.get_next_issue(status: str = "open", log_fetch: bool = True) -> Optional[Issue]

   Get the next issue to work on (FIFO by priority).

   :param status: Status to filter by (default: "open")
   :param log_fetch: If True, logs the fetch in audit trail (default: True)
   :returns: Next issue or None

   **Example:**

   .. code-block:: python

      next_issue = repo.get_next_issue()
      if next_issue:
          print(f"Work on: #{next_issue.id} - {next_issue.title}")

      # Fetch without logging (for preview)
      preview = repo.get_next_issue(log_fetch=False)

.. py:method:: IssueRepository.get_last_fetched(limit: int = 1) -> List[Issue]

   Get the last fetched issue(s) from the audit log.

   :param limit: Maximum number of fetched issues to return (default: 1)
   :returns: List of Issue objects in reverse chronological order (most recent first)

   **Behavior:**

   - Returns issues that were retrieved via ``get_next_issue``
   - Shows current state of existing issues
   - Reconstructs deleted issues from audit log
   - Does not return duplicates

   **Example:**

   .. code-block:: python

      # Get last fetched issue
      last = repo.get_last_fetched()
      if last:
          print(f"Last worked on: {last[0].title}")

      # Get last 5 fetched issues
      recent = repo.get_last_fetched(limit=5)
      for issue in recent:
          print(f"#{issue.id}: {issue.title}")

.. py:method:: IssueRepository.search_issues(keyword: str, limit: Optional[int] = None) -> List[Issue]

   Search issues by keyword in title and description.

   :param keyword: Search keyword
   :param limit: Maximum results
   :returns: List of matching issues

   **Example:**

   .. code-block:: python

      results = repo.search_issues("login", limit=5)

Comment Operations
~~~~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.add_comment(issue_id: int, text: str) -> Comment

   Add a comment to an issue.

   :param issue_id: Issue ID
   :param text: Comment text
   :returns: Created comment
   :raises ValueError: If issue not found or text is empty

   **Example:**

   .. code-block:: python

      comment = repo.add_comment(1, "Started working on this")
      print(f"Comment #{comment.id} added")

.. py:method:: IssueRepository.get_comments(issue_id: int) -> List[Comment]

   Get all comments for an issue.

   :param issue_id: Issue ID
   :returns: List of comments, ordered chronologically

   **Example:**

   .. code-block:: python

      comments = repo.get_comments(1)
      for c in comments:
          print(f"[{c.created_at}] {c.text}")

.. py:method:: IssueRepository.delete_comment(comment_id: int) -> bool

   Delete a comment.

   :param comment_id: Comment ID
   :returns: True if deleted, False if not found

Bulk Operations
~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.bulk_create_issues(issues_data: List[dict]) -> List[Issue]

   Bulk create multiple issues from dictionaries.

   :param issues_data: List of issue dictionaries
   :returns: List of created issues
   :raises ValueError: If any issue data is invalid

   **Example:**

   .. code-block:: python

      issues_data = [
          {"title": "Issue 1", "priority": "high"},
          {"title": "Issue 2", "priority": "medium"},
      ]
      created = repo.bulk_create_issues(issues_data)

.. py:method:: IssueRepository.bulk_update_issues(filter_status: Optional[str] = None, filter_priority: Optional[str] = None, new_status: Optional[str] = None, new_priority: Optional[str] = None) -> int

   Bulk update issues matching filters.

   :param filter_status: Filter by current status
   :param filter_priority: Filter by current priority
   :param new_status: New status to set
   :param new_priority: New priority to set
   :returns: Number of issues updated

   **Example:**

   .. code-block:: python

      # Close all open issues
      count = repo.bulk_update_issues(
          filter_status="open",
          new_status="closed"
      )
      print(f"Closed {count} issues")

.. py:method:: IssueRepository.bulk_update_issues_from_json(updates_data: List[dict]) -> List[Issue]

   Bulk update specific issues from dictionaries.

   :param updates_data: List of dicts with 'id' and fields to update
   :returns: List of updated issues
   :raises ValueError: If any update fails

   **Example:**

   .. code-block:: python

      updates = [
          {"id": 1, "status": "closed"},
          {"id": 2, "priority": "high"},
      ]
      updated = repo.bulk_update_issues_from_json(updates)

.. py:method:: IssueRepository.bulk_close_issues(issue_ids: List[int]) -> List[Issue]

   Bulk close multiple issues.

   :param issue_ids: List of issue IDs to close
   :returns: List of closed issues
   :raises ValueError: If any issue not found

   **Example:**

   .. code-block:: python

      closed = repo.bulk_close_issues([1, 2, 3])

Reporting
~~~~~~~~~

.. py:method:: IssueRepository.get_summary() -> dict

   Get aggregate statistics.

   :returns: Dictionary with totals and breakdowns

   **Example:**

   .. code-block:: python

      summary = repo.get_summary()
      print(f"Total: {summary['total_issues']}")
      print(f"Open: {summary['by_status']['open']['count']}")

.. py:method:: IssueRepository.get_report(group_by: str = "status") -> dict

   Get detailed report grouped by status or priority.

   :param group_by: "status" or "priority"
   :returns: Dictionary with grouped issues
   :raises ValueError: If invalid group_by value

Audit Operations
~~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.get_audit_logs(issue_id: Optional[int] = None) -> List[AuditLog]

   Get audit logs.

   :param issue_id: Optional filter by issue ID
   :returns: List of audit log entries

Administrative
~~~~~~~~~~~~~~

.. py:method:: IssueRepository.clear_all_issues() -> int

   Delete all issues. Preserves audit logs.

   :returns: Number of deleted issues

Complete Example
----------------

.. code-block:: python

   from issuedb.repository import IssueRepository
   from issuedb.models import Issue, Priority, Status

   # Initialize repository
   repo = IssueRepository("./my-project.db")

   # Create issues
   issue1 = repo.create_issue(Issue(
       title="Implement login",
       priority=Priority.HIGH
   ))
   issue2 = repo.create_issue(Issue(
       title="Add tests",
       priority=Priority.MEDIUM
   ))

   # Add comments
   repo.add_comment(issue1.id, "Started implementation")

   # Update status
   repo.update_issue(issue1.id, status="in-progress")

   # Get next issue
   next_issue = repo.get_next_issue()
   print(f"Next: {next_issue.title}")

   # Search
   results = repo.search_issues("login")

   # Get summary
   summary = repo.get_summary()
   print(f"Total issues: {summary['total_issues']}")

   # Bulk close
   repo.bulk_close_issues([issue1.id, issue2.id])
