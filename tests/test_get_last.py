"""Tests for get-last functionality (fetching history tracking)."""

import tempfile
from typing import Generator

import pytest

from issuedb.cli import CLI
from issuedb.models import Issue, Priority
from issuedb.repository import IssueRepository


@pytest.fixture
def repo() -> Generator[IssueRepository, None, None]:
    """Create a fresh repository with temporary database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        yield IssueRepository(f.name)


@pytest.fixture
def cli() -> Generator[CLI, None, None]:
    """Create a fresh CLI instance with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        yield CLI(f.name)


class TestGetLastFetchedRepository:
    """Tests for IssueRepository.get_last_fetched method."""

    def test_get_last_fetched_empty(self, repo: IssueRepository) -> None:
        """Test get_last_fetched when no issues have been fetched."""
        result = repo.get_last_fetched()
        assert result == []

    def test_get_last_fetched_single(self, repo: IssueRepository) -> None:
        """Test get_last_fetched returns the last fetched issue."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Test issue"))

        # Fetch it via get_next
        fetched = repo.get_next_issue()
        assert fetched is not None
        assert fetched.id == issue.id

        # Get last fetched
        result = repo.get_last_fetched()
        assert len(result) == 1
        assert result[0].id == issue.id
        assert result[0].title == "Test issue"

    def test_get_last_fetched_multiple(self, repo: IssueRepository) -> None:
        """Test get_last_fetched with multiple fetches."""
        # Create multiple issues with different priorities
        issue1 = repo.create_issue(Issue(title="Issue 1", priority=Priority.LOW))
        issue2 = repo.create_issue(Issue(title="Issue 2", priority=Priority.CRITICAL))
        issue3 = repo.create_issue(Issue(title="Issue 3", priority=Priority.HIGH))

        # Fetch them one by one (they will be fetched by priority)
        # Critical first
        fetched1 = repo.get_next_issue()
        assert fetched1 is not None
        assert fetched1.id == issue2.id

        # Close it so next one is fetched
        repo.update_issue(issue2.id, status="closed")

        # High priority next
        fetched2 = repo.get_next_issue()
        assert fetched2 is not None
        assert fetched2.id == issue3.id

        repo.update_issue(issue3.id, status="closed")

        # Low priority last
        fetched3 = repo.get_next_issue()
        assert fetched3 is not None
        assert fetched3.id == issue1.id

        # Get last 2 fetched
        result = repo.get_last_fetched(limit=2)
        assert len(result) == 2
        # Most recent first
        assert result[0].id == issue1.id
        assert result[1].id == issue3.id

    def test_get_last_fetched_limit(self, repo: IssueRepository) -> None:
        """Test get_last_fetched with limit parameter."""
        # Create and fetch multiple issues
        issues = []
        for i in range(5):
            issue = repo.create_issue(Issue(title=f"Issue {i}", priority=Priority.CRITICAL))
            issues.append(issue)
            repo.get_next_issue()
            repo.update_issue(issue.id, status="closed")

        # Get last 3
        result = repo.get_last_fetched(limit=3)
        assert len(result) == 3
        # Most recent first
        assert result[0].id == issues[4].id
        assert result[1].id == issues[3].id
        assert result[2].id == issues[2].id

    def test_get_last_fetched_no_duplicates(self, repo: IssueRepository) -> None:
        """Test get_last_fetched doesn't return duplicates for same issue."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Test issue"))

        # Fetch it multiple times (simulating user fetching, doing nothing, fetching again)
        for _ in range(3):
            fetched = repo.get_next_issue()
            assert fetched is not None
            assert fetched.id == issue.id

        # Get last 5 (should only return 1 since it's the same issue)
        result = repo.get_last_fetched(limit=5)
        assert len(result) == 1
        assert result[0].id == issue.id

    def test_get_last_fetched_deleted_issue(self, repo: IssueRepository) -> None:
        """Test get_last_fetched includes deleted issues from audit log."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Will be deleted"))
        issue_id = issue.id

        # Fetch it
        fetched = repo.get_next_issue()
        assert fetched is not None

        # Delete the issue
        repo.delete_issue(issue_id)

        # Get last fetched - should still find it from audit log
        result = repo.get_last_fetched()
        assert len(result) == 1
        assert result[0].id == issue_id
        assert result[0].title == "Will be deleted"

    def test_get_last_fetched_respects_log_fetch_flag(self, repo: IssueRepository) -> None:
        """Test that log_fetch=False doesn't log the fetch."""
        # Create an issue
        repo.create_issue(Issue(title="Test issue"))

        # Fetch without logging
        fetched = repo.get_next_issue(log_fetch=False)
        assert fetched is not None

        # Get last fetched - should be empty
        result = repo.get_last_fetched()
        assert result == []

    def test_get_last_fetched_shows_current_state(self, repo: IssueRepository) -> None:
        """Test that get_last_fetched shows current state of non-deleted issues."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Original title"))

        # Fetch it
        repo.get_next_issue()

        # Update the issue
        repo.update_issue(issue.id, title="Updated title", status="in-progress")

        # Get last fetched - should show current state
        result = repo.get_last_fetched()
        assert len(result) == 1
        assert result[0].title == "Updated title"
        assert result[0].status.value == "in-progress"


class TestGetLastFetchedCLI:
    """Tests for CLI get_last_fetched method."""

    def test_get_last_empty(self, cli: CLI) -> None:
        """Test get-last when no issues have been fetched."""
        result = cli.get_last_fetched()
        assert "No fetched issues found" in result

    def test_get_last_empty_json(self, cli: CLI) -> None:
        """Test get-last JSON output when no issues have been fetched."""
        result = cli.get_last_fetched(as_json=True)
        assert '"message"' in result
        assert "No fetched issues found" in result

    def test_get_last_single(self, cli: CLI) -> None:
        """Test get-last returns the last fetched issue."""
        # Create and fetch an issue
        cli.create_issue(title="Test issue", priority="high")
        cli.get_next_issue()

        # Get last
        result = cli.get_last_fetched()
        assert "Test issue" in result
        assert "ID:" in result

    def test_get_last_json(self, cli: CLI) -> None:
        """Test get-last with JSON output."""
        import json

        # Create and fetch an issue
        cli.create_issue(title="Test issue", priority="high")
        cli.get_next_issue()

        # Get last as JSON
        result = cli.get_last_fetched(as_json=True)
        data = json.loads(result)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test issue"

    def test_get_last_multiple(self, cli: CLI) -> None:
        """Test get-last with multiple issues."""
        import json

        # Create multiple issues
        cli.create_issue(title="Issue 1", priority="low")
        cli.create_issue(title="Issue 2", priority="critical")
        cli.create_issue(title="Issue 3", priority="high")

        # Fetch them in priority order
        cli.get_next_issue()  # critical
        cli.repo.update_issue(2, status="closed")

        cli.get_next_issue()  # high
        cli.repo.update_issue(3, status="closed")

        cli.get_next_issue()  # low

        # Get last 2
        result = cli.get_last_fetched(limit=2, as_json=True)
        data = json.loads(result)

        assert len(data) == 2
        assert data[0]["title"] == "Issue 1"  # most recent
        assert data[1]["title"] == "Issue 3"


class TestAuditLogFetch:
    """Tests for FETCH action in audit logs."""

    def test_fetch_creates_audit_log(self, repo: IssueRepository) -> None:
        """Test that get_next_issue creates a FETCH audit log entry."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Test issue"))

        # Fetch it
        repo.get_next_issue()

        # Check audit logs
        logs = repo.get_audit_logs(issue_id=issue.id)

        # Should have CREATE and FETCH
        assert len(logs) == 2

        # Most recent first
        fetch_log = logs[0]
        assert fetch_log.action == "FETCH"
        assert fetch_log.issue_id == issue.id
        assert fetch_log.new_value is not None

        create_log = logs[1]
        assert create_log.action == "CREATE"

    def test_no_fetch_log_when_disabled(self, repo: IssueRepository) -> None:
        """Test that log_fetch=False doesn't create audit log entry."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Test issue"))

        # Fetch without logging
        repo.get_next_issue(log_fetch=False)

        # Check audit logs
        logs = repo.get_audit_logs(issue_id=issue.id)

        # Should only have CREATE
        assert len(logs) == 1
        assert logs[0].action == "CREATE"

    def test_multiple_fetches_create_multiple_logs(self, repo: IssueRepository) -> None:
        """Test that multiple fetches create multiple audit log entries."""
        # Create an issue
        issue = repo.create_issue(Issue(title="Test issue"))

        # Fetch it multiple times
        for _ in range(3):
            repo.get_next_issue()

        # Check audit logs
        logs = repo.get_audit_logs(issue_id=issue.id)

        # Should have 1 CREATE + 3 FETCH
        assert len(logs) == 4

        fetch_logs = [log for log in logs if log.action == "FETCH"]
        assert len(fetch_logs) == 3
