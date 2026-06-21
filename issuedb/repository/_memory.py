"""Repository methods split from the original god-class (mechanical split)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from issuedb.models import Memory

if TYPE_CHECKING:
    from issuedb.repository import IssueRepository


def add_memory(self: IssueRepository, key: str, value: str, category: str = "general") -> Memory:
    """Add a memory item.

    Args:
        key: Unique key.
        value: Value to store.
        category: Category (default: general).

    Returns:
        Created Memory object.

    Raises:
        ValueError: If key already exists.
    """
    memory = Memory(key=key, value=value, category=category)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO memory (key, value, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    memory.key,
                    memory.value,
                    memory.category,
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                ),
            )
            memory.id = cursor.lastrowid

            # Log audit
            self._log_audit(
                conn,
                0,  # System level
                "MEMORY_ADD",
                None,
                None,
                json.dumps(memory.to_dict()),
            )
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Memory with key '{key}' already exists") from e
            raise

    return memory


def update_memory(
    self: IssueRepository, key: str, value: str | None = None, category: str | None = None
) -> Memory | None:
    """Update a memory item.

    Args:
        key: Key to identify memory.
        value: New value.
        category: New category.

    Returns:
        Updated Memory object or None if not found.
    """
    current_memory = self.get_memory(key)
    if not current_memory:
        return None

    updates = []
    values = []
    audit_entries = []

    if value is not None and value != current_memory.value:
        updates.append("value = ?")
        values.append(value)
        audit_entries.append(("value", current_memory.value, value))

    if category is not None and category != current_memory.category:
        updates.append("category = ?")
        values.append(category)
        audit_entries.append(("category", current_memory.category, category))

    if not updates:
        return current_memory

    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(key)

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        query = f"UPDATE memory SET {', '.join(updates)} WHERE key = ?"
        cursor.execute(query, values)

        # Log audit
        for field, old_val, new_val in audit_entries:
            self._log_audit(
                conn,
                0,
                "MEMORY_UPDATE",
                f"{key}:{field}",
                old_val,
                new_val,
            )

    return self.get_memory(key)


def delete_memory(self: IssueRepository, key: str) -> bool:
    """Delete a memory item.

    Args:
        key: Key to identify memory.

    Returns:
        True if deleted, False if not found.
    """
    memory = self.get_memory(key)
    if not memory:
        return False

    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory WHERE key = ?", (key,))

        # Log audit
        self._log_audit(
            conn,
            0,
            "MEMORY_DELETE",
            None,
            json.dumps(memory.to_dict()),
            None,
        )

        return cursor.rowcount > 0


def get_memory(self: IssueRepository, key: str) -> Memory | None:
    """Get a memory item by key.

    Args:
        key: Key to identify memory.

    Returns:
        Memory object or None.
    """
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memory WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row:
            return Memory(
                id=row["id"],
                key=row["key"],
                value=row["value"],
                category=row["category"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
    return None


def list_memory(
    self: IssueRepository, category: str | None = None, search: str | None = None
) -> list[Memory]:
    """List memory items.


    Args:

        category: Filter by category.

        search: Search in key or value.



    Returns:

        List of Memory objects.

    """

    query = "SELECT * FROM memory WHERE 1=1"

    params: list[Any] = []

    if category:
        query += " AND category = ?"

        params.append(category)

    if search:
        query += " AND (key LIKE ? OR value LIKE ?)"

        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY key ASC"

    with self.db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(query, params)

        rows = cursor.fetchall()

        return [
            Memory(
                id=row["id"],
                key=row["key"],
                value=row["value"],
                category=row["category"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

# Lessons Learned methods
