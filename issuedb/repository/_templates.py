"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import (
    IssueTemplate,
    Priority,
    Status,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def create_template(
    self: IssueRepository,
    name: str,
    title_prefix: str | None = None,
    default_priority: str | None = None,
    default_status: str | None = None,
    required_fields: list[str] | None = None,
    field_prompts: dict[str, str] | None = None,
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


def get_template(self: IssueRepository, name: str) -> IssueTemplate | None:
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


def list_templates(self: IssueRepository) -> list[IssueTemplate]:
    """List all templates.

    Returns:
        List of IssueTemplate objects.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM issue_templates ORDER BY name ASC")
        rows = cursor.fetchall()
        return [self._row_to_template(row) for row in rows]


def delete_template(self: IssueRepository, name: str) -> bool:
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
    self: IssueRepository, template: IssueTemplate, issue_data: dict[str, Any]
) -> list[str]:
    """Validate issue data against a template's requirements.

    Args:
        template: The template to validate against.
        issue_data: Dictionary of issue data to validate.

    Returns:
        List of error messages (empty if validation passes).
    """
    errors: list[str] = []

    # Check required fields
    for field in template.required_fields:
        if field not in issue_data or not issue_data[field]:
            # Get custom prompt if available, otherwise generic message
            if field in template.field_prompts:
                errors.append(f"{field}: {template.field_prompts[field]}")
            else:
                errors.append(f"{field} is required")

    return errors


def _row_to_template(self: IssueRepository, row: Any) -> IssueTemplate:
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
