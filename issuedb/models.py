"""Data models and enums for IssueDB."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


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
    WONT_DO = "wont-do"

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
class Comment:
    """Represents a comment on an issue."""

    id: Optional[int] = field(default=None)
    issue_id: int = field(default=0)
    text: str = field(default="")
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert comment to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "text": self.text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert audit log to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "action": self.action,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class IssueLink:
    """Represents a link between an issue and a git commit or branch."""

    id: Optional[int] = field(default=None)
    issue_id: int = field(default=0)
    link_type: str = field(default="")  # 'commit' or 'branch'
    reference: str = field(default="")  # commit hash or branch name
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert issue link to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "link_type": self.link_type,
            "reference": self.reference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class CodeReference:
    """Represents a reference to a file location in the codebase."""

    id: Optional[int] = field(default=None)
    issue_id: int = field(default=0)
    file_path: str = field(default="")
    start_line: Optional[int] = field(default=None)
    end_line: Optional[int] = field(default=None)
    note: Optional[str] = field(default=None)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert code reference to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Tag:
    """Represents a tag."""

    id: Optional[int] = field(default=None)
    name: str = field(default="")
    color: Optional[str] = field(default=None)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert tag to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Issue:
    """Represents an issue in the tracking system."""

    id: Optional[int] = field(default=None)
    title: str = field(default="")
    description: Optional[str] = field(default=None)
    priority: Priority = field(default=Priority.MEDIUM)
    status: Status = field(default=Status.OPEN)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    estimated_hours: Optional[float] = field(default=None)
    due_date: Optional[datetime] = field(default=None)
    tags: list[Tag] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": [tag.to_dict() for tag in self.tags],
        }
        if self.estimated_hours is not None:
            result["estimated_hours"] = self.estimated_hours
        if self.due_date:
            result["due_date"] = self.due_date.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Issue":
        """Create Issue from dictionary."""
        issue = cls()
        issue.id = data.get("id")
        issue.title = data.get("title", "")
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

        if "estimated_hours" in data:
            issue.estimated_hours = data.get("estimated_hours")

        if "due_date" in data and data["due_date"]:
            if isinstance(data["due_date"], str):
                issue.due_date = datetime.fromisoformat(data["due_date"])
            else:
                issue.due_date = data["due_date"]

        if "tags" in data and isinstance(data["tags"], list):
            issue.tags = []
            for tag_data in data["tags"]:
                tag = Tag(
                    id=tag_data.get("id"),
                    name=tag_data.get("name", ""),
                    color=tag_data.get("color"),
                )
                issue.tags.append(tag)

        return issue


@dataclass
class Memory:
    """Represents a memory item."""

    id: Optional[int] = field(default=None)
    key: str = field(default="")
    value: str = field(default="")
    category: str = field(default="general")
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert memory to dictionary."""
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class LessonLearned:
    """Represents a lesson learned."""

    id: Optional[int] = field(default=None)
    issue_id: Optional[int] = field(default=None)
    lesson: str = field(default="")
    category: str = field(default="general")
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert lesson to dictionary."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "lesson": self.lesson,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class IssueRelation:
    """Represents a relationship between issues."""

    id: Optional[int] = field(default=None)
    source_issue_id: int = field(default=0)
    target_issue_id: int = field(default=0)
    relation_type: str = field(default="")
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_issue_id": self.source_issue_id,
            "target_issue_id": self.target_issue_id,
            "relation_type": self.relation_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class IssueTemplate:
    """Represents a template for creating issues with predefined settings."""

    id: Optional[int] = field(default=None)
    name: str = field(default="")
    title_prefix: Optional[str] = field(default=None)
    default_priority: Optional[str] = field(default=None)
    default_status: Optional[str] = field(default=None)
    required_fields: list[str] = field(default_factory=list)  # List of field names
    field_prompts: dict[str, str] = field(default_factory=dict)  # Field name -> prompt text
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "title_prefix": self.title_prefix,
            "default_priority": self.default_priority,
            "default_status": self.default_status,
            "required_fields": self.required_fields,
            "field_prompts": self.field_prompts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueTemplate":
        """Create IssueTemplate from dictionary."""
        template = cls()
        template.id = data.get("id")
        template.name = data.get("name", "")
        template.title_prefix = data.get("title_prefix")
        template.default_priority = data.get("default_priority")
        template.default_status = data.get("default_status")
        template.required_fields = data.get("required_fields", [])
        template.field_prompts = data.get("field_prompts", {})

        if "created_at" in data and data["created_at"]:
            if isinstance(data["created_at"], str):
                template.created_at = datetime.fromisoformat(data["created_at"])
            else:
                template.created_at = data["created_at"]

        return template
