"""Git link repository methods for IssueDB."""

from datetime import datetime
from typing import Any, List, Optional

from issuedb.database import get_database
from issuedb.models import Issue, IssueLink, Priority, Status


class GitLinkRepository:
    """Handles git link-related database operations."""

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
        """Log an audit entry for a link change.

        Args:
            conn: Database connection to use
            issue_id: ID of the affected issue
            action: Action type (LINK_ADD, LINK_REMOVE)
            field_name: Name of the field (link_type)
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
                return Issue(
                    id=row["id"],
                    title=row["title"],
                    description=row["description"],
                    priority=Priority.from_string(row["priority"]),
                    status=Status.from_string(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            return None

    def add_link(self, issue_id: int, link_type: str, reference: str) -> Optional[IssueLink]:
        """Add a git link (commit or branch) to an issue.

        Args:
            issue_id: ID of the issue to link.
            link_type: Type of link ('commit' or 'branch').
            reference: Commit hash or branch name.

        Returns:
            Created IssueLink object, or None if issue not found.

        Raises:
            ValueError: If link_type is invalid or link already exists.
        """
        # Validate link type
        if link_type not in ("commit", "branch"):
            raise ValueError(f"Invalid link_type: {link_type}. Must be 'commit' or 'branch'")

        # Verify issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            return None

        # Check if link already exists
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM issue_links
                WHERE issue_id = ? AND link_type = ? AND reference = ?
            """,
                (issue_id, link_type, reference),
            )
            if cursor.fetchone():
                raise ValueError(
                    f"Link already exists: issue {issue_id} -> {link_type} {reference}"
                )

            # Create the link
            link = IssueLink(
                issue_id=issue_id,
                link_type=link_type,
                reference=reference,
            )

            cursor.execute(
                """
                INSERT INTO issue_links (issue_id, link_type, reference, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (
                    link.issue_id,
                    link.link_type,
                    link.reference,
                    link.created_at.isoformat(),
                ),
            )

            link.id = cursor.lastrowid

            # Log in audit log
            self._log_audit(
                conn,
                issue_id,
                "LINK_ADD",
                link_type,
                None,
                reference,
            )

            return link

    def remove_link(
        self, issue_id: int, link_type: Optional[str] = None, reference: Optional[str] = None
    ) -> int:
        """Remove git link(s) from an issue.

        Args:
            issue_id: ID of the issue.
            link_type: Optional type filter ('commit' or 'branch').
            reference: Optional reference filter (commit hash or branch name).

        Returns:
            Number of links removed.

        Raises:
            ValueError: If neither link_type nor reference is provided.
        """
        if link_type is None and reference is None:
            raise ValueError("Must specify at least one of: link_type or reference")

        # Build query based on filters
        query = "DELETE FROM issue_links WHERE issue_id = ?"
        params: List[Any] = [issue_id]

        if link_type:
            if link_type not in ("commit", "branch"):
                raise ValueError(f"Invalid link_type: {link_type}. Must be 'commit' or 'branch'")
            query += " AND link_type = ?"
            params.append(link_type)

        if reference:
            query += " AND reference = ?"
            params.append(reference)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get links before deletion for audit logging
            select_query = query.replace("DELETE FROM", "SELECT * FROM")
            cursor.execute(select_query, params)
            deleted_links = cursor.fetchall()

            # Delete links
            cursor.execute(query, params)
            count = cursor.rowcount

            # Log in audit log
            for link in deleted_links:
                self._log_audit(
                    conn,
                    issue_id,
                    "LINK_REMOVE",
                    link["link_type"],
                    link["reference"],
                    None,
                )

            return count

    def get_links(self, issue_id: int) -> List[IssueLink]:
        """Get all git links for an issue.

        Args:
            issue_id: ID of the issue.

        Returns:
            List of IssueLink objects.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM issue_links
                WHERE issue_id = ?
                ORDER BY created_at DESC
            """,
                (issue_id,),
            )
            rows = cursor.fetchall()

            links = []
            for row in rows:
                link = IssueLink(
                    id=row["id"],
                    issue_id=row["issue_id"],
                    link_type=row["link_type"],
                    reference=row["reference"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                links.append(link)

            return links

    def get_issues_by_link(
        self, link_type: Optional[str] = None, reference: Optional[str] = None
    ) -> List[Issue]:
        """Get issues linked to a commit or branch.

        Args:
            link_type: Optional type filter ('commit' or 'branch').
            reference: Optional reference filter (commit hash or branch name).

        Returns:
            List of Issue objects.

        Raises:
            ValueError: If neither link_type nor reference is provided.
        """
        if link_type is None and reference is None:
            raise ValueError("Must specify at least one of: link_type or reference")

        # Build query based on filters
        query = """
            SELECT DISTINCT i.* FROM issues i
            INNER JOIN issue_links il ON i.id = il.issue_id
            WHERE 1=1
        """
        params: List[Any] = []

        if link_type:
            if link_type not in ("commit", "branch"):
                raise ValueError(f"Invalid link_type: {link_type}. Must be 'commit' or 'branch'")
            query += " AND il.link_type = ?"
            params.append(link_type)

        if reference:
            query += " AND il.reference = ?"
            params.append(reference)

        query += " ORDER BY i.created_at DESC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            issues = []
            for row in rows:
                issue = Issue(
                    id=row["id"],
                    title=row["title"],
                    description=row["description"],
                    priority=Priority.from_string(row["priority"]),
                    status=Status.from_string(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                issues.append(issue)

            return issues

    def scan_commits_and_close_issues(
        self, commits: List[dict[str, Any]], auto_close: bool = True
    ) -> dict[str, Any]:
        """Scan commits for issue references and optionally auto-close issues.

        Args:
            commits: List of commit dicts with 'hash' and 'message' keys.
            auto_close: If True, auto-close issues referenced with closing keywords.

        Returns:
            Dictionary with scan results: {
                'scanned': int,
                'links_created': int,
                'issues_closed': int,
                'details': list of dicts
            }
        """
        from issuedb.git_utils import parse_close_refs, parse_issue_refs
        from issuedb.repository import IssueRepository

        repo = IssueRepository(str(self.db.db_path) if self.db.db_path else None)

        scanned = 0
        links_created = 0
        issues_closed = 0
        details = []

        for commit in commits:
            commit_hash = commit.get("hash", "")
            message = commit.get("message", "")

            if not commit_hash or not message:
                continue

            scanned += 1

            # Parse issue references
            issue_refs = parse_issue_refs(message)
            close_refs = parse_close_refs(message)

            for issue_id in issue_refs:
                # Check if issue exists
                issue = self.get_issue(issue_id)
                if not issue:
                    details.append(
                        {
                            "commit": commit_hash,
                            "issue_id": issue_id,
                            "action": "skipped",
                            "reason": "issue not found",
                        }
                    )
                    continue

                # Add link if doesn't exist
                try:
                    link = self.add_link(issue_id, "commit", commit_hash)
                    if link:
                        links_created += 1
                        details.append(
                            {
                                "commit": commit_hash,
                                "issue_id": issue_id,
                                "action": "linked",
                                "link_id": link.id,
                            }
                        )
                except ValueError:
                    # Link already exists, skip
                    details.append(
                        {
                            "commit": commit_hash,
                            "issue_id": issue_id,
                            "action": "skipped",
                            "reason": "link already exists",
                        }
                    )

                # Auto-close if in close_refs and auto_close is True
                if auto_close and issue_id in close_refs and issue.status.value != "closed":
                    repo.update_issue(issue_id, status="closed")
                    issues_closed += 1
                    details.append(
                        {
                            "commit": commit_hash,
                            "issue_id": issue_id,
                            "action": "closed",
                        }
                    )

        return {
            "scanned": scanned,
            "links_created": links_created,
            "issues_closed": issues_closed,
            "details": details,
        }
