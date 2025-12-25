"""Repository layer for issue CRUD operations."""

import contextlib
import fnmatch
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from issuedb.database import get_database
from issuedb.date_utils import parse_date, validate_date_range
from issuedb.models import (
    AuditLog,
    CodeReference,
    Comment,
    Issue,
    IssueRelation,
    IssueTemplate,
    LessonLearned,
    Memory,
    Priority,
    Status,
    Tag,
)


class IssueRepository:
    """Handles all issue-related database operations."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize repository with database connection.

        Args:
            db_path: Optional path to database file.
        """
        self.db = get_database(db_path)

    def _log_audit(
        self,
        conn: Any,
        issue_id: int,
        action: str,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> None:
        """Log an audit entry for an issue change.

        Args:
            conn: Database connection to use
            issue_id: ID of the affected issue
            action: Action type (CREATE, UPDATE, DELETE)
            field_name: Name of the field that changed
            old_value: Previous value
            new_value: New value
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (issue_id, action, field_name, old_value, new_value)
            VALUES (?, ?, ?, ?, ?)
        """,
            (issue_id, action, field_name, old_value, new_value),
        )

    def create_issue(self, issue: Issue) -> Issue:
        """Create a new issue.

        Args:
            issue: Issue object to create.

        Returns:
            Issue: Created issue with assigned ID.

        Raises:
            ValueError: If required fields are missing.
        """
        if not issue.title:
            raise ValueError("Title is required")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO issues (title, description, priority, status,
                                   created_at, updated_at, estimated_hours, due_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    issue.title,
                    issue.description,
                    issue.priority.value,
                    issue.status.value,
                    issue.created_at.isoformat(),
                    issue.updated_at.isoformat(),
                    issue.estimated_hours,
                    issue.due_date.isoformat() if issue.due_date else None,
                ),
            )

            issue.id = cursor.lastrowid
            assert issue.id is not None  # Guaranteed by successful insert

            # Log creation in audit log
            self._log_audit(
                conn,
                issue.id,
                "CREATE",
                None,
                None,
                json.dumps(issue.to_dict()),
            )

        return issue

    def _get_issue_with_conn(self, conn: Any, issue_id: int) -> Optional[Issue]:
        """Get an issue by ID using an existing connection.

        Args:
            conn: Database connection to use.
            issue_id: ID of the issue to retrieve.

        Returns:
            Issue if found, None otherwise.

        Note:
            Internal method to avoid nested connections.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM issues WHERE id = ?
        """,
            (issue_id,),
        )
        row = cursor.fetchone()

        if row:
            issue = self._row_to_issue(row)
            # Populate tags using the same connection
            issue.tags = self._get_issue_tags_with_conn(conn, issue_id)
            return issue
        return None

    def get_issue(self, issue_id: int) -> Optional[Issue]:
        """Get an issue by ID.

        Args:
            issue_id: ID of the issue to retrieve.

        Returns:
            Issue if found, None otherwise.
        """
        with self.db.get_connection() as conn:
            return self._get_issue_with_conn(conn, issue_id)

    def update_issue(self, issue_id: int, **updates: Any) -> Optional[Issue]:
        """Update an issue.

        Args:
            issue_id: ID of the issue to update.
            **updates: Fields to update (title, description, priority, status).

        Returns:
            Updated Issue if found, None otherwise.

        Raises:
            ValueError: If invalid field names or values are provided.
        """
        # Use a single connection for the entire operation to avoid deadlocks
        with self.db.get_connection() as conn:
            # Get current issue for audit logging
            current_issue = self._get_issue_with_conn(conn, issue_id)
            if not current_issue:
                return None

            # Validate and prepare updates
            allowed_fields = {"title", "description", "priority", "status", "due_date"}
            update_fields: List[str] = []
            update_values: List[Any] = []
            audit_entries: List[tuple[str, str, str]] = []

            for field, value in updates.items():
                if field not in allowed_fields:
                    raise ValueError(f"Cannot update field: {field}")

                # Validate and convert enums
                old_value: Any
                if field == "priority":
                    value = Priority.from_string(value).value
                    old_value = current_issue.priority.value
                elif field == "status":
                    value = Status.from_string(value).value
                    old_value = current_issue.status.value
                elif field == "due_date":
                    # Value should be ISO format string or None
                    if value:
                        # Validate date format
                        try:
                            datetime.fromisoformat(value)
                        except ValueError:
                            raise ValueError(f"Invalid date format for {field}: {value}") from None
                    due_date = current_issue.due_date
                    old_value = due_date.isoformat() if due_date else None
                else:
                    old_value = getattr(current_issue, field)

                # Only update if value changed
                if str(old_value) != str(value):
                    update_fields.append(f"{field} = ?")
                    update_values.append(value)
                    audit_entries.append((field, str(old_value), str(value)))

            if not update_fields:
                return current_issue  # No changes

            # Always update the updated_at timestamp
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat())

            # Add issue_id for WHERE clause
            update_values.append(issue_id)

            cursor = conn.cursor()
            query = f"UPDATE issues SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, update_values)

            # Log each field change in audit log
            for field, old_val, new_val in audit_entries:
                assert issue_id is not None  # Already validated above
                self._log_audit(
                    conn,
                    issue_id,
                    "UPDATE",
                    field,
                    old_val,
                    new_val,
                )

            # Return updated issue using the same connection
            return self._get_issue_with_conn(conn, issue_id)

    def bulk_update_issues(
        self,
        new_status: Optional[str] = None,
        new_priority: Optional[str] = None,
        filter_status: Optional[str] = None,
        filter_priority: Optional[str] = None,
    ) -> int:
        """Bulk update issues matching filters.

        Args:
            new_status: New status to set.
            new_priority: New priority to set.
            filter_status: Filter by current status.
            filter_priority: Filter by current priority.

        Returns:
            Number of issues updated.

        Raises:
            ValueError: If invalid field names or values are provided.
        """
        update_fields: List[str] = []
        update_values: List[Any] = []

        # Prepare updates
        if new_status:
            status_value = Status.from_string(new_status).value
            update_fields.append("status = ?")
            update_values.append(status_value)

        if new_priority:
            priority_value = Priority.from_string(new_priority).value
            update_fields.append("priority = ?")
            update_values.append(priority_value)

        if not update_fields:
            return 0  # No changes

        # Always update the updated_at timestamp
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat())

        # Build WHERE clause for filters
        where_conditions = []
        where_values = []
        if filter_status:
            filter_status_enum = Status.from_string(filter_status)
            where_conditions.append("status = ?")
            where_values.append(filter_status_enum.value)
        if filter_priority:
            filter_priority_enum = Priority.from_string(filter_priority)
            where_conditions.append("priority = ?")
            where_values.append(filter_priority_enum.value)

        where_clause = f" WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get affected issues for audit logging
            select_query = f"SELECT * FROM issues{where_clause}"
            cursor.execute(select_query, where_values)
            affected_issues = [self._row_to_issue(row) for row in cursor.fetchall()]

            if not affected_issues:
                return 0

            # Perform bulk update
            query = f"UPDATE issues SET {', '.join(update_fields)}{where_clause}"
            cursor.execute(query, update_values + where_values)

            # Log audit entries for each affected issue
            for issue in affected_issues:
                assert issue.id is not None  # Issues from DB always have ID
                if new_status:
                    old_value = issue.status.value
                    new_value = Status.from_string(new_status).value
                    if old_value != new_value:
                        self._log_audit(
                            conn,
                            issue.id,
                            "BULK_UPDATE",
                            "status",
                            old_value,
                            new_value,
                        )

                if new_priority:
                    old_value = issue.priority.value
                    new_value = Priority.from_string(new_priority).value
                    if old_value != new_value:
                        self._log_audit(
                            conn,
                            issue.id,
                            "BULK_UPDATE",
                            "priority",
                            old_value,
                            new_value,
                        )

            return len(affected_issues)

    def delete_issue(self, issue_id: int) -> bool:
        """Delete an issue.

        Args:
            issue_id: ID of the issue to delete.

        Returns:
            True if issue was deleted, False if not found.
        """
        # Use a single connection for the entire operation to avoid deadlocks
        with self.db.get_connection() as conn:
            # Get issue details for audit log before deletion
            issue = self._get_issue_with_conn(conn, issue_id)
            if not issue:
                return False

            cursor = conn.cursor()
            cursor.execute("DELETE FROM issues WHERE id = ?", (issue_id,))

            # Log deletion in audit log (with full issue data)
            self._log_audit(
                conn,
                issue_id,
                "DELETE",
                None,
                json.dumps(issue.to_dict()),
                None,
            )

            return cursor.rowcount > 0

    def count_issues(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[str] = None,
        tag: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> int:
        """Count issues matching optional filters.

        Args:
            status: Filter by status.
            priority: Filter by priority.
            due_date: Filter by due date (exact match).
            tag: Filter by tag name.
            keyword: Filter by keyword search in title/description.

        Returns:
            Count of matching issues.
        """
        query = "SELECT COUNT(DISTINCT i.id) as count FROM issues i"
        params: List[Any] = []

        joins = []
        wheres = ["1=1"]

        if tag:
            joins.append("JOIN issue_tags it ON i.id = it.issue_id")
            joins.append("JOIN tags t ON it.tag_id = t.id")
            wheres.append("t.name = ?")
            params.append(tag)

        if status:
            Status.from_string(status)  # Validate status
            wheres.append("i.status = ?")
            params.append(status.lower())

        if priority:
            Priority.from_string(priority)  # Validate priority
            wheres.append("i.priority = ?")
            params.append(priority.lower())

        if due_date:
            wheres.append("date(i.due_date) = date(?)")
            params.append(due_date)

        if keyword:
            wheres.append("(i.title LIKE ? OR i.description LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        if joins:
            query += " " + " ".join(joins)

        query += " WHERE " + " AND ".join(wheres)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return int(result["count"]) if result else 0

    def list_issues(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        due_date: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Issue]:
        """List issues with optional filters.

        Args:
            status: Filter by status.
            priority: Filter by priority.
            limit: Maximum number of issues to return.
            offset: Number of issues to skip.
            due_date: Filter by due date (exact match).
            tag: Filter by tag name.

        Returns:
            List of matching issues.
        """
        query = "SELECT DISTINCT i.* FROM issues i"
        params: List[Any] = []

        joins = []
        wheres = ["1=1"]

        if tag:
            joins.append("JOIN issue_tags it ON i.id = it.issue_id")
            joins.append("JOIN tags t ON it.tag_id = t.id")
            wheres.append("t.name = ?")
            params.append(tag)

        if status:
            Status.from_string(status)  # Validate status
            wheres.append("i.status = ?")
            params.append(status.lower())

        if priority:
            Priority.from_string(priority)  # Validate priority
            wheres.append("i.priority = ?")
            params.append(priority.lower())

        if due_date:
            wheres.append("date(i.due_date) = date(?)")
            params.append(due_date)

        if joins:
            query += " " + " ".join(joins)

        query += " WHERE " + " AND ".join(wheres)
        query += " ORDER BY i.created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)
            if offset:
                query += " OFFSET ?"
                params.append(offset)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_issue(row) for row in rows]

    def get_all_issues(self) -> List[Issue]:
        """Get all issues without any filters or pagination.

        Returns:
            List of all issues in the database.
        """
        query = "SELECT * FROM issues ORDER BY created_at DESC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            return [self._row_to_issue(row) for row in rows]

    def get_next_issue(
        self, status: Optional[str] = None, log_fetch: bool = True
    ) -> Optional[Issue]:
        """Get the next issue based on priority and creation date (FIFO within priority).

        Skips issues that are blocked by unresolved (open/in-progress) issues.

        Args:
            status: Filter by status (defaults to 'open' if not specified).
            log_fetch: If True, log this fetch in the audit log (default: True).

        Returns:
            Next Issue to work on, or None if no issues match.
        """
        query = """
            SELECT * FROM issues
            WHERE 1=1
        """
        params: List[Any] = []

        # Default to open issues if status not specified
        if status:
            Status.from_string(status)  # Validate status
            query += " AND status = ?"
            params.append(status.lower())
        else:
            query += " AND status = ?"
            params.append(Status.OPEN.value)

        # Exclude blocked issues (issues with unresolved blockers)
        query += """
            AND id NOT IN (
                SELECT DISTINCT d.blocked_id
                FROM issue_dependencies d
                INNER JOIN issues blocker ON blocker.id = d.blocker_id
                WHERE blocker.status != 'closed'
            )
        """

        # Order by priority (critical first) then by creation date (FIFO)
        query += """
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at ASC
            LIMIT 1
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()

            if row:
                issue = self._row_to_issue(row)
                # Log the fetch in audit log
                if log_fetch and issue.id is not None:
                    self._log_audit(
                        conn,
                        issue.id,
                        "FETCH",
                        None,
                        None,
                        json.dumps(issue.to_dict()),
                    )
                return issue
            return None

    def search_issues(
        self, keyword: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[Issue]:
        """Search issues by keyword in title and description.

        Args:
            keyword: Keyword to search for.
            limit: Maximum number of issues to return.
            offset: Number of issues to skip.

        Returns:
            List of matching issues.
        """
        query = """
            SELECT * FROM issues
            WHERE (title LIKE ? OR description LIKE ?)
        """
        params: List[Any] = [f"%{keyword}%", f"%{keyword}%"]

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)
            if offset:
                query += " OFFSET ?"
                params.append(offset)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_issue(row) for row in rows]

    def clear_all_issues(self) -> int:
        """Clear all issues from the database.

        Returns:
            Number of issues deleted.
        """
        # Get all issues for audit logging
        issues = self.list_issues()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Log deletion for each issue
            for issue in issues:
                assert issue.id is not None  # Issues from DB always have ID
                self._log_audit(
                    conn,
                    issue.id,
                    "DELETE",
                    None,
                    json.dumps(issue.to_dict()),
                    None,
                )

            # Delete all issues
            cursor.execute("DELETE FROM issues")
            return cursor.rowcount

    def get_audit_logs(self, issue_id: Optional[int] = None) -> List[AuditLog]:
        """Get audit logs for issues.

        Args:
            issue_id: Filter by issue ID.

        Returns:
            List of audit log entries.
        """
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if issue_id:
            query += " AND issue_id = ?"
            params.append(issue_id)

        query += " ORDER BY id DESC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            logs = []
            for row in rows:
                log = AuditLog(
                    id=row["id"],
                    issue_id=row["issue_id"],
                    action=row["action"],
                    field_name=row["field_name"],
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                logs.append(log)

            return logs

    def get_last_fetched(self, limit: int = 1) -> List[Issue]:
        """Get the last fetched issue(s) from the audit log.

        Args:
            limit: Maximum number of fetched issues to return (default: 1).

        Returns:
            List of Issue objects that were last fetched via get-next.
            Issues are returned in reverse chronological order (most recent first).
            If an issue has been deleted, it will not be included.
        """
        query = """
            SELECT DISTINCT al.issue_id, al.new_value, al.timestamp, i.id as current_id
            FROM audit_logs al
            LEFT JOIN issues i ON al.issue_id = i.id
            WHERE al.action = 'FETCH'
            ORDER BY al.id DESC
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            issues = []
            seen_ids: set[int] = set()

            for row in rows:
                issue_id = row["issue_id"]

                # Skip duplicates (same issue fetched multiple times)
                if issue_id in seen_ids:
                    continue

                # If issue still exists, get current state
                if row["current_id"] is not None:
                    issue = self.get_issue(issue_id)
                    if issue:
                        issues.append(issue)
                        seen_ids.add(issue_id)
                else:
                    # Issue was deleted, reconstruct from audit log
                    if row["new_value"]:
                        try:
                            issue_data = json.loads(row["new_value"])
                            issue = Issue.from_dict(issue_data)
                            issue.id = issue_id
                            issues.append(issue)
                            seen_ids.add(issue_id)
                        except (json.JSONDecodeError, KeyError):
                            # Skip if we can't reconstruct
                            continue

                if len(issues) >= limit:
                    break

            return issues

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of issues.

        Returns:
            Dictionary with issue statistics including counts by status and priority.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get total count
            query = "SELECT COUNT(*) as count FROM issues"
            cursor.execute(query)
            total_count = cursor.fetchone()["count"]

            # Get count by status
            query = """
                SELECT status, COUNT(*) as count
                FROM issues
                GROUP BY status
            """
            cursor.execute(query)
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Get count by priority
            query = """
                SELECT priority, COUNT(*) as count
                FROM issues
                GROUP BY priority
            """
            cursor.execute(query)
            priority_counts = {row["priority"]: row["count"] for row in cursor.fetchall()}

            # Calculate percentages
            status_percentages = {}
            if total_count > 0:
                for status in ["open", "in-progress", "closed", "wont-do"]:
                    count = status_counts.get(status, 0)
                    status_percentages[status] = round((count / total_count) * 100, 1)

            priority_percentages = {}
            if total_count > 0:
                for priority in ["low", "medium", "high", "critical"]:
                    count = priority_counts.get(priority, 0)
                    priority_percentages[priority] = round((count / total_count) * 100, 1)

            return {
                "total_issues": total_count,
                "by_status": {
                    "open": status_counts.get("open", 0),
                    "in_progress": status_counts.get("in-progress", 0),
                    "closed": status_counts.get("closed", 0),
                    "wont_do": status_counts.get("wont-do", 0),
                },
                "by_priority": {
                    "low": priority_counts.get("low", 0),
                    "medium": priority_counts.get("medium", 0),
                    "high": priority_counts.get("high", 0),
                    "critical": priority_counts.get("critical", 0),
                },
                "status_percentages": status_percentages,
                "priority_percentages": priority_percentages,
            }

    def get_report(self, group_by: str = "status") -> dict[str, Any]:
        """Get detailed report of issues grouped by status or priority.

        Args:
            group_by: Group issues by 'status' or 'priority' (default: 'status').

        Returns:
            Dictionary with grouped issue lists.
        """
        if group_by not in ["status", "priority"]:
            raise ValueError("group_by must be 'status' or 'priority'")

        # Get all issues
        issues = self.list_issues()

        # Group issues
        grouped: Dict[str, List[Issue]]
        if group_by == "status":
            grouped = {
                "open": [],
                "in_progress": [],
                "closed": [],
            }
            for issue in issues:
                key = "in_progress" if issue.status.value == "in-progress" else issue.status.value
                grouped[key].append(issue)
        else:  # group by priority
            grouped = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            }
            for issue in issues:
                grouped[issue.priority.value].append(issue)

        # Convert to dict format
        result: Dict[str, Any] = {
            "group_by": group_by,
            "total_issues": len(issues),
            "groups": {},
        }

        for key, issue_list in grouped.items():
            result["groups"][key] = {
                "count": len(issue_list),
                "issues": [issue.to_dict() for issue in issue_list],
            }

        return result

    def bulk_create_issues(self, issues_data: List[dict[str, Any]]) -> List[Issue]:
        """Bulk create multiple issues from JSON data.

        Args:
            issues_data: List of dictionaries containing issue data.

        Returns:
            List of created Issue objects.

        Raises:
            ValueError: If any issue data is invalid.
        """
        created_issues = []

        with self.db.get_connection() as conn:
            for issue_data in issues_data:
                # Validate required fields
                if "title" not in issue_data or not issue_data["title"]:
                    raise ValueError(f"Title is required for all issues: {issue_data}")

                # Create Issue object from dict
                issue = Issue.from_dict(issue_data)

                # Insert into database
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO issues (title, description, priority, status,
                                       created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        issue.title,
                        issue.description,
                        issue.priority.value,
                        issue.status.value,
                        issue.created_at.isoformat(),
                        issue.updated_at.isoformat(),
                    ),
                )

                issue.id = cursor.lastrowid
                assert issue.id is not None  # Guaranteed by successful insert

                # Log creation in audit log
                self._log_audit(
                    conn,
                    issue.id,
                    "BULK_CREATE",
                    None,
                    None,
                    json.dumps(issue.to_dict()),
                )

                created_issues.append(issue)

        return created_issues

    def bulk_update_issues_from_json(self, updates_data: List[dict[str, Any]]) -> List[Issue]:
        """Bulk update multiple specific issues from JSON data.

        Args:
            updates_data: List of dictionaries with 'id' and fields to update.

        Returns:
            List of updated Issue objects.

        Raises:
            ValueError: If any update data is invalid or issue not found.
        """
        updated_issues = []

        for update_data in updates_data:
            # Validate required id field
            if "id" not in update_data:
                raise ValueError(f"Issue ID is required for all updates: {update_data}")

            issue_id = update_data["id"]

            # Extract update fields (exclude id)
            updates = {k: v for k, v in update_data.items() if k != "id"}

            if not updates:
                raise ValueError(f"No update fields provided for issue {issue_id}")

            # Update the issue
            updated_issue = self.update_issue(issue_id, **updates)

            if not updated_issue:
                raise ValueError(f"Issue {issue_id} not found")

            updated_issues.append(updated_issue)

        return updated_issues

    def bulk_close_issues(self, issue_ids: List[int]) -> List[Issue]:
        """Bulk close multiple issues by their IDs.

        Args:
            issue_ids: List of issue IDs to close.

        Returns:
            List of closed Issue objects.

        Raises:
            ValueError: If any issue not found.
        """
        closed_issues = []

        for issue_id in issue_ids:
            # Update status to closed
            updated_issue = self.update_issue(issue_id, status="closed")

            if not updated_issue:
                raise ValueError(f"Issue {issue_id} not found")

            closed_issues.append(updated_issue)

        return closed_issues

    def add_comment(self, issue_id: int, text: str) -> Comment:
        """Add a comment to an issue.

        Args:
            issue_id: ID of the issue to comment on.
            text: Comment text.

        Returns:
            Created Comment object.

        Raises:
            ValueError: If issue not found or text is empty.
        """
        if not text or not text.strip():
            raise ValueError("Comment text cannot be empty")

        # Verify issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        comment = Comment(
            issue_id=issue_id,
            text=text.strip(),
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO comments (issue_id, text, created_at)
                VALUES (?, ?, ?)
            """,
                (
                    comment.issue_id,
                    comment.text,
                    comment.created_at.isoformat(),
                ),
            )

            comment.id = cursor.lastrowid

        return comment

    def get_comments(self, issue_id: int) -> List[Comment]:
        """Get all comments for an issue.

        Args:
            issue_id: ID of the issue.

        Returns:
            List of Comment objects, ordered by creation time.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM comments
                WHERE issue_id = ?
                ORDER BY created_at ASC
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()

            comments = []
            for row in rows:
                comment = Comment(
                    id=row["id"],
                    issue_id=row["issue_id"],
                    text=row["text"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                comments.append(comment)

            return comments

    def delete_comment(self, comment_id: int) -> bool:
        """Delete a comment.

        Args:
            comment_id: ID of the comment to delete.

        Returns:
            True if comment was deleted, False if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
            return cursor.rowcount > 0

    def find_by_pattern(
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
        use_regex: bool = False,
        case_sensitive: bool = False,
    ) -> List[Issue]:
        """Find issues matching title and/or description patterns.

        Args:
            title_pattern: Pattern to match against title (glob or regex).
            desc_pattern: Pattern to match against description (glob or regex).
            use_regex: If True, patterns are regex; if False, glob patterns.
            case_sensitive: If True, matching is case-sensitive.

        Returns:
            List of matching issues.
        """
        all_issues = self.get_all_issues()
        matching_issues = []

        for issue in all_issues:
            title_match = True
            desc_match = True

            # Match title if pattern provided
            if title_pattern:
                title_text = issue.title if case_sensitive else issue.title.lower()
                pattern = title_pattern if case_sensitive else title_pattern.lower()

                if use_regex:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    title_match = bool(re.search(pattern, issue.title, flags=flags))
                else:
                    title_match = fnmatch.fnmatch(title_text, pattern)

            # Match description if pattern provided
            if desc_pattern and issue.description:
                desc_text = issue.description if case_sensitive else issue.description.lower()
                pattern = desc_pattern if case_sensitive else desc_pattern.lower()

                if use_regex:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    desc_match = bool(re.search(pattern, issue.description, flags=flags))
                else:
                    desc_match = fnmatch.fnmatch(desc_text, pattern)
            elif desc_pattern and not issue.description:
                desc_match = False

            # Include issue if both patterns match (or pattern not provided)
            if title_match and desc_match:
                matching_issues.append(issue)

        return matching_issues

    def bulk_close_by_pattern(
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
        use_regex: bool = False,
        case_sensitive: bool = False,
        dry_run: bool = False,
    ) -> List[Issue]:
        """Close issues matching the pattern.

        Args:
            title_pattern: Pattern to match against title.
            desc_pattern: Pattern to match against description.
            use_regex: If True, patterns are regex; if False, glob patterns.
            case_sensitive: If True, matching is case-sensitive.
            dry_run: If True, return matches without making changes.

        Returns:
            List of issues that were (or would be) closed.
        """
        matching_issues = self.find_by_pattern(
            title_pattern=title_pattern,
            desc_pattern=desc_pattern,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
        )

        if dry_run:
            return matching_issues

        # Close all matching issues
        closed_issues = []
        for issue in matching_issues:
            assert issue.id is not None  # Issues from DB always have ID
            updated_issue = self.update_issue(issue.id, status="closed")
            if updated_issue:
                closed_issues.append(updated_issue)

        return closed_issues

    def bulk_update_by_pattern(
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
        use_regex: bool = False,
        case_sensitive: bool = False,
        new_status: Optional[str] = None,
        new_priority: Optional[str] = None,
        dry_run: bool = False,
    ) -> List[Issue]:
        """Update issues matching the pattern.

        Args:
            title_pattern: Pattern to match against title.
            desc_pattern: Pattern to match against description.
            use_regex: If True, patterns are regex; if False, glob patterns.
            case_sensitive: If True, matching is case-sensitive.
            new_status: New status to set.
            new_priority: New priority to set.
            dry_run: If True, return matches without making changes.

        Returns:
            List of issues that were (or would be) updated.
        """
        matching_issues = self.find_by_pattern(
            title_pattern=title_pattern,
            desc_pattern=desc_pattern,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
        )

        if dry_run:
            return matching_issues

        # Update all matching issues
        updated_issues = []
        updates = {}
        if new_status:
            updates["status"] = new_status
        if new_priority:
            updates["priority"] = new_priority

        if not updates:
            return []  # No updates to apply

        for issue in matching_issues:
            assert issue.id is not None  # Issues from DB always have ID
            updated_issue = self.update_issue(issue.id, **updates)
            if updated_issue:
                updated_issues.append(updated_issue)

        return updated_issues

    def bulk_delete_by_pattern(
        self,
        title_pattern: Optional[str] = None,
        desc_pattern: Optional[str] = None,
        use_regex: bool = False,
        case_sensitive: bool = False,
        dry_run: bool = False,
    ) -> List[Issue]:
        """Delete issues matching the pattern.

        Args:
            title_pattern: Pattern to match against title.
            desc_pattern: Pattern to match against description.
            use_regex: If True, patterns are regex; if False, glob patterns.
            case_sensitive: If True, matching is case-sensitive.
            dry_run: If True, return matches without making changes.

        Returns:
            List of issues that were (or would be) deleted.
        """
        matching_issues = self.find_by_pattern(
            title_pattern=title_pattern,
            desc_pattern=desc_pattern,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
        )

        if dry_run:
            return matching_issues

        # Delete all matching issues
        deleted_issues = []
        for issue in matching_issues:
            assert issue.id is not None  # Issues from DB always have ID
            # Store issue before deletion
            deleted_issues.append(issue)
            self.delete_issue(issue.id)

        return deleted_issues

    def _row_to_issue(self, row: Any) -> Issue:
        """Convert a database row to an Issue object.

        Args:
            row: SQLite row object.

        Returns:
            Issue object.
        """
        issue = Issue(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=Priority.from_string(row["priority"]),
            status=Status.from_string(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

        if "estimated_hours" in row and row["estimated_hours"] is not None:
            issue.estimated_hours = row["estimated_hours"]

        if "due_date" in row and row["due_date"] is not None:
            issue.due_date = datetime.fromisoformat(row["due_date"])

        return issue

    def parse_file_spec(self, file_spec: str) -> Tuple[str, Optional[int], Optional[int]]:
        """Parse file specification with optional line numbers.

        Supports formats:
        - path/to/file.py
        - path/to/file.py:45
        - path/to/file.py:45-60

        Args:
            file_spec: File specification string.

        Returns:
            Tuple of (file_path, start_line, end_line).

        Raises:
            ValueError: If format is invalid.
        """
        # Split by colon to separate path and line numbers
        parts = file_spec.rsplit(":", 1)
        file_path = parts[0]

        start_line: Optional[int] = None
        end_line: Optional[int] = None

        if len(parts) == 2:
            line_spec = parts[1]
            # Check if it's a range (start-end)
            if "-" in line_spec:
                line_parts = line_spec.split("-", 1)
                try:
                    start_line = int(line_parts[0])
                    end_line = int(line_parts[1])
                    if start_line > end_line:
                        raise ValueError(
                            f"Invalid line range: {start_line}-{end_line} "
                            "(start line must be <= end line)"
                        )
                except ValueError as e:
                    if "invalid literal" in str(e):
                        raise ValueError(f"Invalid line range format: {line_spec}") from e
                    raise
            else:
                # Single line number
                try:
                    start_line = int(line_spec)
                    end_line = None
                except ValueError as e:
                    raise ValueError(f"Invalid line number: {line_spec}") from e

        return file_path, start_line, end_line

    def add_code_reference(
        self,
        issue_id: int,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        note: Optional[str] = None,
        validate_file: bool = True,
    ) -> CodeReference:
        """Add a code reference to an issue.

        Args:
            issue_id: ID of the issue.
            file_path: Path to the file (relative or absolute).
            start_line: Optional starting line number.
            end_line: Optional ending line number.
            note: Optional note about this reference.
            validate_file: If True, validate that file exists.

        Returns:
            Created CodeReference object.

        Raises:
            ValueError: If issue not found or file doesn't exist (when validate_file=True).
        """
        # Verify issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        # Validate line numbers
        if start_line is not None and start_line < 1:
            raise ValueError("Line numbers must be >= 1")
        if end_line is not None and end_line < 1:
            raise ValueError("Line numbers must be >= 1")
        if start_line is not None and end_line is not None and start_line > end_line:
            raise ValueError("start_line must be <= end_line")

        # Convert to relative path if absolute
        if os.path.isabs(file_path):
            with contextlib.suppress(ValueError):
                file_path = os.path.relpath(file_path)

        # Validate file exists if requested
        if validate_file and not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        code_ref = CodeReference(
            issue_id=issue_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            note=note,
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO code_references
                (issue_id, file_path, start_line, end_line, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    code_ref.issue_id,
                    code_ref.file_path,
                    code_ref.start_line,
                    code_ref.end_line,
                    code_ref.note,
                    code_ref.created_at.isoformat(),
                ),
            )
            code_ref.id = cursor.lastrowid

        return code_ref

    def remove_code_reference(
        self,
        issue_id: int,
        file_path: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> int:
        """Remove code reference(s) from an issue.

        Args:
            issue_id: ID of the issue.
            file_path: Optional file path to remove (removes all refs to this file).
            reference_id: Optional specific reference ID to remove.

        Returns:
            Number of references removed.

        Raises:
            ValueError: If neither file_path nor reference_id is provided.
        """
        if file_path is None and reference_id is None:
            raise ValueError("Must provide either file_path or reference_id")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if reference_id is not None:
                # Remove specific reference
                cursor.execute(
                    "DELETE FROM code_references WHERE id = ? AND issue_id = ?",
                    (reference_id, issue_id),
                )
            else:
                # Remove all references to file_path
                # Convert to relative path if absolute for comparison
                if file_path and os.path.isabs(file_path):
                    with contextlib.suppress(ValueError):
                        file_path = os.path.relpath(file_path)

                cursor.execute(
                    "DELETE FROM code_references WHERE issue_id = ? AND file_path = ?",
                    (issue_id, file_path),
                )

            return cursor.rowcount

    def get_code_references(self, issue_id: int) -> List[CodeReference]:
        """Get all code references for an issue.

        Args:
            issue_id: ID of the issue.

        Returns:
            List of CodeReference objects.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM code_references
                WHERE issue_id = ?
                ORDER BY created_at ASC
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()

            references = []
            for row in rows:
                ref = CodeReference(
                    id=row["id"],
                    issue_id=row["issue_id"],
                    file_path=row["file_path"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    note=row["note"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                references.append(ref)

            return references

    def get_issues_by_file(self, file_path: str) -> List[Issue]:
        """Get all issues that reference a specific file.

        Args:
            file_path: Path to the file.

        Returns:
            List of Issue objects that reference this file.
        """
        # Convert to relative path if absolute for comparison
        if os.path.isabs(file_path):
            with contextlib.suppress(ValueError):
                file_path = os.path.relpath(file_path)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT i.*
                FROM issues i
                JOIN code_references cr ON i.id = cr.issue_id
                WHERE cr.file_path = ?
                ORDER BY i.created_at DESC
            """,
                (file_path,),
            )
            rows = cursor.fetchall()

            return [self._row_to_issue(row) for row in rows]

    # Dependency management methods

    def add_dependency(self, blocked_id: int, blocker_id: int) -> bool:
        """Add a dependency relationship between issues.

        Args:
            blocked_id: ID of the issue being blocked.
            blocker_id: ID of the issue that blocks.

        Returns:
            True if dependency was added, False if it already exists.

        Raises:
            ValueError: If either issue doesn't exist or if adding would create a cycle.
        """
        # Verify both issues exist
        blocked_issue = self.get_issue(blocked_id)
        blocker_issue = self.get_issue(blocker_id)

        if not blocked_issue:
            raise ValueError(f"Blocked issue {blocked_id} not found")
        if not blocker_issue:
            raise ValueError(f"Blocker issue {blocker_id} not found")

        # Prevent self-blocking
        if blocked_id == blocker_id:
            raise ValueError("Issue cannot block itself")

        # Check for cycles (would blocker_id be blocked by blocked_id?)
        if self._would_create_cycle(blocked_id, blocker_id):
            raise ValueError(
                f"Adding this dependency would create a cycle: "
                f"issue {blocker_id} is already transitively blocked by issue {blocked_id}"
            )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO issue_dependencies (blocker_id, blocked_id)
                    VALUES (?, ?)
                """,
                    (blocker_id, blocked_id),
                )
                return True
            except Exception as e:
                # Check if it's a unique constraint violation
                if "UNIQUE constraint failed" in str(e):
                    return False
                raise

    def remove_dependency(self, blocked_id: int, blocker_id: Optional[int] = None) -> int:
        """Remove dependency relationship(s) for an issue.

        Args:
            blocked_id: ID of the blocked issue.
            blocker_id: ID of the blocker issue. If None, removes all blockers.

        Returns:
            Number of dependencies removed.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if blocker_id is not None:
                cursor.execute(
                    """
                    DELETE FROM issue_dependencies
                    WHERE blocked_id = ? AND blocker_id = ?
                """,
                    (blocked_id, blocker_id),
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM issue_dependencies
                    WHERE blocked_id = ?
                """,
                    (blocked_id,),
                )

            return cursor.rowcount

    def get_blockers(self, issue_id: int) -> List[Issue]:
        """Get all issues blocking this issue.

        Args:
            issue_id: ID of the issue.

        Returns:
            List of Issue objects that are blocking this issue.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT i.* FROM issues i
                INNER JOIN issue_dependencies d ON i.id = d.blocker_id
                WHERE d.blocked_id = ?
                ORDER BY
                    CASE i.priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    i.created_at ASC
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_issue(row) for row in rows]

    def get_blocking(self, issue_id: int) -> List[Issue]:
        """Get all issues that this issue is blocking.

        Args:
            issue_id: ID of the issue.

        Returns:
            List of Issue objects that are blocked by this issue.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT i.* FROM issues i
                INNER JOIN issue_dependencies d ON i.id = d.blocked_id
                WHERE d.blocker_id = ?
                ORDER BY
                    CASE i.priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    i.created_at ASC
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_issue(row) for row in rows]

    def is_blocked(self, issue_id: int) -> bool:
        """Check if an issue has unresolved blockers.

        Args:
            issue_id: ID of the issue.

        Returns:
            True if the issue has at least one open/in-progress blocker.
        """
        blockers = self.get_blockers(issue_id)
        # Issue is blocked if it has any blocker that is not closed
        return any(blocker.status != Status.CLOSED for blocker in blockers)

    def get_all_blocked_issues(self, status: Optional[str] = None) -> List[Issue]:
        """Get all issues that are currently blocked.

        Args:
            status: Optional filter by status.

        Returns:
            List of Issue objects that have unresolved blockers.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get all issues with dependencies
            query = """
                SELECT DISTINCT i.* FROM issues i
                INNER JOIN issue_dependencies d ON i.id = d.blocked_id
                INNER JOIN issues blocker ON blocker.id = d.blocker_id
                WHERE blocker.status != 'closed'
            """
            params: List[Any] = []

            if status:
                Status.from_string(status)  # Validate status
                query += " AND i.status = ?"
                params.append(status.lower())

            query += """
                ORDER BY
                    CASE i.priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    i.created_at ASC
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_issue(row) for row in rows]

    def _would_create_cycle(self, blocked_id: int, blocker_id: int) -> bool:
        """Check if adding a dependency would create a cycle.

        A cycle would be created if blocker_id is already (transitively)
        blocked by blocked_id.

        Args:
            blocked_id: ID of the issue to be blocked.
            blocker_id: ID of the potential blocker.

        Returns:
            True if adding this dependency would create a cycle.
        """
        # Check if blocker_id is blocked by blocked_id (directly or transitively)
        visited = set()
        to_check = [blocker_id]

        while to_check:
            current = to_check.pop()
            if current in visited:
                continue
            visited.add(current)

            # If we find blocked_id in the blocker chain, we have a cycle
            if current == blocked_id:
                return True

            # Add all blockers of current issue to check
            blockers = self.get_blockers(current)
            for blocker in blockers:
                if blocker.id and blocker.id not in visited:
                    to_check.append(blocker.id)

        return False

    def search_issues_advanced(
        self,
        keyword: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        priorities: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        sort_by: str = "created",
        order: str = "desc",
        limit: Optional[int] = None,
    ) -> List[Issue]:
        """Advanced search for issues with multiple filters and sorting.

        Args:
            keyword: Search keyword for title and description.
            created_after: Issues created after this date (supports relative dates).
            created_before: Issues created before this date (supports relative dates).
            updated_after: Issues updated after this date (supports relative dates).
            updated_before: Issues updated before this date (supports relative dates).
            priorities: List of priority values to filter by.
            statuses: List of status values to filter by.
            sort_by: Field to sort by ('created', 'updated', 'priority').
            order: Sort order ('asc' or 'desc').
            limit: Maximum number of results.

        Returns:
            List of matching issues.

        Raises:
            ValueError: If invalid parameters are provided.
        """
        # Parse date strings
        created_after_dt = parse_date(created_after) if created_after else None
        created_before_dt = parse_date(created_before) if created_before else None
        updated_after_dt = parse_date(updated_after) if updated_after else None
        updated_before_dt = parse_date(updated_before) if updated_before else None

        # Validate date ranges
        validate_date_range(created_after_dt, created_before_dt)
        validate_date_range(updated_after_dt, updated_before_dt)

        # Validate priorities and statuses
        if priorities:
            for p in priorities:
                Priority.from_string(p)  # Will raise ValueError if invalid

        if statuses:
            for s in statuses:
                Status.from_string(s)  # Will raise ValueError if invalid

        # Validate sort parameters
        if sort_by not in ["created", "updated", "priority"]:
            raise ValueError(
                f"Invalid sort_by: {sort_by}. Must be 'created', 'updated', or 'priority'"
            )

        if order not in ["asc", "desc"]:
            raise ValueError(f"Invalid order: {order}. Must be 'asc' or 'desc'")

        # Build query
        query = "SELECT * FROM issues WHERE 1=1"
        params: List[Any] = []

        # Keyword search
        if keyword:
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        # Date filters
        if created_after_dt:
            query += " AND created_at >= ?"
            params.append(created_after_dt.isoformat())

        if created_before_dt:
            query += " AND created_at <= ?"
            params.append(created_before_dt.isoformat())

        if updated_after_dt:
            query += " AND updated_at >= ?"
            params.append(updated_after_dt.isoformat())

        if updated_before_dt:
            query += " AND updated_at <= ?"
            params.append(updated_before_dt.isoformat())

        # Priority filter
        if priorities:
            placeholders = ",".join(["?"] * len(priorities))
            query += f" AND priority IN ({placeholders})"
            params.extend([p.lower() for p in priorities])

        # Status filter
        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            query += f" AND status IN ({placeholders})"
            params.extend([s.lower() for s in statuses])

        # Sorting
        if sort_by == "created":
            query += f" ORDER BY created_at {order.upper()}"
        elif sort_by == "updated":
            query += f" ORDER BY updated_at {order.upper()}"
        elif sort_by == "priority":
            # Custom priority ordering
            if order == "desc":
                query += """
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END ASC
                """
            else:
                query += """
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END DESC
                """

        # Limit
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        # Execute query
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_issue(row) for row in rows]

    def save_search(self, name: str, search_params: Dict[str, Any]) -> int:
        """Save a search query for later reuse.

        Args:
            name: Unique name for the saved search.
            search_params: Dictionary of search parameters.

        Returns:
            ID of the saved search.

        Raises:
            ValueError: If name already exists or is invalid.
        """
        if not name or not name.strip():
            raise ValueError("Search name cannot be empty")

        # Convert params to JSON
        query_json = json.dumps(search_params)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO saved_searches (name, query_json)
                    VALUES (?, ?)
                """,
                    (name.strip(), query_json),
                )
                # lastrowid should never be None after successful INSERT
                return cursor.lastrowid or 0
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError(f"A saved search with name '{name}' already exists") from e
                raise

    def get_saved_search(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a saved search by name.

        Args:
            name: Name of the saved search.

        Returns:
            Dictionary with saved search details, or None if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM saved_searches WHERE name = ?
            """,
                (name,),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "query_params": json.loads(row["query_json"]),
                    "created_at": datetime.fromisoformat(row["created_at"]),
                }
            return None

    def list_saved_searches(self) -> List[Dict[str, Any]]:
        """List all saved searches.

        Returns:
            List of saved search dictionaries.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM saved_searches ORDER BY name ASC
            """
            )
            rows = cursor.fetchall()

            searches = []
            for row in rows:
                searches.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "query_params": json.loads(row["query_json"]),
                        "created_at": datetime.fromisoformat(row["created_at"]),
                    }
                )

            return searches

    def delete_saved_search(self, name: str) -> bool:
        """Delete a saved search.

        Args:
            name: Name of the saved search to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM saved_searches WHERE name = ?", (name,))
            return cursor.rowcount > 0

    def run_saved_search(self, name: str) -> List[Issue]:
        """Execute a saved search.

        Args:
            name: Name of the saved search.

        Returns:
            List of matching issues.

        Raises:
            ValueError: If saved search not found.
        """
        saved_search = self.get_saved_search(name)
        if not saved_search:
            raise ValueError(f"Saved search '{name}' not found")

        # Execute the search with saved parameters
        return self.search_issues_advanced(**saved_search["query_params"])

    # Workspace methods

    def get_active_issue(self) -> Optional[tuple[Issue, datetime]]:
        """Get the currently active issue and when it was started.

        Returns:
            Tuple of (Issue, started_at) if there's an active issue, None otherwise.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT active_issue_id, started_at
                FROM workspace_state
                WHERE id = 1
            """
            )
            row = cursor.fetchone()

            if row and row["active_issue_id"]:
                issue = self.get_issue(row["active_issue_id"])
                if issue:
                    started_at = datetime.fromisoformat(row["started_at"])
                    return (issue, started_at)

            return None

    def start_issue(self, issue_id: int) -> tuple[Issue, datetime]:
        """Set an issue as the active issue and update its status to in-progress.

        Args:
            issue_id: ID of the issue to start.

        Returns:
            Tuple of (Issue, started_at).

        Raises:
            ValueError: If issue not found.
        """
        # Verify issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        started_at = datetime.now()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Initialize workspace_state if not exists
            cursor.execute(
                """
                INSERT OR IGNORE INTO workspace_state (id, active_issue_id, started_at)
                VALUES (1, NULL, NULL)
            """
            )

            # Update workspace_state
            cursor.execute(
                """
                UPDATE workspace_state
                SET active_issue_id = ?, started_at = ?
                WHERE id = 1
            """,
                (issue_id, started_at.isoformat()),
            )

            # Log workspace action in audit log
            self._log_audit(
                conn,
                issue_id,
                "WORKSPACE_START",
                None,
                None,
                started_at.isoformat(),
            )

        # Auto-update issue status to in-progress
        updated_issue = self.update_issue(issue_id, status="in-progress")
        if not updated_issue:
            raise ValueError(f"Failed to update issue {issue_id}")

        return (updated_issue, started_at)

    def stop_issue(self, close: bool = False) -> Optional[tuple[Issue, datetime, datetime]]:
        """Clear the active issue and optionally close it.

        Args:
            close: If True, also set the issue status to closed.

        Returns:
            Tuple of (Issue, started_at, stopped_at) if there was an active issue,
            None otherwise.
        """
        active = self.get_active_issue()
        if not active:
            return None

        issue, started_at = active
        stopped_at = datetime.now()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Clear workspace_state
            cursor.execute(
                """
                UPDATE workspace_state
                SET active_issue_id = NULL, started_at = NULL
                WHERE id = 1
            """
            )

            # Log workspace action in audit log
            assert issue.id is not None
            self._log_audit(
                conn,
                issue.id,
                "WORKSPACE_STOP",
                None,
                started_at.isoformat(),
                stopped_at.isoformat(),
            )

        # Optionally close the issue
        if close and issue.id:
            updated_issue = self.update_issue(issue.id, status="closed")
            if updated_issue:
                issue = updated_issue

        return (issue, started_at, stopped_at)

    def get_workspace_status(self) -> dict[str, Any]:
        """Get comprehensive workspace status including git info and recent activity.

        Returns:
            Dictionary with workspace status information.
        """
        import subprocess
        from pathlib import Path

        status: Dict[str, Any] = {}

        # Get active issue
        active = self.get_active_issue()
        if active:
            issue, started_at = active
            time_spent = datetime.now() - started_at
            hours = int(time_spent.total_seconds() // 3600)
            minutes = int((time_spent.total_seconds() % 3600) // 60)

            status["active_issue"] = {
                "id": issue.id,
                "title": issue.title,
                "status": issue.status.value,
                "priority": issue.priority.value,
                "started_at": started_at.isoformat(),
                "time_spent": f"{hours}h {minutes}m",
                "time_spent_seconds": int(time_spent.total_seconds()),
            }
        else:
            status["active_issue"] = None

        # Get git branch
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=Path.cwd(),
            )
            if result.returncode == 0:
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    cwd=Path.cwd(),
                )
                if branch_result.returncode == 0:
                    status["git_branch"] = branch_result.stdout.strip()

                # Get uncommitted files count
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    cwd=Path.cwd(),
                )
                if status_result.returncode == 0:
                    uncommitted = [
                        line for line in status_result.stdout.split("\n") if line.strip()
                    ]
                    status["uncommitted_files"] = len(uncommitted)
            else:
                status["git_branch"] = None
                status["uncommitted_files"] = None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            status["git_branch"] = None
            status["uncommitted_files"] = None

        # Get recent workspace activity (last 5 start/stop events)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT al.issue_id, al.action, al.new_value, al.timestamp, i.title
                FROM audit_logs al
                LEFT JOIN issues i ON al.issue_id = i.id
                WHERE al.action IN ('WORKSPACE_START', 'WORKSPACE_STOP')
                ORDER BY al.timestamp DESC
                LIMIT 5
            """
            )
            rows = cursor.fetchall()

            recent_activity = []
            for row in rows:
                activity: Dict[str, Any] = {
                    "issue_id": row["issue_id"],
                    "action": row["action"],
                    "timestamp": row["timestamp"],
                }
                if row["title"]:
                    activity["title"] = row["title"]

                # Calculate time ago
                timestamp = datetime.fromisoformat(row["timestamp"])
                time_diff = datetime.now() - timestamp
                if time_diff.days > 0:
                    activity["time_ago"] = f"{time_diff.days}d ago"
                elif time_diff.seconds >= 3600:
                    activity["time_ago"] = f"{time_diff.seconds // 3600}h ago"
                elif time_diff.seconds >= 60:
                    activity["time_ago"] = f"{time_diff.seconds // 60}m ago"
                else:
                    activity["time_ago"] = "just now"

                recent_activity.append(activity)

            status["recent_activity"] = recent_activity

        return status

    # Time Tracking Methods

    def start_timer(self, issue_id: int, note: Optional[str] = None) -> Dict[str, Any]:
        """Start a timer for an issue.

        Args:
            issue_id: ID of the issue to track time for.
            note: Optional note about what work is being done.

        Returns:
            Dictionary with timer information.

        Raises:
            ValueError: If issue not found or timer already running for this issue.
        """
        # Verify issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if there's already a running timer for this issue
            cursor.execute(
                """
                SELECT id FROM time_entries
                WHERE issue_id = ? AND ended_at IS NULL
            """,
                (issue_id,),
            )
            if cursor.fetchone():
                raise ValueError(f"Timer already running for issue {issue_id}")

            # Create new time entry
            started_at = datetime.now()
            cursor.execute(
                """
                INSERT INTO time_entries (issue_id, started_at, note)
                VALUES (?, ?, ?)
            """,
                (issue_id, started_at.isoformat(), note),
            )

            entry_id = cursor.lastrowid

            return {
                "id": entry_id,
                "issue_id": issue_id,
                "started_at": started_at.isoformat(),
                "note": note,
            }

    def stop_timer(self, issue_id: Optional[int] = None) -> Dict[str, Any]:
        """Stop a running timer.

        Args:
            issue_id: Optional issue ID. If not provided, stops the most recent running timer.

        Returns:
            Dictionary with completed timer information including duration.

        Raises:
            ValueError: If no running timer found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Find running timer
            if issue_id:
                cursor.execute(
                    """
                    SELECT * FROM time_entries
                    WHERE issue_id = ? AND ended_at IS NULL
                    ORDER BY started_at DESC
                    LIMIT 1
                """,
                    (issue_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM time_entries
                    WHERE ended_at IS NULL
                    ORDER BY started_at DESC
                    LIMIT 1
                """
                )

            row = cursor.fetchone()
            if not row:
                if issue_id:
                    raise ValueError(f"No running timer found for issue {issue_id}")
                else:
                    raise ValueError("No running timer found")

            # Stop the timer
            ended_at = datetime.now()
            started_at = datetime.fromisoformat(row["started_at"])
            duration_seconds = int((ended_at - started_at).total_seconds())

            cursor.execute(
                """
                UPDATE time_entries
                SET ended_at = ?, duration_seconds = ?
                WHERE id = ?
            """,
                (ended_at.isoformat(), duration_seconds, row["id"]),
            )

            return {
                "id": row["id"],
                "issue_id": row["issue_id"],
                "started_at": row["started_at"],
                "ended_at": ended_at.isoformat(),
                "duration_seconds": duration_seconds,
                "note": row["note"],
            }

    def get_running_timers(self) -> List[Dict[str, Any]]:
        """Get all currently running timers.

        Returns:
            List of dictionaries with running timer information.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT te.*, i.title
                FROM time_entries te
                JOIN issues i ON te.issue_id = i.id
                WHERE te.ended_at IS NULL
                ORDER BY te.started_at DESC
            """
            )
            rows = cursor.fetchall()

            timers = []
            for row in rows:
                started_at = datetime.fromisoformat(row["started_at"])
                elapsed_seconds = int((datetime.now() - started_at).total_seconds())

                timers.append(
                    {
                        "id": row["id"],
                        "issue_id": row["issue_id"],
                        "issue_title": row["title"],
                        "started_at": row["started_at"],
                        "elapsed_seconds": elapsed_seconds,
                        "note": row["note"],
                    }
                )

            return timers

    def get_time_entries(self, issue_id: int) -> List[Dict[str, Any]]:
        """Get all time entries for an issue.

        Args:
            issue_id: ID of the issue.

        Returns:
            List of time entry dictionaries.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM time_entries
                WHERE issue_id = ?
                ORDER BY started_at DESC
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()

            entries = []
            for row in rows:
                entry = {
                    "id": row["id"],
                    "issue_id": row["issue_id"],
                    "started_at": row["started_at"],
                    "ended_at": row["ended_at"],
                    "duration_seconds": row["duration_seconds"],
                    "note": row["note"],
                }
                entries.append(entry)

            return entries

    def set_estimate(self, issue_id: int, hours: float) -> Optional[Issue]:
        """Set time estimate for an issue.

        Args:
            issue_id: ID of the issue.
            hours: Estimated hours to complete the issue.

        Returns:
            Updated Issue object, or None if issue not found.

        Raises:
            ValueError: If hours is negative.
        """
        if hours < 0:
            raise ValueError("Estimated hours must be non-negative")

        # Use a single connection for the entire operation
        with self.db.get_connection() as conn:
            # Get current issue for audit logging
            current_issue = self._get_issue_with_conn(conn, issue_id)
            if not current_issue:
                return None

            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE issues
                SET estimated_hours = ?, updated_at = ?
                WHERE id = ?
            """,
                (hours, datetime.now().isoformat(), issue_id),
            )

            # Log the change in audit log
            old_value = getattr(current_issue, "estimated_hours", None)
            self._log_audit(
                conn,
                issue_id,
                "UPDATE",
                "estimated_hours",
                str(old_value) if old_value is not None else None,
                str(hours),
            )

            return self._get_issue_with_conn(conn, issue_id)

    def get_time_report(
        self, period: str = "all", issue_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate a time report for specified period.

        Args:
            period: Report period - 'week', 'month', or 'all'.
            issue_id: Optional issue ID to filter by specific issue.

        Returns:
            Dictionary with time report data.

        Raises:
            ValueError: If invalid period specified.
        """
        if period not in ["week", "month", "all"]:
            raise ValueError("Period must be 'week', 'month', or 'all'")

        # Calculate date range
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(days=7)
            period_label = "This Week"
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_label = "This Month"
        else:
            start_date = datetime(1970, 1, 1)
            period_label = "All Time"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Build query based on filters
            query = """
                SELECT
                    i.id,
                    i.title,
                    i.estimated_hours,
                    SUM(te.duration_seconds) as total_seconds,
                    COUNT(te.id) as entry_count
                FROM issues i
                LEFT JOIN time_entries te ON i.id = te.issue_id
                WHERE te.ended_at IS NOT NULL
                AND te.started_at >= ?
            """
            params: List[Any] = [start_date.isoformat()]

            if issue_id:
                query += " AND i.id = ?"
                params.append(issue_id)

            query += """
                GROUP BY i.id
                ORDER BY total_seconds DESC
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Process results
            issues = []
            total_seconds = 0

            for row in rows:
                seconds = row["total_seconds"] or 0
                total_seconds += seconds
                hours = seconds / 3600
                estimated_hours = row["estimated_hours"]

                issue_data = {
                    "issue_id": row["id"],
                    "title": row["title"],
                    "total_seconds": seconds,
                    "total_hours": round(hours, 2),
                    "estimated_hours": estimated_hours,
                    "entry_count": row["entry_count"],
                }

                # Calculate if over/under estimate
                if estimated_hours:
                    issue_data["over_estimate"] = hours > estimated_hours
                    issue_data["difference_hours"] = round(hours - estimated_hours, 2)
                else:
                    issue_data["over_estimate"] = None
                    issue_data["difference_hours"] = None

                issues.append(issue_data)

            return {
                "period": period,
                "period_label": period_label,
                "total_seconds": total_seconds,
                "total_hours": round(total_seconds / 3600, 2),
                "issues": issues,
                "issue_count": len(issues),
            }

    # Template management methods

    def create_template(
        self,
        name: str,
        title_prefix: Optional[str] = None,
        default_priority: Optional[str] = None,
        default_status: Optional[str] = None,
        required_fields: Optional[List[str]] = None,
        field_prompts: Optional[Dict[str, str]] = None,
    ) -> IssueTemplate:
        """Create a new issue template.

        Args:
            name: Unique template name.
            title_prefix: Optional prefix to add to issue titles.
            default_priority: Default priority for issues created from template.
            default_status: Default status for issues created from template.
            required_fields: List of required field names.
            field_prompts: Dictionary mapping field names to prompt text.

        Returns:
            Created IssueTemplate object.

        Raises:
            ValueError: If template name already exists or invalid values provided.
        """
        if not name or not name.strip():
            raise ValueError("Template name cannot be empty")

        # Validate priority and status if provided
        if default_priority:
            Priority.from_string(default_priority)  # Will raise if invalid
        if default_status:
            Status.from_string(default_status)  # Will raise if invalid

        # Validate required fields
        if required_fields is None:
            required_fields = []
        valid_fields = {"title", "description", "priority", "status"}
        invalid_fields = [f for f in required_fields if f not in valid_fields]
        if invalid_fields:
            raise ValueError(f"Invalid field names: {', '.join(invalid_fields)}")

        # Create template object
        template = IssueTemplate(
            name=name.strip(),
            title_prefix=title_prefix,
            default_priority=default_priority,
            default_status=default_status,
            required_fields=required_fields,
            field_prompts=field_prompts or {},
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO issue_templates
                    (name, title_prefix, default_priority, default_status,
                     required_fields, field_prompts, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        template.name,
                        template.title_prefix,
                        template.default_priority,
                        template.default_status,
                        json.dumps(template.required_fields),
                        json.dumps(template.field_prompts),
                        template.created_at.isoformat(),
                    ),
                )
                template.id = cursor.lastrowid
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError(f"Template '{name}' already exists") from e
                raise

        return template

    def get_template(self, name: str) -> Optional[IssueTemplate]:
        """Get a template by name.

        Args:
            name: Template name.

        Returns:
            IssueTemplate if found, None otherwise.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM issue_templates WHERE name = ?",
                (name,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_template(row)
            return None

    def list_templates(self) -> List[IssueTemplate]:
        """List all templates.

        Returns:
            List of IssueTemplate objects.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM issue_templates ORDER BY name ASC")
            rows = cursor.fetchall()
            return [self._row_to_template(row) for row in rows]

    def delete_template(self, name: str) -> bool:
        """Delete a template.

        Args:
            name: Template name.

        Returns:
            True if template was deleted, False if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM issue_templates WHERE name = ?",
                (name,),
            )
            return cursor.rowcount > 0

    def validate_against_template(
        self, template: IssueTemplate, issue_data: Dict[str, Any]
    ) -> List[str]:
        """Validate issue data against a template's requirements.

        Args:
            template: The template to validate against.
            issue_data: Dictionary of issue data to validate.

        Returns:
            List of error messages (empty if validation passes).
        """
        errors: List[str] = []

        # Check required fields
        for field in template.required_fields:
            if field not in issue_data or not issue_data[field]:
                # Get custom prompt if available, otherwise generic message
                if field in template.field_prompts:
                    errors.append(f"{field}: {template.field_prompts[field]}")
                else:
                    errors.append(f"{field} is required")

        return errors

    def _row_to_template(self, row: Any) -> IssueTemplate:
        """Convert a database row to an IssueTemplate object.

        Args:
            row: SQLite row object.

        Returns:
            IssueTemplate object.
        """
        # Parse JSON fields
        required_fields = json.loads(row["required_fields"]) if row["required_fields"] else []
        field_prompts = json.loads(row["field_prompts"]) if row["field_prompts"] else {}

        return IssueTemplate(
            id=row["id"],
            name=row["name"],
            title_prefix=row["title_prefix"],
            default_priority=row["default_priority"],
            default_status=row["default_status"],
            required_fields=required_fields,
            field_prompts=field_prompts,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Memory methods

    def add_memory(self, key: str, value: str, category: str = "general") -> Memory:
        """Add a memory item.

        Args:
            key: Unique key.
            value: Value to store.
            category: Category (default: general).

        Returns:
            Created Memory object.

        Raises:
            ValueError: If key already exists.
        """
        memory = Memory(key=key, value=value, category=category)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO memory (key, value, category, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        memory.key,
                        memory.value,
                        memory.category,
                        memory.created_at.isoformat(),
                        memory.updated_at.isoformat(),
                    ),
                )
                memory.id = cursor.lastrowid

                # Log audit
                self._log_audit(
                    conn,
                    0,  # System level
                    "MEMORY_ADD",
                    None,
                    None,
                    json.dumps(memory.to_dict()),
                )
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError(f"Memory with key '{key}' already exists") from e
                raise

        return memory

    def update_memory(
        self, key: str, value: Optional[str] = None, category: Optional[str] = None
    ) -> Optional[Memory]:
        """Update a memory item.

        Args:
            key: Key to identify memory.
            value: New value.
            category: New category.

        Returns:
            Updated Memory object or None if not found.
        """
        current_memory = self.get_memory(key)
        if not current_memory:
            return None

        updates = []
        values = []
        audit_entries = []

        if value is not None and value != current_memory.value:
            updates.append("value = ?")
            values.append(value)
            audit_entries.append(("value", current_memory.value, value))

        if category is not None and category != current_memory.category:
            updates.append("category = ?")
            values.append(category)
            audit_entries.append(("category", current_memory.category, category))

        if not updates:
            return current_memory

        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(key)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = f"UPDATE memory SET {', '.join(updates)} WHERE key = ?"
            cursor.execute(query, values)

            # Log audit
            for field, old_val, new_val in audit_entries:
                self._log_audit(
                    conn,
                    0,
                    "MEMORY_UPDATE",
                    f"{key}:{field}",
                    old_val,
                    new_val,
                )

        return self.get_memory(key)

    def delete_memory(self, key: str) -> bool:
        """Delete a memory item.

        Args:
            key: Key to identify memory.

        Returns:
            True if deleted, False if not found.
        """
        memory = self.get_memory(key)
        if not memory:
            return False

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory WHERE key = ?", (key,))

            # Log audit
            self._log_audit(
                conn,
                0,
                "MEMORY_DELETE",
                None,
                json.dumps(memory.to_dict()),
                None,
            )

            return cursor.rowcount > 0

    def get_memory(self, key: str) -> Optional[Memory]:
        """Get a memory item by key.

        Args:
            key: Key to identify memory.

        Returns:
            Memory object or None.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row:
                return Memory(
                    id=row["id"],
                    key=row["key"],
                    value=row["value"],
                    category=row["category"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
        return None

    def list_memory(
        self, category: Optional[str] = None, search: Optional[str] = None
    ) -> List[Memory]:
        """List memory items.


        Args:

            category: Filter by category.

            search: Search in key or value.



        Returns:

            List of Memory objects.

        """

        query = "SELECT * FROM memory WHERE 1=1"

        params: List[Any] = []

        if category:
            query += " AND category = ?"

            params.append(category)

        if search:
            query += " AND (key LIKE ? OR value LIKE ?)"

            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY key ASC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(query, params)

            rows = cursor.fetchall()

            return [
                Memory(
                    id=row["id"],
                    key=row["key"],
                    value=row["value"],
                    category=row["category"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    # Lessons Learned methods

    def add_lesson(
        self, lesson: str, issue_id: Optional[int] = None, category: str = "general"
    ) -> LessonLearned:
        """Add a lesson learned.

        Args:
            lesson: The lesson text.
            issue_id: Related issue ID (optional).
            category: Category (default: general).

        Returns:
            Created LessonLearned object.
        """
        # Verify issue if provided
        if issue_id:
            issue = self.get_issue(issue_id)
            if not issue:
                raise ValueError(f"Issue {issue_id} not found")

        ll = LessonLearned(issue_id=issue_id, lesson=lesson, category=category)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO lessons_learned (issue_id, lesson, category, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (
                    ll.issue_id,
                    ll.lesson,
                    ll.category,
                    ll.created_at.isoformat(),
                ),
            )
            ll.id = cursor.lastrowid

            # Log audit
            self._log_audit(
                conn,
                issue_id if issue_id else 0,
                "LESSON_ADD",
                None,
                None,
                json.dumps(ll.to_dict()),
            )

        return ll

    def update_lesson(
        self, lesson_id: int, lesson: Optional[str] = None, category: Optional[str] = None
    ) -> Optional[LessonLearned]:
        """Update a lesson learned.

        Args:
            lesson_id: ID of the lesson.
            lesson: New lesson text.
            category: New category.

        Returns:
            Updated LessonLearned object or None.
        """
        current_lesson = self.get_lesson(lesson_id)
        if not current_lesson:
            return None

        updates = []
        values: List[Any] = []
        audit_entries = []

        if lesson is not None and lesson != current_lesson.lesson:
            updates.append("lesson = ?")
            values.append(lesson)
            audit_entries.append(("lesson", current_lesson.lesson, lesson))

        if category is not None and category != current_lesson.category:
            updates.append("category = ?")
            values.append(category)
            audit_entries.append(("category", current_lesson.category, category))

        if not updates:
            return current_lesson

        values.append(lesson_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = f"UPDATE lessons_learned SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)

            # Log audit
            for field, old_val, new_val in audit_entries:
                self._log_audit(
                    conn,
                    current_lesson.issue_id if current_lesson.issue_id else 0,
                    "LESSON_UPDATE",
                    f"lesson:{lesson_id}:{field}",
                    old_val,
                    new_val,
                )

        return self.get_lesson(lesson_id)

    def delete_lesson(self, lesson_id: int) -> bool:
        """Delete a lesson learned.

        Args:
            lesson_id: ID of the lesson.

        Returns:
            True if deleted.
        """
        current_lesson = self.get_lesson(lesson_id)
        if not current_lesson:
            return False

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lessons_learned WHERE id = ?", (lesson_id,))

            # Log audit
            self._log_audit(
                conn,
                current_lesson.issue_id if current_lesson.issue_id else 0,
                "LESSON_DELETE",
                None,
                json.dumps(current_lesson.to_dict()),
                None,
            )

            return cursor.rowcount > 0

    def get_lesson(self, lesson_id: int) -> Optional[LessonLearned]:
        """Get a lesson learned by ID.

        Args:
            lesson_id: ID of the lesson.

        Returns:
            LessonLearned object or None.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lessons_learned WHERE id = ?", (lesson_id,))
            row = cursor.fetchone()

            if row:
                return LessonLearned(
                    id=row["id"],
                    issue_id=row["issue_id"],
                    lesson=row["lesson"],
                    category=row["category"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            return None

    def list_lessons(
        self, issue_id: Optional[int] = None, category: Optional[str] = None
    ) -> List[LessonLearned]:
        """List lessons learned.

        Args:
            issue_id: Filter by issue ID.
            category: Filter by category.

        Returns:
            List of LessonLearned objects.
        """
        query = "SELECT * FROM lessons_learned WHERE 1=1"
        params: List[Any] = []

        if issue_id:
            query += " AND issue_id = ?"
            params.append(issue_id)

        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [
                LessonLearned(
                    id=row["id"],
                    issue_id=row["issue_id"],
                    lesson=row["lesson"],
                    category=row["category"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    # Tag methods

    def create_tag(self, name: str, color: Optional[str] = None) -> Tag:
        """Create a new tag.

        Args:
            name: Tag name.
            color: Hex color (optional).

        Returns:
            Created Tag object.
        """
        tag = Tag(name=name, color=color)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO tags (name, color, created_at) VALUES (?, ?, ?)",
                    (tag.name, tag.color, tag.created_at.isoformat()),
                )
                tag.id = cursor.lastrowid

                # Log audit (global)
                self._log_audit(
                    conn,
                    0,
                    "TAG_CREATE",
                    None,
                    None,
                    json.dumps(tag.to_dict()),
                )
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError(f"Tag '{name}' already exists") from e
                raise

        return tag

    def list_tags(self) -> List[Tag]:
        """List all tags.

        Returns:
            List of Tag objects.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tags ORDER BY name ASC")
            rows = cursor.fetchall()
            return [
                Tag(
                    id=row["id"],
                    name=row["name"],
                    color=row["color"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    def add_issue_tag(self, issue_id: int, tag_name: str) -> bool:
        """Add a tag to an issue. Creates the tag if it doesn't exist.

        Args:
            issue_id: Issue ID.
            tag_name: Tag name.

        Returns:
            True if tag was added, False if already present.
        """
        # Ensure tag exists
        with contextlib.suppress(ValueError):
            self.create_tag(tag_name)

        # Get tag ID
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_row = cursor.fetchone()
            if not tag_row:
                raise ValueError(f"Tag {tag_name} not found")
            tag_id = tag_row["id"]

            try:
                cursor.execute(
                    "INSERT INTO issue_tags (issue_id, tag_id, created_at) VALUES (?, ?, ?)",
                    (issue_id, tag_id, datetime.now().isoformat()),
                )

                # Log audit
                self._log_audit(
                    conn,
                    issue_id,
                    "TAG_ADD",
                    "tag",
                    None,
                    tag_name,
                )
                return True
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    return False
                raise

    def remove_issue_tag(self, issue_id: int, tag_name: str) -> bool:
        """Remove a tag from an issue.

        Args:
            issue_id: Issue ID.
            tag_name: Tag name.

        Returns:
            True if removed.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM issue_tags
                WHERE issue_id = ? AND tag_id IN (SELECT id FROM tags WHERE name = ?)
            """,
                (issue_id, tag_name),
            )

            if cursor.rowcount > 0:
                # Log audit
                self._log_audit(
                    conn,
                    issue_id,
                    "TAG_REMOVE",
                    "tag",
                    tag_name,
                    None,
                )
                return True
            return False

    def _get_issue_tags_with_conn(self, conn: Any, issue_id: int) -> List[Tag]:
        """Get tags for an issue using an existing connection.

        Args:
            conn: Database connection to use.
            issue_id: Issue ID.

        Returns:
            List of Tag objects.

        Note:
            Internal method to avoid nested connections.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.* FROM tags t
            JOIN issue_tags it ON t.id = it.tag_id
            WHERE it.issue_id = ?
            ORDER BY t.name ASC
        """,
            (issue_id,),
        )
        rows = cursor.fetchall()
        return [
            Tag(
                id=row["id"],
                name=row["name"],
                color=row["color"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def get_issue_tags(self, issue_id: int) -> List[Tag]:
        """Get tags for an issue.

        Args:
            issue_id: Issue ID.

        Returns:
            List of Tag objects.
        """
        with self.db.get_connection() as conn:
            return self._get_issue_tags_with_conn(conn, issue_id)

    # Issue Relation methods

    def link_issues(self, source_id: int, target_id: int, relation_type: str) -> IssueRelation:
        """Link two issues.

        Args:
            source_id: Source issue ID.
            target_id: Target issue ID.
            relation_type: Type of relation (e.g., "relates_to", "duplicates").

        Returns:
            Created IssueRelation object.
        """
        if source_id == target_id:
            raise ValueError("Cannot link issue to itself")

        relation = IssueRelation(
            source_issue_id=source_id,
            target_issue_id=target_id,
            relation_type=relation_type,
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO issue_relations
                    (source_issue_id, target_issue_id, relation_type, created_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        relation.source_issue_id,
                        relation.target_issue_id,
                        relation.relation_type,
                        relation.created_at.isoformat(),
                    ),
                )
                relation.id = cursor.lastrowid

                # Log audit on both issues
                self._log_audit(
                    conn,
                    source_id,
                    "LINK_ADD",
                    "relation",
                    None,
                    f"{relation_type} -> #{target_id}",
                )
                self._log_audit(
                    conn,
                    target_id,
                    "LINK_ADD",
                    "relation",
                    None,
                    f"#{source_id} -> {relation_type}",
                )
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError("Relation already exists") from e
                raise

        return relation

    def unlink_issues(
        self, source_id: int, target_id: int, relation_type: Optional[str] = None
    ) -> bool:
        """Remove link between issues.

        Args:
            source_id: Source issue ID.
            target_id: Target issue ID.
            relation_type: Optional type to filter.

        Returns:
            True if removed.
        """
        query = "DELETE FROM issue_relations WHERE source_issue_id = ? AND target_issue_id = ?"
        params: List[Any] = [source_id, target_id]

        if relation_type:
            query += " AND relation_type = ?"
            params.append(relation_type)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            if cursor.rowcount > 0:
                # Log audit on both
                self._log_audit(
                    conn,
                    source_id,
                    "LINK_REMOVE",
                    "relation",
                    f"#{target_id}",
                    None,
                )
                self._log_audit(
                    conn,
                    target_id,
                    "LINK_REMOVE",
                    "relation",
                    f"#{source_id}",
                    None,
                )
                return True
            return False

    def get_issue_relations(self, issue_id: int) -> Dict[str, List[dict[str, Any]]]:
        """Get all relations for an issue.

        Args:
            issue_id: Issue ID.

        Returns:
            Dictionary with 'source' and 'target' relations.
        """
        result: Dict[str, List[dict[str, Any]]] = {"source": [], "target": []}

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get relations where issue is source
            cursor.execute(
                """
                SELECT r.*, i.title, i.status
                FROM issue_relations r
                JOIN issues i ON r.target_issue_id = i.id
                WHERE r.source_issue_id = ?
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()
            for row in rows:
                result["source"].append(
                    {
                        "id": row["id"],
                        "target_id": row["target_issue_id"],
                        "target_title": row["title"],
                        "target_status": row["status"],
                        "type": row["relation_type"],
                        "created_at": row["created_at"],
                    }
                )

            # Get relations where issue is target
            cursor.execute(
                """
                SELECT r.*, i.title, i.status
                FROM issue_relations r
                JOIN issues i ON r.source_issue_id = i.id
                WHERE r.target_issue_id = ?
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()
            for row in rows:
                result["target"].append(
                    {
                        "id": row["id"],
                        "source_id": row["source_issue_id"],
                        "source_title": row["title"],
                        "source_status": row["status"],
                        "type": row["relation_type"],
                        "created_at": row["created_at"],
                    }
                )

        return result
