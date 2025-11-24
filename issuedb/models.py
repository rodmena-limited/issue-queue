"""Data models and enums for IssueDB."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Priority(Enum):
    """Priority levels for issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, value: str) -> "Priority":
        """Create Priority from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid priority: {value}. Must be one of: {', '.join([p.value for p in cls])}"
            ) from None

    def to_int(self) -> int:
        """Convert priority to integer for sorting (higher number = higher priority)."""
        priority_map = {
            Priority.LOW: 1,
            Priority.MEDIUM: 2,
            Priority.HIGH: 3,
            Priority.CRITICAL: 4,
        }
        return priority_map[self]


class Status(Enum):
    """Status levels for issues."""

    OPEN = "open"
    IN_PROGRESS = "in-progress"
    CLOSED = "closed"

    @classmethod
    def from_string(cls, value: str) -> "Status":
        """Create Status from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid status: {value}. Must be one of: {', '.join([s.value for s in cls])}"
            ) from None


@dataclass
class Issue:
    """Represents an issue in the tracking system."""

    id: Optional[int] = field(default=None)
    title: str = field(default="")
    project: str = field(default="")
    description: Optional[str] = field(default=None)
    priority: Priority = field(default=Priority.MEDIUM)
    status: Status = field(default=Status.OPEN)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert issue to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "project": self.project,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Issue":
        """Create Issue from dictionary."""
        issue = cls()
        issue.id = data.get("id")
        issue.title = data.get("title", "")
        issue.project = data.get("project", "")
        issue.description = data.get("description")

        if "priority" in data:
            issue.priority = Priority.from_string(data["priority"])

        if "status" in data:
            issue.status = Status.from_string(data["status"])

        if "created_at" in data and data["created_at"]:
            if isinstance(data["created_at"], str):
                issue.created_at = datetime.fromisoformat(data["created_at"])
            else:
                issue.created_at = data["created_at"]

        if "updated_at" in data and data["updated_at"]:
            if isinstance(data["updated_at"], str):
                issue.updated_at = datetime.fromisoformat(data["updated_at"])
            else:
                issue.updated_at = data["updated_at"]

        return issue


@dataclass
class AuditLog:
    """Represents an audit log entry for tracking changes."""

    id: Optional[int] = field(default=None)
    issue_id: int = field(default=0)
    action: str = field(default="")  # CREATE, UPDATE, DELETE
    field_name: Optional[str] = field(default=None)
    old_value: Optional[str] = field(default=None)
    new_value: Optional[str] = field(default=None)
    timestamp: datetime = field(default_factory=datetime.now)
    project: str = field(default="")

    def to_dict(self) -> dict:
        """Convert audit log to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "action": self.action,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "project": self.project,
        }
