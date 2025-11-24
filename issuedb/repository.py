"""Repository layer for issue CRUD operations."""

import json
from datetime import datetime
from typing import List, Optional

from issuedb.database import get_database
from issuedb.models import AuditLog, Issue, Priority, Status


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
        conn,
        issue_id: int,
        action: str,
        project: str,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> None:
        """Log an audit entry for an issue change.

        Args:
            conn: Database connection to use
            issue_id: ID of the affected issue
            action: Action type (CREATE, UPDATE, DELETE)
            project: Project name
            field_name: Name of the field that changed
            old_value: Previous value
            new_value: New value
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (issue_id, action, field_name, old_value, new_value, project)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (issue_id, action, field_name, old_value, new_value, project),
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
        if not issue.project:
            raise ValueError("Project is required")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO issues (title, project, description, priority, status,
                                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    issue.title,
                    issue.project,
                    issue.description,
                    issue.priority.value,
                    issue.status.value,
                    issue.created_at,
                    issue.updated_at,
                ),
            )

            issue.id = cursor.lastrowid

            # Log creation in audit log
            self._log_audit(
                conn,
                issue.id,
                "CREATE",
                issue.project,
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

    def update_issue(self, issue_id: int, **updates) -> Optional[Issue]:
        """Update an issue.

        Args:
            issue_id: ID of the issue to update.
            **updates: Fields to update (title, project, description, priority, status).

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
        allowed_fields = {"title", "project", "description", "priority", "status"}
        update_fields = []
        update_values = []
        audit_entries = []

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
        update_values.append(datetime.now())

        # Add issue_id for WHERE clause
        update_values.append(issue_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = f"UPDATE issues SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, update_values)

            # Log each field change in audit log
            for field, old_val, new_val in audit_entries:
                self._log_audit(
                    conn,
                    issue_id,
                    "UPDATE",
                    current_issue.project,
                    field,
                    old_val,
                    new_val,
                )

        return self.get_issue(issue_id)

    def bulk_update_issues(
        self,
        new_status: Optional[str] = None,
        new_priority: Optional[str] = None,
        filter_project: Optional[str] = None,
        filter_status: Optional[str] = None,
        filter_priority: Optional[str] = None,
    ) -> int:
        """Bulk update issues matching filters.

        Args:
            new_status: New status to set.
            new_priority: New priority to set.
            filter_project: Filter by project name.
            filter_status: Filter by current status.
            filter_priority: Filter by current priority.

        Returns:
            Number of issues updated.

        Raises:
            ValueError: If invalid field names or values are provided.
        """
        update_fields = []
        update_values = []

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
        update_values.append(datetime.now())

        # Build WHERE clause for filters
        where_conditions = []
        where_values = []
        if filter_project:
            where_conditions.append("project = ?")
            where_values.append(filter_project)
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
                if new_status:
                    old_value = issue.status.value
                    new_value = Status.from_string(new_status).value
                    if old_value != new_value:
                        self._log_audit(
                            conn,
                            issue.id,
                            "BULK_UPDATE",
                            issue.project,
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
                            issue.project,
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
                issue.project,
                None,
                json.dumps(issue.to_dict()),
                None,
            )

            return cursor.rowcount > 0

    def list_issues(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Issue]:
        """List issues with optional filters.

        Args:
            project: Filter by project name.
            status: Filter by status.
            priority: Filter by priority.
            limit: Maximum number of issues to return.
            offset: Number of issues to skip.

        Returns:
            List of matching issues.
        """
        query = "SELECT * FROM issues WHERE 1=1"
        params = []

        if project:
            query += " AND project = ?"
            params.append(project)

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
        self, project: Optional[str] = None, status: Optional[str] = None
    ) -> Optional[Issue]:
        """Get the next issue based on priority and creation date (FIFO within priority).

        Args:
            project: Filter by project name.
            status: Filter by status (defaults to 'open' if not specified).

        Returns:
            Next Issue to work on, or None if no issues match.
        """
        query = """
            SELECT * FROM issues
            WHERE 1=1
        """
        params = []

        if project:
            query += " AND project = ?"
            params.append(project)

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
        self, keyword: str, project: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Issue]:
        """Search issues by keyword in title and description.

        Args:
            keyword: Keyword to search for.
            project: Filter by project name.
            limit: Maximum number of issues to return.

        Returns:
            List of matching issues.
        """
        query = """
            SELECT * FROM issues
            WHERE (title LIKE ? OR description LIKE ?)
        """
        params = [f"%{keyword}%", f"%{keyword}%"]

        if project:
            query += " AND project = ?"
            params.append(project)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_issue(row) for row in rows]

    def clear_project(self, project: str) -> int:
        """Clear all issues for a project.

        Args:
            project: Project name.

        Returns:
            Number of issues deleted.
        """
        # Get all issues for audit logging
        issues = self.list_issues(project=project)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Log deletion for each issue
            for issue in issues:
                self._log_audit(
                    conn,
                    issue.id,
                    "DELETE",
                    issue.project,
                    None,
                    json.dumps(issue.to_dict()),
                    None,
                )

            # Delete all issues for the project
            cursor.execute("DELETE FROM issues WHERE project = ?", (project,))
            return cursor.rowcount

    def get_audit_logs(
        self, issue_id: Optional[int] = None, project: Optional[str] = None
    ) -> List[AuditLog]:
        """Get audit logs for issues.

        Args:
            issue_id: Filter by issue ID.
            project: Filter by project.

        Returns:
            List of audit log entries.
        """
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if issue_id:
            query += " AND issue_id = ?"
            params.append(issue_id)

        if project:
            query += " AND project = ?"
            params.append(project)

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
                    project=row["project"],
                )
                logs.append(log)

            return logs

    def get_summary(self, project: Optional[str] = None) -> dict:
        """Get summary statistics of issues.

        Args:
            project: Optional project name to filter by.

        Returns:
            Dictionary with issue statistics including counts by status and priority.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            where_clause = "WHERE project = ?" if project else ""
            params = [project] if project else []

            # Get total count
            query = f"SELECT COUNT(*) as count FROM issues {where_clause}"
            cursor.execute(query, params)
            total_count = cursor.fetchone()["count"]

            # Get count by status
            query = f"""
                SELECT status, COUNT(*) as count
                FROM issues {where_clause}
                GROUP BY status
            """
            cursor.execute(query, params)
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Get count by priority
            query = f"""
                SELECT priority, COUNT(*) as count
                FROM issues {where_clause}
                GROUP BY priority
            """
            cursor.execute(query, params)
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
                "project": project,
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

    def get_report(self, project: Optional[str] = None, group_by: str = "status") -> dict:
        """Get detailed report of issues grouped by status or priority.

        Args:
            project: Optional project name to filter by.
            group_by: Group issues by 'status' or 'priority' (default: 'status').

        Returns:
            Dictionary with grouped issue lists.
        """
        if group_by not in ["status", "priority"]:
            raise ValueError("group_by must be 'status' or 'priority'")

        # Get all issues filtered by project
        issues = self.list_issues(project=project)

        # Group issues
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
        result = {
            "project": project,
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

    def _row_to_issue(self, row) -> Issue:
        """Convert a database row to an Issue object.

        Args:
            row: SQLite row object.

        Returns:
            Issue object.
        """
        return Issue(
            id=row["id"],
            title=row["title"],
            project=row["project"],
            description=row["description"],
            priority=Priority.from_string(row["priority"]),
            status=Status.from_string(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
