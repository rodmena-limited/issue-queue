"""Tests for repository module."""

import json
import tempfile

import pytest

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


class TestIssueRepository:
    """Test IssueRepository class."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            repo = IssueRepository(f.name)
            yield repo

    @pytest.fixture
    def sample_issue(self):
        """Create a sample issue."""
        return Issue(
            title="Test Issue",
            description="Test description",
            priority=Priority.MEDIUM,
            status=Status.OPEN,
        )

    def test_create_issue(self, repo, sample_issue):
        """Test creating an issue."""
        created = repo.create_issue(sample_issue)

        assert created.id is not None
        assert created.title == "Test Issue"
        assert created.description == "Test description"
        assert created.priority == Priority.MEDIUM
        assert created.status == Status.OPEN

        # Check audit log
        logs = repo.get_audit_logs(issue_id=created.id)
        assert len(logs) == 1
        assert logs[0].action == "CREATE"

    def test_create_issue_missing_title(self, repo):
        """Test that creating issue without title raises error."""
        issue = Issue()
        with pytest.raises(ValueError, match="Title is required"):
            repo.create_issue(issue)

    def test_get_issue(self, repo, sample_issue):
        """Test getting an issue by ID."""
        created = repo.create_issue(sample_issue)
        retrieved = repo.get_issue(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title

    def test_get_issue_not_found(self, repo):
        """Test getting non-existent issue returns None."""
        result = repo.get_issue(999)
        assert result is None

    def test_update_issue(self, repo, sample_issue):
        """Test updating an issue."""
        created = repo.create_issue(sample_issue)

        updated = repo.update_issue(
            created.id,
            title="Updated Title",
            status="in-progress",
            priority="high",
        )

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.status == Status.IN_PROGRESS
        assert updated.priority == Priority.HIGH

        # Check audit logs
        logs = repo.get_audit_logs(issue_id=created.id)
        assert len(logs) == 4  # CREATE + 3 field updates
        update_logs = [log for log in logs if log.action == "UPDATE"]
        assert len(update_logs) == 3

    def test_update_issue_no_changes(self, repo, sample_issue):
        """Test updating issue with no actual changes."""
        created = repo.create_issue(sample_issue)
        updated = repo.update_issue(created.id, title=created.title)

        assert updated.title == created.title
        # Only CREATE log should exist
        logs = repo.get_audit_logs(issue_id=created.id)
        assert len(logs) == 1
        assert logs[0].action == "CREATE"

    def test_update_issue_not_found(self, repo):
        """Test updating non-existent issue returns None."""
        result = repo.update_issue(999, title="New Title")
        assert result is None

    def test_update_issue_invalid_field(self, repo, sample_issue):
        """Test updating issue with invalid field raises error."""
        created = repo.create_issue(sample_issue)
        with pytest.raises(ValueError, match="Cannot update field: invalid"):
            repo.update_issue(created.id, invalid="value")

    def test_delete_issue(self, repo, sample_issue):
        """Test deleting an issue."""
        created = repo.create_issue(sample_issue)
        result = repo.delete_issue(created.id)

        assert result is True
        assert repo.get_issue(created.id) is None

        # Check audit log
        logs = repo.get_audit_logs(issue_id=created.id)
        assert len(logs) == 2  # CREATE and DELETE
        assert logs[0].action == "DELETE"  # Most recent first
        assert json.loads(logs[0].old_value)["title"] == "Test Issue"

    def test_delete_issue_not_found(self, repo):
        """Test deleting non-existent issue returns False."""
        result = repo.delete_issue(999)
        assert result is False

    def test_list_issues(self, repo):
        """Test listing issues."""
        # Create multiple issues
        repo.create_issue(Issue(title="Issue 1", priority=Priority.HIGH))
        repo.create_issue(Issue(title="Issue 2", status=Status.CLOSED))
        repo.create_issue(Issue(title="Issue 3", priority=Priority.LOW))

        # Test listing all
        all_issues = repo.list_issues()
        assert len(all_issues) == 3

        # Test filter by status
        open_issues = repo.list_issues(status="open")
        assert len(open_issues) == 2

        # Test filter by priority
        high_priority = repo.list_issues(priority="high")
        assert len(high_priority) == 1

        # Test combined filters
        filtered = repo.list_issues(status="closed")
        assert len(filtered) == 1

        # Test limit
        limited = repo.list_issues(limit=2)
        assert len(limited) == 2

    def test_get_next_issue(self, repo):
        """Test getting next issue based on priority and FIFO."""
        # Create issues in specific order
        repo.create_issue(Issue(title="Low", priority=Priority.LOW))
        critical = repo.create_issue(Issue(title="Critical", priority=Priority.CRITICAL))
        high1 = repo.create_issue(Issue(title="High 1", priority=Priority.HIGH))
        repo.create_issue(Issue(title="High 2", priority=Priority.HIGH))

        # Should get critical first (highest priority)
        next_issue = repo.get_next_issue()
        assert next_issue.id == critical.id

        # Close critical and get next
        repo.update_issue(critical.id, status="closed")
        next_issue = repo.get_next_issue()
        assert next_issue.id == high1.id  # First high priority (FIFO)

        # Test with status filter
        next_issue = repo.get_next_issue(status="closed")
        assert next_issue.id == critical.id

    def test_get_next_issue_none(self, repo):
        """Test get_next_issue returns None when no issues match."""
        result = repo.get_next_issue()
        assert result is None

        # Create closed issue
        repo.create_issue(Issue(title="Closed", status=Status.CLOSED))
        result = repo.get_next_issue()  # Defaults to open
        assert result is None

    def test_search_issues(self, repo):
        """Test searching issues by keyword."""
        repo.create_issue(Issue(title="Fix bug in login", description="Login fails"))
        repo.create_issue(Issue(title="Add feature", description="New feature request"))
        repo.create_issue(Issue(title="Update docs", description="Documentation"))

        # Search in title
        results = repo.search_issues("bug")
        assert len(results) == 1
        assert "bug" in results[0].title.lower()

        # Search in description
        results = repo.search_issues("feature")
        assert len(results) == 1

        # Search with limit
        results = repo.search_issues("e", limit=1)
        assert len(results) == 1

    def test_clear_all_issues(self, repo):
        """Test clearing all issues."""
        # Create issues
        repo.create_issue(Issue(title="A1"))
        repo.create_issue(Issue(title="A2"))
        repo.create_issue(Issue(title="B1"))

        # Clear all
        deleted = repo.clear_all_issues()
        assert deleted == 3

        # Check that all issues are gone
        remaining = repo.list_issues()
        assert len(remaining) == 0

        # Check audit logs
        logs = repo.get_audit_logs()
        delete_logs = [log for log in logs if log.action == "DELETE"]
        assert len(delete_logs) == 3

    def test_get_audit_logs(self, repo):
        """Test retrieving audit logs."""
        issue = repo.create_issue(Issue(title="Test"))
        repo.update_issue(issue.id, status="in-progress")
        repo.delete_issue(issue.id)

        # Get all logs for issue
        logs = repo.get_audit_logs(issue_id=issue.id)
        assert len(logs) == 3
        assert logs[0].action == "DELETE"  # Most recent first
        assert logs[1].action == "UPDATE"
        assert logs[2].action == "CREATE"

    def test_bulk_update_all_issues(self, repo):
        """Test bulk updating all issues."""
        # Create multiple issues
        issue1 = repo.create_issue(Issue(title="Issue 1", status=Status.OPEN))
        issue2 = repo.create_issue(Issue(title="Issue 2", status=Status.OPEN))
        issue3 = repo.create_issue(Issue(title="Issue 3", status=Status.IN_PROGRESS))

        # Bulk update all to closed
        count = repo.bulk_update_issues(new_status="closed")
        assert count == 3

        # Verify all are closed
        updated1 = repo.get_issue(issue1.id)
        updated2 = repo.get_issue(issue2.id)
        updated3 = repo.get_issue(issue3.id)
        assert updated1.status == Status.CLOSED
        assert updated2.status == Status.CLOSED
        assert updated3.status == Status.CLOSED

        # Check audit logs
        logs1 = repo.get_audit_logs(issue_id=issue1.id)
        assert any(log.action == "BULK_UPDATE" for log in logs1)

    def test_bulk_update_by_status_filter(self, repo):
        """Test bulk updating issues with specific status."""
        # Create issues with different statuses
        issue1 = repo.create_issue(Issue(title="Issue 1", status=Status.OPEN))
        issue2 = repo.create_issue(Issue(title="Issue 2", status=Status.IN_PROGRESS))
        issue3 = repo.create_issue(Issue(title="Issue 3", status=Status.OPEN))

        # Bulk update only open issues
        count = repo.bulk_update_issues(filter_status="open", new_status="in-progress")
        assert count == 2

        # Verify only open issues were updated
        updated1 = repo.get_issue(issue1.id)
        updated2 = repo.get_issue(issue2.id)
        updated3 = repo.get_issue(issue3.id)
        assert updated1.status == Status.IN_PROGRESS
        assert updated2.status == Status.IN_PROGRESS  # Already in-progress
        assert updated3.status == Status.IN_PROGRESS

    def test_bulk_update_by_priority_filter(self, repo):
        """Test bulk updating issues with specific priority."""
        # Create issues with different priorities
        issue1 = repo.create_issue(Issue(title="Issue 1", priority=Priority.HIGH))
        issue2 = repo.create_issue(Issue(title="Issue 2", priority=Priority.CRITICAL))
        issue3 = repo.create_issue(Issue(title="Issue 3", priority=Priority.HIGH))

        # Bulk update only high priority issues
        count = repo.bulk_update_issues(filter_priority="high", new_priority="medium")
        assert count == 2

        # Verify only high priority issues were updated
        updated1 = repo.get_issue(issue1.id)
        updated2 = repo.get_issue(issue2.id)
        updated3 = repo.get_issue(issue3.id)
        assert updated1.priority == Priority.MEDIUM
        assert updated2.priority == Priority.CRITICAL  # Not updated
        assert updated3.priority == Priority.MEDIUM

    def test_bulk_update_no_matches(self, repo):
        """Test bulk update with no matching issues."""
        # Create an issue
        repo.create_issue(Issue(title="Issue 1", status=Status.OPEN))

        # Try to update with filter that matches nothing
        count = repo.bulk_update_issues(filter_status="closed", new_status="open")
        assert count == 0

    def test_bulk_update_no_changes(self, repo):
        """Test bulk update with no update fields."""
        # Create an issue
        repo.create_issue(Issue(title="Issue 1"))

        # Try to update with no fields
        count = repo.bulk_update_issues()
        assert count == 0

    def test_get_summary_all_issues(self, repo):
        """Test getting summary of all issues."""
        # Create issues with different statuses and priorities
        repo.create_issue(Issue(title="Issue 1", status=Status.OPEN, priority=Priority.HIGH))
        repo.create_issue(Issue(title="Issue 2", status=Status.OPEN, priority=Priority.LOW))
        repo.create_issue(
            Issue(
                title="Issue 3",
                status=Status.CLOSED,
                priority=Priority.CRITICAL,
            )
        )
        repo.create_issue(
            Issue(
                title="Issue 4",
                status=Status.IN_PROGRESS,
                priority=Priority.MEDIUM,
            )
        )

        summary = repo.get_summary()

        assert summary["total_issues"] == 4
        assert summary["by_status"]["open"] == 2
        assert summary["by_status"]["in_progress"] == 1
        assert summary["by_status"]["closed"] == 1
        assert summary["by_priority"]["high"] == 1
        assert summary["by_priority"]["low"] == 1
        assert summary["by_priority"]["critical"] == 1
        assert summary["by_priority"]["medium"] == 1
        assert summary["status_percentages"]["open"] == 50.0
        assert summary["status_percentages"]["closed"] == 25.0

    def test_get_report_grouped_by_status(self, repo):
        """Test getting report grouped by status."""
        # Create issues with different statuses
        issue1 = repo.create_issue(Issue(title="Issue 1", status=Status.OPEN))
        repo.create_issue(Issue(title="Issue 2", status=Status.CLOSED))
        repo.create_issue(Issue(title="Issue 3", status=Status.IN_PROGRESS))

        report = repo.get_report(group_by="status")

        assert report["total_issues"] == 3
        assert report["group_by"] == "status"
        assert report["groups"]["open"]["count"] == 1
        assert report["groups"]["closed"]["count"] == 1
        assert report["groups"]["in_progress"]["count"] == 1
        assert len(report["groups"]["open"]["issues"]) == 1
        assert report["groups"]["open"]["issues"][0]["id"] == issue1.id

    def test_get_report_grouped_by_priority(self, repo):
        """Test getting report grouped by priority."""
        # Create issues with different priorities
        repo.create_issue(Issue(title="Issue 1", priority=Priority.HIGH))
        repo.create_issue(Issue(title="Issue 2", priority=Priority.CRITICAL))
        repo.create_issue(Issue(title="Issue 3", priority=Priority.HIGH))

        report = repo.get_report(group_by="priority")

        assert report["total_issues"] == 3
        assert report["group_by"] == "priority"
        assert report["groups"]["high"]["count"] == 2
        assert report["groups"]["critical"]["count"] == 1
        assert report["groups"]["low"]["count"] == 0
        assert len(report["groups"]["high"]["issues"]) == 2

    def test_get_report_invalid_group_by(self, repo):
        """Test getting report with invalid group_by parameter."""
        repo.create_issue(Issue(title="Issue 1"))

        with pytest.raises(ValueError, match="group_by must be"):
            repo.get_report(group_by="invalid")

    def test_bulk_create_issues(self, repo):
        """Test bulk creating multiple issues from JSON data."""
        issues_data = [
            {
                "title": "Issue 1",
                "description": "Description 1",
                "priority": "high",
                "status": "open",
            },
            {
                "title": "Issue 2",
                "description": "Description 2",
                "priority": "critical",
                "status": "in-progress",
            },
            {"title": "Issue 3", "priority": "low"},
        ]

        created_issues = repo.bulk_create_issues(issues_data)

        assert len(created_issues) == 3
        assert created_issues[0].title == "Issue 1"
        assert created_issues[0].priority == Priority.HIGH
        assert created_issues[1].title == "Issue 2"
        assert created_issues[1].status == Status.IN_PROGRESS
        assert created_issues[2].title == "Issue 3"
        assert created_issues[2].priority == Priority.LOW

        # Verify all issues are in database
        all_issues = repo.list_issues()
        assert len(all_issues) == 3

        # Check audit logs
        logs = repo.get_audit_logs(issue_id=created_issues[0].id)
        assert len(logs) == 1
        assert logs[0].action == "BULK_CREATE"

    def test_bulk_create_issues_missing_title(self, repo):
        """Test bulk create fails if any issue is missing title."""
        issues_data = [
            {"title": "Issue 1", "priority": "high"},
            {"description": "Missing title"},  # No title
        ]

        with pytest.raises(ValueError, match="Title is required"):
            repo.bulk_create_issues(issues_data)

        # Verify no issues were created (transaction rollback)
        all_issues = repo.list_issues()
        assert len(all_issues) == 0

    def test_bulk_update_issues_from_json(self, repo):
        """Test bulk updating specific issues from JSON data."""
        # Create issues first
        issue1 = repo.create_issue(Issue(title="Issue 1", priority=Priority.LOW))
        issue2 = repo.create_issue(Issue(title="Issue 2", status=Status.OPEN))
        issue3 = repo.create_issue(Issue(title="Issue 3"))

        # Prepare updates
        updates_data = [
            {"id": issue1.id, "priority": "high", "status": "in-progress"},
            {"id": issue2.id, "title": "Updated Issue 2"},
            {"id": issue3.id, "status": "closed"},
        ]

        updated_issues = repo.bulk_update_issues_from_json(updates_data)

        assert len(updated_issues) == 3
        assert updated_issues[0].id == issue1.id
        assert updated_issues[0].priority == Priority.HIGH
        assert updated_issues[0].status == Status.IN_PROGRESS
        assert updated_issues[1].title == "Updated Issue 2"
        assert updated_issues[2].status == Status.CLOSED

        # Verify updates in database
        retrieved1 = repo.get_issue(issue1.id)
        assert retrieved1.priority == Priority.HIGH

    def test_bulk_update_issues_from_json_missing_id(self, repo):
        """Test bulk update fails if any update is missing id."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))

        updates_data = [
            {"id": issue1.id, "status": "closed"},
            {"title": "No ID"},  # Missing id
        ]

        with pytest.raises(ValueError, match="Issue ID is required"):
            repo.bulk_update_issues_from_json(updates_data)

    def test_bulk_update_issues_from_json_not_found(self, repo):
        """Test bulk update fails if any issue not found."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))

        updates_data = [
            {"id": issue1.id, "status": "closed"},
            {"id": 999, "status": "closed"},  # Non-existent ID
        ]

        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.bulk_update_issues_from_json(updates_data)

    def test_bulk_update_issues_from_json_no_fields(self, repo):
        """Test bulk update fails if no update fields provided."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))

        updates_data = [
            {"id": issue1.id},  # Only ID, no updates
        ]

        with pytest.raises(ValueError, match="No update fields provided"):
            repo.bulk_update_issues_from_json(updates_data)

    def test_bulk_close_issues(self, repo):
        """Test bulk closing multiple issues."""
        # Create issues with different statuses
        issue1 = repo.create_issue(Issue(title="Issue 1", status=Status.OPEN))
        issue2 = repo.create_issue(Issue(title="Issue 2", status=Status.IN_PROGRESS))
        issue3 = repo.create_issue(Issue(title="Issue 3", status=Status.OPEN))

        # Bulk close specific issues
        issue_ids = [issue1.id, issue2.id, issue3.id]
        closed_issues = repo.bulk_close_issues(issue_ids)

        assert len(closed_issues) == 3
        assert all(issue.status == Status.CLOSED for issue in closed_issues)

        # Verify in database
        retrieved1 = repo.get_issue(issue1.id)
        retrieved2 = repo.get_issue(issue2.id)
        retrieved3 = repo.get_issue(issue3.id)
        assert retrieved1.status == Status.CLOSED
        assert retrieved2.status == Status.CLOSED
        assert retrieved3.status == Status.CLOSED

        # Check audit logs
        logs = repo.get_audit_logs(issue_id=issue1.id)
        update_logs = [log for log in logs if log.action == "UPDATE"]
        assert len(update_logs) > 0

    def test_bulk_close_issues_not_found(self, repo):
        """Test bulk close fails if any issue not found."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))

        issue_ids = [issue1.id, 999]  # 999 doesn't exist

        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.bulk_close_issues(issue_ids)

    def test_bulk_close_issues_empty_list(self, repo):
        """Test bulk close with empty list."""
        closed_issues = repo.bulk_close_issues([])
        assert len(closed_issues) == 0
