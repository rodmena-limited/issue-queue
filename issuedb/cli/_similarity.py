"""Similarity and duplicate-detection CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from issuedb.cli import CLI


def find_similar_issues(
    self: CLI,
    query: str,
    threshold: float = 0.6,
    limit: int | None = 10,
    as_json: bool = False,
) -> str:
    """Find issues similar to given text.

    Args:
        query: Text to find similar issues for.
        threshold: Similarity threshold (0.0 to 1.0).
        limit: Maximum number of results.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    from issuedb.similarity import find_similar_issues

    # Get all issues
    all_issues = self.repo.get_all_issues()

    # Find similar issues
    similar_issues = find_similar_issues(query, all_issues, threshold=threshold)

    # Limit results
    if limit:
        similar_issues = similar_issues[:limit]

    if as_json:
        results = []
        for issue, similarity in similar_issues:
            issue_dict = issue.to_dict()
            issue_dict["similarity"] = round(similarity * 100, 1)
            results.append(issue_dict)
        return json.dumps(results, indent=2)
    else:
        if not similar_issues:
            return "No similar issues found."

        lines = [f"Found {len(similar_issues)} similar issue(s):\n"]
        for issue, similarity in similar_issues:
            lines.append(f"Issue #{issue.id} ({round(similarity * 100, 1)}% similar)")
            lines.append(f"  Title: {issue.title}")
            lines.append(f"  Status: {issue.status.value}")
            lines.append(f"  Priority: {issue.priority.value}")
            lines.append("")

        return "\n".join(lines)


def find_duplicates(
    self: CLI,
    threshold: float = 0.7,
    as_json: bool = False,
) -> str:
    """Find potential duplicate issues.

    Args:
        threshold: Similarity threshold for considering duplicates.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    from issuedb.similarity import find_duplicate_groups

    # Get all issues
    all_issues = self.repo.get_all_issues()

    # Find duplicate groups
    duplicate_groups = find_duplicate_groups(all_issues, threshold=threshold)

    if as_json:
        groups_data = []
        for group in duplicate_groups:
            duplicates_list: list[dict[str, Any]] = []
            for issue, similarity in group[1:]:
                dup_dict = issue.to_dict()
                dup_dict["similarity"] = round(similarity * 100, 1)
                duplicates_list.append(dup_dict)
            group_data = {"primary": group[0][0].to_dict(), "duplicates": duplicates_list}
            groups_data.append(group_data)

        return json.dumps(
            {"total_groups": len(duplicate_groups), "groups": groups_data}, indent=2
        )
    else:
        if not duplicate_groups:
            return "No potential duplicates found."

        lines = [f"Found {len(duplicate_groups)} group(s) of potential duplicates:\n"]

        for i, group in enumerate(duplicate_groups, 1):
            primary_issue, _ = group[0]
            lines.append(f"Group {i}:")
            lines.append(f"  Primary: Issue #{primary_issue.id} - {primary_issue.title}")
            lines.append("  Potential duplicates:")

            for issue, similarity in group[1:]:
                lines.append(
                    f"    - Issue #{issue.id}: {issue.title} "
                    f"({round(similarity * 100, 1)}% similar)"
                )
            lines.append("")

        return "\n".join(lines)
