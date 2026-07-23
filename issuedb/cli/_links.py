"""Issue link CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def link_issues(self: CLI, source: int, target: int, type: str, as_json: bool = False) -> str:
    """Link issues.

    Raises:
        ValueError: On self-link, duplicate relation, or missing issue.
    """
    rel = self.repo.link_issues(source, target, type)
    if as_json:
        return json.dumps(rel.to_dict(), indent=2)
    return f"Linked #{source} to #{target} ({type})"


def unlink_issues(
    self: CLI, source: int, target: int, type: str | None = None, as_json: bool = False
) -> str:
    """Unlink issues.

    Raises:
        ValueError: If the link does not exist.
    """
    if self.repo.unlink_issues(source, target, type):
        msg = f"Unlinked #{source} and #{target}"
        return json.dumps({"message": msg}) if as_json else msg
    raise ValueError("Link not found")
