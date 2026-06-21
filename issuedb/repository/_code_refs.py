"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import contextlib
import os
from datetime import datetime
from typing import TYPE_CHECKING

from issuedb.models import (
    CodeReference,
    Issue,
)

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def parse_file_spec(self: IssueRepository, file_spec: str) -> tuple[str, int | None, int | None]:
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

    start_line: int | None = None
    end_line: int | None = None

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
    self: IssueRepository,
    issue_id: int,
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    note: str | None = None,
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
    self: IssueRepository,
    issue_id: int,
    file_path: str | None = None,
    reference_id: int | None = None,
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


def get_code_references(self: IssueRepository, issue_id: int) -> list[CodeReference]:
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


def get_issues_by_file(self: IssueRepository, file_path: str) -> list[Issue]:
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
