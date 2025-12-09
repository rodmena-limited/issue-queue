"""Tests for data models."""

import json
from datetime import datetime

import pytest

from issuedb.models import AuditLog, Issue, Priority, Status


class TestPriority:
    """Test Priority enum."""

    def test_from_string_valid(self):
        """Test creating Priority from valid string."""
        assert Priority.from_string("low") == Priority.LOW
        assert Priority.from_string("MEDIUM") == Priority.MEDIUM
        assert Priority.from_string("High") == Priority.HIGH
        assert Priority.from_string("critical") == Priority.CRITICAL

    def test_from_string_invalid(self):
        """Test creating Priority from invalid string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid priority"):
            Priority.from_string("invalid")

    def test_to_int(self):
        """Test converting Priority to integer for sorting."""
        assert Priority.LOW.to_int() == 1
        assert Priority.MEDIUM.to_int() == 2
        assert Priority.HIGH.to_int() == 3
        assert Priority.CRITICAL.to_int() == 4


class TestStatus:
    """Test Status enum."""

    def test_from_string_valid(self):
        """Test creating Status from valid string."""
        assert Status.from_string("open") == Status.OPEN
        assert Status.from_string("IN-PROGRESS") == Status.IN_PROGRESS
        assert Status.from_string("Closed") == Status.CLOSED
        assert Status.from_string("wont-do") == Status.WONT_DO
        assert Status.from_string("WONT-DO") == Status.WONT_DO

    def test_from_string_invalid(self):
        """Test creating Status from invalid string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Status.from_string("invalid")

    def test_wont_do_value(self):
        """Test that WONT_DO has correct value."""
        assert Status.WONT_DO.value == "wont-do"

    def test_all_status_values(self):
        """Test all status enum values exist."""
        assert len(Status) == 4
        values = [s.value for s in Status]
        assert "open" in values
        assert "in-progress" in values
        assert "closed" in values
        assert "wont-do" in values


class TestIssue:
    """Test Issue model."""

    def test_default_values(self):
        """Test Issue default values."""
        issue = Issue()
        assert issue.id is None
        assert issue.title == ""
        assert issue.description is None
        assert issue.priority == Priority.MEDIUM
        assert issue.status == Status.OPEN
        assert isinstance(issue.created_at, datetime)
        assert isinstance(issue.updated_at, datetime)

    def test_to_dict(self):
        """Test converting Issue to dictionary."""
        now = datetime.now()
        issue = Issue(
            id=1,
            title="Test Issue",
            description="Test description",
            priority=Priority.HIGH,
            status=Status.IN_PROGRESS,
            created_at=now,
            updated_at=now,
        )

        result = issue.to_dict()

        assert result["id"] == 1
        assert result["title"] == "Test Issue"
        assert result["description"] == "Test description"
        assert result["priority"] == "high"
        assert result["status"] == "in-progress"
        assert result["created_at"] == now.isoformat()
        assert result["updated_at"] == now.isoformat()

    def test_from_dict(self):
        """Test creating Issue from dictionary."""
        now = datetime.now()
        data = {
            "id": 1,
            "title": "Test Issue",
            "description": "Test description",
            "priority": "high",
            "status": "in-progress",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        issue = Issue.from_dict(data)

        assert issue.id == 1
        assert issue.title == "Test Issue"
        assert issue.description == "Test description"
        assert issue.priority == Priority.HIGH
        assert issue.status == Status.IN_PROGRESS

    def test_from_dict_partial(self):
        """Test creating Issue from partial dictionary."""
        data = {"title": "Test"}
        issue = Issue.from_dict(data)

        assert issue.title == "Test"
        assert issue.priority == Priority.MEDIUM
        assert issue.status == Status.OPEN

    def test_json_serialization(self):
        """Test that Issue can be serialized to JSON."""
        issue = Issue(
            id=1,
            title="Test",
            priority=Priority.HIGH,
            status=Status.OPEN,
        )

        json_str = json.dumps(issue.to_dict())
        data = json.loads(json_str)

        assert data["id"] == 1
        assert data["title"] == "Test"
        assert data["priority"] == "high"
        assert data["status"] == "open"


class TestAuditLog:
    """Test AuditLog model."""

    def test_default_values(self):
        """Test AuditLog default values."""
        log = AuditLog()
        assert log.id is None
        assert log.issue_id == 0
        assert log.action == ""
        assert log.field_name is None
        assert log.old_value is None
        assert log.new_value is None
        assert isinstance(log.timestamp, datetime)

    def test_to_dict(self):
        """Test converting AuditLog to dictionary."""
        now = datetime.now()
        log = AuditLog(
            id=1,
            issue_id=100,
            action="UPDATE",
            field_name="status",
            old_value="open",
            new_value="closed",
            timestamp=now,
        )

        result = log.to_dict()

        assert result["id"] == 1
        assert result["issue_id"] == 100
        assert result["action"] == "UPDATE"
        assert result["field_name"] == "status"
        assert result["old_value"] == "open"
        assert result["new_value"] == "closed"
        assert result["timestamp"] == now.isoformat()
