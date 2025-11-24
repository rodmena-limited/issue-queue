Models API
==========

This module contains the data models used throughout IssueDB.

.. module:: issuedb.models

Enumerations
------------

Priority
~~~~~~~~

.. py:class:: Priority

   Priority levels for issues.

   .. py:attribute:: LOW
      :value: "low"

   .. py:attribute:: MEDIUM
      :value: "medium"

   .. py:attribute:: HIGH
      :value: "high"

   .. py:attribute:: CRITICAL
      :value: "critical"

   .. py:method:: from_string(value: str) -> Priority
      :classmethod:

      Create Priority from string value.

      :param value: Priority string (case-insensitive)
      :returns: Priority enum value
      :raises ValueError: If value is not a valid priority

      **Example:**

      .. code-block:: python

         from issuedb.models import Priority

         p = Priority.from_string("high")
         assert p == Priority.HIGH

         p = Priority.from_string("HIGH")  # Case insensitive
         assert p == Priority.HIGH

   .. py:method:: to_int() -> int

      Convert priority to integer for sorting (higher number = higher priority).

      :returns: Integer value (1=low, 2=medium, 3=high, 4=critical)

      **Example:**

      .. code-block:: python

         assert Priority.LOW.to_int() == 1
         assert Priority.CRITICAL.to_int() == 4

Status
~~~~~~

.. py:class:: Status

   Status levels for issues.

   .. py:attribute:: OPEN
      :value: "open"

   .. py:attribute:: IN_PROGRESS
      :value: "in-progress"

   .. py:attribute:: CLOSED
      :value: "closed"

   .. py:method:: from_string(value: str) -> Status
      :classmethod:

      Create Status from string value.

      :param value: Status string (case-insensitive)
      :returns: Status enum value
      :raises ValueError: If value is not a valid status

Data Classes
------------

Issue
~~~~~

.. py:class:: Issue

   Represents an issue in the tracking system.

   .. py:attribute:: id
      :type: Optional[int]

      Unique issue identifier. None for new issues, set after creation.

   .. py:attribute:: title
      :type: str

      Issue title (required).

   .. py:attribute:: description
      :type: Optional[str]

      Detailed description (optional).

   .. py:attribute:: priority
      :type: Priority

      Issue priority. Default: ``Priority.MEDIUM``

   .. py:attribute:: status
      :type: Status

      Issue status. Default: ``Status.OPEN``

   .. py:attribute:: created_at
      :type: datetime

      Creation timestamp. Default: current time.

   .. py:attribute:: updated_at
      :type: datetime

      Last update timestamp. Default: current time.

   .. py:method:: to_dict() -> dict

      Convert issue to dictionary for JSON serialization.

      :returns: Dictionary with all issue fields

      **Example:**

      .. code-block:: python

         issue = Issue(id=1, title="Fix bug", priority=Priority.HIGH)
         d = issue.to_dict()
         # {'id': 1, 'title': 'Fix bug', 'priority': 'high', ...}

   .. py:method:: from_dict(data: dict) -> Issue
      :classmethod:

      Create Issue from dictionary.

      :param data: Dictionary with issue fields
      :returns: Issue instance

      **Example:**

      .. code-block:: python

         data = {'title': 'New issue', 'priority': 'high'}
         issue = Issue.from_dict(data)
         assert issue.title == 'New issue'
         assert issue.priority == Priority.HIGH

Comment
~~~~~~~

.. py:class:: Comment

   Represents a comment on an issue.

   .. py:attribute:: id
      :type: Optional[int]

      Unique comment identifier. None for new comments.

   .. py:attribute:: issue_id
      :type: int

      ID of the issue this comment belongs to.

   .. py:attribute:: text
      :type: str

      Comment text content.

   .. py:attribute:: created_at
      :type: datetime

      Creation timestamp.

   .. py:method:: to_dict() -> dict

      Convert comment to dictionary for JSON serialization.

      :returns: Dictionary with all comment fields

AuditLog
~~~~~~~~

.. py:class:: AuditLog

   Represents an audit log entry for tracking changes.

   .. py:attribute:: id
      :type: Optional[int]

      Unique log entry identifier.

   .. py:attribute:: issue_id
      :type: int

      ID of the affected issue.

   .. py:attribute:: action
      :type: str

      Type of action: CREATE, UPDATE, DELETE, BULK_CREATE, BULK_UPDATE

   .. py:attribute:: field_name
      :type: Optional[str]

      Name of the field that changed (for UPDATE actions).

   .. py:attribute:: old_value
      :type: Optional[str]

      Previous value (for UPDATE/DELETE actions).

   .. py:attribute:: new_value
      :type: Optional[str]

      New value (for CREATE/UPDATE actions).

   .. py:attribute:: timestamp
      :type: datetime

      When the change occurred.

   .. py:method:: to_dict() -> dict

      Convert audit log to dictionary for JSON serialization.

      :returns: Dictionary with all audit log fields

Usage Examples
--------------

Creating Issues Programmatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from issuedb.models import Issue, Priority, Status

   # Create a new issue
   issue = Issue(
       title="Implement feature X",
       description="Detailed description here",
       priority=Priority.HIGH,
       status=Status.OPEN
   )

   # Convert to dict for JSON
   issue_dict = issue.to_dict()

   # Create from dict (e.g., from JSON input)
   data = {
       'title': 'Another issue',
       'priority': 'critical',
       'status': 'in-progress'
   }
   issue2 = Issue.from_dict(data)

Working with Priorities
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from issuedb.models import Priority

   # Parse from user input
   user_input = "HIGH"
   try:
       priority = Priority.from_string(user_input)
   except ValueError as e:
       print(f"Invalid priority: {e}")

   # Sort issues by priority
   issues = [...]  # List of Issue objects
   sorted_issues = sorted(issues, key=lambda i: i.priority.to_int(), reverse=True)
