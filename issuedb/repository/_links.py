"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from issuedb.models import (
    IssueRelation,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def link_issues(
    self: IssueRepository, source_id: int, target_id: int, relation_type: str
) -> IssueRelation:
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
    self: IssueRepository, source_id: int, target_id: int, relation_type: str | None = None
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
    params: list[Any] = [source_id, target_id]

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


def get_issue_relations(self: IssueRepository, issue_id: int) -> dict[str, list[dict[str, Any]]]:
    """Get all relations for an issue.

    Args:
        issue_id: Issue ID.

    Returns:
        Dictionary with 'source' and 'target' relations.
    """
    result: dict[str, list[dict[str, Any]]] = {"source": [], "target": []}

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
