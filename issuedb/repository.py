"""Repository layer for issue CRUD operations."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from issuedb.database import get_database
from issuedb.models import AuditLog, Comment, Issue, Priority, Status


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
                "CREATE",
                None,
                None,
                json.dumps(issue.to_dict()),
            )

        return issue

    def get_issue(self, issue_id: int) -> Optional[Issue]:
        """Get an issue by ID.

        Args:
            issue_id: ID of the issue to retrieve.

        Returns:
            Issue if found, None otherwise.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM issues WHERE id = ?
            """,
                (issue_id,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_issue(row)
            return None

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
        # Get current issue for audit logging
        current_issue = self.get_issue(issue_id)
        if not current_issue:
            return None

        # Validate and prepare updates
        allowed_fields = {"title", "description", "priority", "status"}
        update_fields: List[str] = []
        update_values: List[Any] = []
        audit_entries: List[tuple[str, str, str]] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                raise ValueError(f"Cannot update field: {field}")

            # Validate and convert enums
            if field == "priority":
                value = Priority.from_string(value).value
                old_value = current_issue.priority.value
            elif field == "status":
                value = Status.from_string(value).value
                old_value = current_issue.status.value
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

        with self.db.get_connection() as conn:
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

        return self.get_issue(issue_id)

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
        # Get issue details for audit log before deletion
        issue = self.get_issue(issue_id)
        if not issue:
            return False

        with self.db.get_connection() as conn:
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

    def list_issues(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Issue]:
        """List issues with optional filters.

        Args:
            status: Filter by status.
            priority: Filter by priority.
            limit: Maximum number of issues to return.
            offset: Number of issues to skip.

        Returns:
            List of matching issues.
        """
        query = "SELECT * FROM issues WHERE 1=1"
        params: List[Any] = []

        if status:
            Status.from_string(status)  # Validate status
            query += " AND status = ?"
            params.append(status.lower())

        if priority:
            Priority.from_string(priority)  # Validate priority
            query += " AND priority = ?"
            params.append(priority.lower())

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

    def get_next_issue(
        self, status: Optional[str] = None
    ) -> Optional[Issue]:
        """Get the next issue based on priority and creation date (FIFO within priority).

        Args:
            status: Filter by status (defaults to 'open' if not specified).

        Returns:
            Next Issue to work on, or None if no issues match.
        """
        query = """
            SELECT * FROM issues
            WHERE 1=1
        """
        params = []

        # Default to open issues if status not specified
        if status:
            Status.from_string(status)  # Validate status
            query += " AND status = ?"
            params.append(status.lower())
        else:
            query += " AND status = ?"
            params.append(Status.OPEN.value)

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
                return self._row_to_issue(row)
            return None

    def search_issues(
        self, keyword: str, limit: Optional[int] = None
    ) -> List[Issue]:
        """Search issues by keyword in title and description.

        Args:
            keyword: Keyword to search for.
            limit: Maximum number of issues to return.

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

    def get_audit_logs(
        self, issue_id: Optional[int] = None
    ) -> List[AuditLog]:
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

    def get_summary(self) -> dict:
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
                for status in ["open", "in-progress", "closed"]:
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

    def get_report(self, group_by: str = "status") -> dict:
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

    def bulk_create_issues(self, issues_data: List[dict]) -> List[Issue]:
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

    def bulk_update_issues_from_json(self, updates_data: List[dict]) -> List[Issue]:
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

    def _row_to_issue(self, row: Any) -> Issue:
        """Convert a database row to an Issue object.

        Args:
            row: SQLite row object.

        Returns:
            Issue object.
        """
        return Issue(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=Priority.from_string(row["priority"]),
            status=Status.from_string(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
