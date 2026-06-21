"""Code reference CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def attach_code_reference(
    self: CLI,
    issue_id: int,
    file_spec: str,
    note: str | None = None,
    as_json: bool = False,
) -> str:
    """Attach a code reference to an issue.

    Args:
        issue_id: ID of the issue.
        file_spec: File path with optional line number (e.g., "file.py:10" or "file.py:10-20").
        note: Optional note about the reference.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    # Parse file spec
    file_path, start_line, end_line = self.repo.parse_file_spec(file_spec)

    ref = self.repo.add_code_reference(
        issue_id=issue_id,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        note=note,
    )

    if as_json:
        return json.dumps(ref.to_dict(), indent=2)
    else:
        lines = ["Code reference added:"]
        lines.append(f"  Issue: #{issue_id}")
        lines.append(f"  File: {ref.file_path}")
        if ref.start_line and ref.end_line:
            lines.append(f"  Lines: {ref.start_line}-{ref.end_line}")
        elif ref.start_line:
            lines.append(f"  Line: {ref.start_line}")
        if ref.note:
            lines.append(f"  Note: {ref.note}")
        return "\n".join(lines)


def detach_code_reference(
    self: CLI,
    issue_id: int,
    file_path: str | None = None,
    reference_id: int | None = None,
    as_json: bool = False,
) -> str:
    """Detach a code reference from an issue.

    Args:
        issue_id: ID of the issue.
        file_path: File path to remove references for.
        reference_id: Specific reference ID to remove.
        as_json: Output as JSON.

    Returns:
        Formatted output.

    Raises:
        ValueError: If neither file_path nor reference_id provided.
    """
    if not file_path and not reference_id:
        raise ValueError("Must provide --file or --reference-id")

    count = self.repo.remove_code_reference(
        issue_id=issue_id,
        file_path=file_path,
        reference_id=reference_id,
    )

    if as_json:
        return json.dumps({"removed_count": count}, indent=2)
    else:
        return f"Removed {count} code reference(s) from issue #{issue_id}"


def list_code_references(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """List all code references for an issue.

    Args:
        issue_id: ID of the issue.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    refs = self.repo.get_code_references(issue_id)

    if as_json:
        return json.dumps([ref.to_dict() for ref in refs], indent=2)
    else:
        if not refs:
            return "No code references found."

        lines = [f"Code references for issue #{issue_id}:"]
        for ref in refs:
            lines.append(f"\n  File: {ref.file_path}")
            if ref.start_line and ref.end_line:
                lines.append(f"  Lines: {ref.start_line}-{ref.end_line}")
            elif ref.start_line:
                lines.append(f"  Line: {ref.start_line}")
            if ref.note:
                lines.append(f"  Note: {ref.note}")
        return "\n".join(lines)


def list_affected_issues(self: CLI, file_path: str, as_json: bool = False) -> str:
    """List issues that reference a specific file.

    Args:
        file_path: File path to search for.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    issues = self.repo.get_issues_by_file(file_path)

    if as_json:
        return json.dumps([issue.to_dict() for issue in issues], indent=2)
    else:
        if not issues:
            return f"No issues found referencing {file_path}"

        lines = [f"Issues referencing {file_path}:"]
        for issue in issues:
            lines.append(
                f"  - Issue #{issue.id}: {issue.title} "
                f"[{issue.status.value}, {issue.priority.value}]"
            )
        return "\n".join(lines)
