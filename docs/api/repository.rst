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
          priority=Priority.HIGH,
          due_date=datetime(2025, 12, 31)
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
   :param updates: Field updates (title, description, priority, status, due_date)
   :returns: Updated issue or None if not found
   :raises ValueError: If invalid field name provided

   **Example:**

   .. code-block:: python

      updated = repo.update_issue(1,
          status="in-progress",
          priority="high",
          due_date="2025-01-01"
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

.. py:method:: IssueRepository.list_issues(status: Optional[str] = None, priority: Optional[str] = None, limit: Optional[int] = None, offset: int = 0, due_date: Optional[str] = None, tag: Optional[str] = None) -> List[Issue]

   List issues with optional filters.

   :param status: Filter by status
   :param priority: Filter by priority
   :param limit: Maximum number of results
   :param offset: Number of results to skip
   :param due_date: Filter by due date (exact match)
   :param tag: Filter by tag name
   :returns: List of issues

   **Example:**

   .. code-block:: python

      # All open issues
      open_issues = repo.list_issues(status="open")

      # High priority issues, first 10
      urgent = repo.list_issues(priority="high", limit=10)

      # Issues with 'bug' tag
      bugs = repo.list_issues(tag="bug")

Memory Operations
~~~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.add_memory(key: str, value: str, category: str = "general") -> Memory

   Add a memory item.

   :param key: Unique key
   :param value: Content
   :param category: Category
   :returns: Created Memory object

.. py:method:: IssueRepository.get_memory(key: str) -> Optional[Memory]

   Get a memory item by key.

   :param key: Key to search for
   :returns: Memory object or None

.. py:method:: IssueRepository.list_memory(category: Optional[str] = None, search: Optional[str] = None) -> List[Memory]

   List memory items.

   :param category: Filter by category
   :param search: Search in key or value
   :returns: List of Memory objects

.. py:method:: IssueRepository.update_memory(key: str, value: Optional[str] = None, category: Optional[str] = None) -> Optional[Memory]

   Update a memory item.

   :param key: Key of item to update
   :param value: New value
   :param category: New category
   :returns: Updated Memory object or None

.. py:method:: IssueRepository.delete_memory(key: str) -> bool

   Delete a memory item.

   :param key: Key of item to delete
   :returns: True if deleted

Lessons Learned
~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.add_lesson(lesson: str, issue_id: Optional[int] = None, category: str = "general") -> LessonLearned

   Add a lesson learned.

   :param lesson: Lesson text
   :param issue_id: Related issue ID
   :param category: Category
   :returns: Created LessonLearned object

.. py:method:: IssueRepository.list_lessons(issue_id: Optional[int] = None, category: Optional[str] = None) -> List[LessonLearned]

   List lessons learned.

   :param issue_id: Filter by related issue
   :param category: Filter by category
   :returns: List of LessonLearned objects

Tag Operations
~~~~~~~~~~~~~~

.. py:method:: IssueRepository.create_tag(name: str, color: Optional[str] = None) -> Tag

   Create a new tag.

   :param name: Tag name
   :param color: Optional color code
   :returns: Created Tag object

.. py:method:: IssueRepository.list_tags() -> List[Tag]

   List all tags.

   :returns: List of Tag objects

.. py:method:: IssueRepository.add_issue_tag(issue_id: int, tag_name: str) -> bool

   Add a tag to an issue.

   :param issue_id: Issue ID
   :param tag_name: Tag name
   :returns: True if added, False if already exists

.. py:method:: IssueRepository.remove_issue_tag(issue_id: int, tag_name: str) -> bool

   Remove a tag from an issue.

   :param issue_id: Issue ID
   :param tag_name: Tag name
   :returns: True if removed

.. py:method:: IssueRepository.get_issue_tags(issue_id: int) -> List[Tag]

   Get tags for an issue.

   :param issue_id: Issue ID
   :returns: List of Tag objects

Link Operations
~~~~~~~~~~~~~~~

.. py:method:: IssueRepository.link_issues(source_id: int, target_id: int, relation_type: str) -> IssueRelation

   Link two issues.

   :param source_id: Source issue ID
   :param target_id: Target issue ID
   :param relation_type: Relationship type
   :returns: Created IssueRelation object

.. py:method:: IssueRepository.unlink_issues(source_id: int, target_id: int, relation_type: Optional[str] = None) -> bool

   Unlink issues.

   :param source_id: Source issue ID
   :param target_id: Target issue ID
   :param relation_type: Optional type filter
   :returns: True if removed

.. py:method:: IssueRepository.get_issue_relations(issue_id: int) -> Dict[str, List[dict]]

   Get all relations for an issue.

   :param issue_id: Issue ID
   :returns: Dictionary with 'source' and 'target' lists

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
