"""Memory CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def memory_add(
    self: CLI, key: str, value: str, category: str = "general", as_json: bool = False
) -> str:
    """Add memory item.

    Raises:
        ValueError: If the key already exists (propagates to the CLI error
            handler: message on stderr, exit code 1).
    """
    memory = self.repo.add_memory(key, value, category)
    if as_json:
        return json.dumps(memory.to_dict(), indent=2)
    return f"Memory added: {key} ({category})"


def memory_list(
    self: CLI, category: str | None = None, search: str | None = None, as_json: bool = False
) -> str:
    """List memory items."""
    memories = self.repo.list_memory(category, search)
    if as_json:
        return json.dumps([m.to_dict() for m in memories], indent=2)

    if not memories:
        return "No memory items found."

    lines = []
    for m in memories:
        lines.append(f"[{m.category}] {m.key}: {m.value}")
    return "\n".join(lines)


def memory_update(
    self: CLI,
    key: str,
    value: str | None = None,
    category: str | None = None,
    as_json: bool = False,
) -> str:
    """Update memory item.

    Raises:
        ValueError: If the key does not exist.
    """
    memory = self.repo.update_memory(key, value, category)
    if not memory:
        raise ValueError(f"Memory '{key}' not found")

    if as_json:
        return json.dumps(memory.to_dict(), indent=2)
    return f"Memory updated: {key}"


def memory_delete(self: CLI, key: str, as_json: bool = False) -> str:
    """Delete memory item.

    Raises:
        ValueError: If the key does not exist.
    """
    if self.repo.delete_memory(key):
        msg = f"Memory '{key}' deleted"
        return json.dumps({"message": msg}) if as_json else msg
    raise ValueError(f"Memory '{key}' not found")
