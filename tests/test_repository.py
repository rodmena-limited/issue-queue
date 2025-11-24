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
            project="TestProject",
            description="Test description",
            priority=Priority.MEDIUM,
            status=Status.OPEN,
        )

    def test_create_issue(self, repo, sample_issue):
        """Test creating an issue."""
        created = repo.create_issue(sample_issue)

        assert created.id is not None
        assert created.title == "Test Issue"
        assert created.project == "TestProject"
        assert created.description == "Test description"
        assert created.priority == Priority.MEDIUM
        assert created.status == Status.OPEN

        # Check audit log
        logs = repo.get_audit_logs(issue_id=created.id)
        assert len(logs) == 1
        assert logs[0].action == "CREATE"
        assert logs[0].project == "TestProject"

    def test_create_issue_missing_title(self, repo):
        """Test that creating issue without title raises error."""
        issue = Issue(project="TestProject")
        with pytest.raises(ValueError, match="Title is required"):
            repo.create_issue(issue)

    def test_create_issue_missing_project(self, repo):
        """Test that creating issue without project raises error."""
        issue = Issue(title="Test")
        with pytest.raises(ValueError, match="Project is required"):
            repo.create_issue(issue)

    def test_get_issue(self, repo, sample_issue):
        """Test getting an issue by ID."""
        created = repo.create_issue(sample_issue)
        retrieved = repo.get_issue(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title
        assert retrieved.project == created.project

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
        assert updated.project == "TestProject"  # Unchanged

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
        repo.create_issue(Issue(title="Issue 1", project="ProjectA", priority=Priority.HIGH))
        repo.create_issue(Issue(title="Issue 2", project="ProjectA", status=Status.CLOSED))
        repo.create_issue(Issue(title="Issue 3", project="ProjectB", priority=Priority.LOW))

        # Test listing all
        all_issues = repo.list_issues()
        assert len(all_issues) == 3

        # Test filter by project
        project_a = repo.list_issues(project="ProjectA")
        assert len(project_a) == 2

        # Test filter by status
        open_issues = repo.list_issues(status="open")
        assert len(open_issues) == 2

        # Test filter by priority
        high_priority = repo.list_issues(priority="high")
        assert len(high_priority) == 1

        # Test combined filters
        filtered = repo.list_issues(project="ProjectA", status="closed")
        assert len(filtered) == 1

        # Test limit
        limited = repo.list_issues(limit=2)
        assert len(limited) == 2

    def test_get_next_issue(self, repo):
        """Test getting next issue based on priority and FIFO."""
        # Create issues in specific order
        repo.create_issue(Issue(title="Low", project="Project", priority=Priority.LOW))
        critical = repo.create_issue(
            Issue(title="Critical", project="Project", priority=Priority.CRITICAL)
        )
        high1 = repo.create_issue(Issue(title="High 1", project="Project", priority=Priority.HIGH))
        repo.create_issue(Issue(title="High 2", project="Project", priority=Priority.HIGH))

        # Should get critical first (highest priority)
        next_issue = repo.get_next_issue()
        assert next_issue.id == critical.id

        # Close critical and get next
        repo.update_issue(critical.id, status="closed")
        next_issue = repo.get_next_issue()
        assert next_issue.id == high1.id  # First high priority (FIFO)

        # Test with project filter
        repo.create_issue(Issue(title="Other", project="OtherProject", priority=Priority.CRITICAL))
        next_issue = repo.get_next_issue(project="Project")
        assert next_issue.project == "Project"

        # Test with status filter
        next_issue = repo.get_next_issue(status="closed")
        assert next_issue.id == critical.id

    def test_get_next_issue_none(self, repo):
        """Test get_next_issue returns None when no issues match."""
        result = repo.get_next_issue()
        assert result is None

        # Create closed issue
        repo.create_issue(Issue(title="Closed", project="Project", status=Status.CLOSED))
        result = repo.get_next_issue()  # Defaults to open
        assert result is None

    def test_search_issues(self, repo):
        """Test searching issues by keyword."""
        repo.create_issue(
            Issue(title="Fix bug in login", project="Project", description="Login fails")
        )
        repo.create_issue(
            Issue(title="Add feature", project="Project", description="New feature request")
        )
        repo.create_issue(Issue(title="Update docs", project="Other", description="Documentation"))

        # Search in title
        results = repo.search_issues("bug")
        assert len(results) == 1
        assert "bug" in results[0].title.lower()

        # Search in description
        results = repo.search_issues("feature")
        assert len(results) == 1

        # Search with project filter
        results = repo.search_issues("d", project="Other")
        assert len(results) == 1

        # Search with limit
        results = repo.search_issues("e", limit=1)
        assert len(results) == 1

    def test_clear_project(self, repo):
        """Test clearing all issues for a project."""
        # Create issues in different projects
        repo.create_issue(Issue(title="A1", project="ProjectA"))
        repo.create_issue(Issue(title="A2", project="ProjectA"))
        repo.create_issue(Issue(title="B1", project="ProjectB"))

        # Clear ProjectA
        deleted = repo.clear_project("ProjectA")
        assert deleted == 2

        # Check that ProjectA issues are gone
        remaining = repo.list_issues()
        assert len(remaining) == 1
        assert remaining[0].project == "ProjectB"

        # Check audit logs
        logs = repo.get_audit_logs(project="ProjectA")
        delete_logs = [log for log in logs if log.action == "DELETE"]
        assert len(delete_logs) == 2

    def test_get_audit_logs(self, repo):
        """Test retrieving audit logs."""
        issue = repo.create_issue(Issue(title="Test", project="Project"))
        repo.update_issue(issue.id, status="in-progress")
        repo.delete_issue(issue.id)

        # Get all logs for issue
        logs = repo.get_audit_logs(issue_id=issue.id)
        assert len(logs) == 3
        assert logs[0].action == "DELETE"  # Most recent first
        assert logs[1].action == "UPDATE"
        assert logs[2].action == "CREATE"

        # Get logs by project
        project_logs = repo.get_audit_logs(project="Project")
        assert len(project_logs) == 3

        # Create another issue in different project
        repo.create_issue(Issue(title="Other", project="OtherProject"))
        other_logs = repo.get_audit_logs(project="OtherProject")
        assert len(other_logs) == 1
