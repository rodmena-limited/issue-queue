"""Memory CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def memory_add(
    self: CLI, key: str, value: str, category: str = "general", as_json: bool = False
) -> str:
    """Add memory item."""
    try:
        memory = self.repo.add_memory(key, value, category)
        if as_json:
            return json.dumps(memory.to_dict(), indent=2)
        return f"Memory added: {key} ({category})"
    except ValueError as e:
        return json.dumps({"error": str(e)}) if as_json else str(e)


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
    """Update memory item."""
    memory = self.repo.update_memory(key, value, category)
    if not memory:
        msg = f"Memory '{key}' not found"
        return json.dumps({"error": msg}) if as_json else msg

    if as_json:
        return json.dumps(memory.to_dict(), indent=2)
    return f"Memory updated: {key}"


def memory_delete(self: CLI, key: str, as_json: bool = False) -> str:
    """Delete memory item."""
    if self.repo.delete_memory(key):
        msg = f"Memory '{key}' deleted"
        return json.dumps({"message": msg}) if as_json else msg
    msg = f"Memory '{key}' not found"
    return json.dumps({"error": msg}) if as_json else msg
