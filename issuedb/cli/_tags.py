"""Tag CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def tag_issue(self: CLI, issue_id: int, tags: list[str], as_json: bool = False) -> str:
    """Add tags to issue."""
    added = []
    for tag in tags:
        if self.repo.add_issue_tag(issue_id, tag):
            added.append(tag)

    if as_json:
        return json.dumps({"added": added}, indent=2)
    return f"Added tags to issue #{issue_id}: {', '.join(added)}"


def untag_issue(self: CLI, issue_id: int, tags: list[str], as_json: bool = False) -> str:
    """Remove tags from issue."""
    removed = []
    for tag in tags:
        if self.repo.remove_issue_tag(issue_id, tag):
            removed.append(tag)

    if as_json:
        return json.dumps({"removed": removed}, indent=2)
    return f"Removed tags from issue #{issue_id}: {', '.join(removed)}"


def tag_list(self: CLI, as_json: bool = False) -> str:
    """List all available tags."""
    tags = self.repo.list_tags()
    if as_json:
        return json.dumps([t.to_dict() for t in tags], indent=2)
    return ", ".join([t.name for t in tags])
