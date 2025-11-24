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
