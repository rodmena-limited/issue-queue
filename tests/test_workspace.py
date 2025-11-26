"""Tests for workspace functionality."""

import tempfile
from datetime import datetime
from time import sleep

import pytest

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


class TestWorkspace:
    """Test workspace awareness features."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            repo = IssueRepository(f.name)
            yield repo

    @pytest.fixture
    def sample_issue(self, repo):
        """Create and return a sample issue."""
        issue = Issue(
            title="Test Issue",
            description="Test description",
            priority=Priority.MEDIUM,
            status=Status.OPEN,
        )
        return repo.create_issue(issue)

    @pytest.fixture
    def another_issue(self, repo):
        """Create and return another sample issue."""
        issue = Issue(
            title="Another Test Issue",
            description="Another test description",
            priority=Priority.HIGH,
            status=Status.OPEN,
        )
        return repo.create_issue(issue)

    def test_get_active_issue_none(self, repo):
        """Test getting active issue when none is set."""
        result = repo.get_active_issue()
        assert result is None

    def test_start_issue(self, repo, sample_issue):
        """Test starting an issue."""
        issue, started_at = repo.start_issue(sample_issue.id)

        assert issue.id == sample_issue.id
        assert issue.status == Status.IN_PROGRESS
        assert isinstance(started_at, datetime)

        # Verify workspace state
        active = repo.get_active_issue()
        assert active is not None
        active_issue, active_started = active
        assert active_issue.id == sample_issue.id
        assert active_started == started_at

    def test_start_issue_not_found(self, repo):
        """Test starting a non-existent issue raises error."""
        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.start_issue(999)

    def test_start_issue_auto_updates_status(self, repo, sample_issue):
        """Test that starting an issue auto-updates status to in-progress."""
        assert sample_issue.status == Status.OPEN

        issue, _ = repo.start_issue(sample_issue.id)

        assert issue.status == Status.IN_PROGRESS

        # Verify in database
        retrieved = repo.get_issue(sample_issue.id)
        assert retrieved.status == Status.IN_PROGRESS

    def test_start_issue_replaces_previous_active(self, repo, sample_issue, another_issue):
        """Test that starting a new issue replaces the previous active issue."""
        # Start first issue
        repo.start_issue(sample_issue.id)

        # Start second issue
        issue2, started_at2 = repo.start_issue(another_issue.id)

        # Verify only second issue is active
        active = repo.get_active_issue()
        assert active is not None
        active_issue, active_started = active
        assert active_issue.id == another_issue.id
        assert active_started == started_at2

    def test_stop_issue(self, repo, sample_issue):
        """Test stopping an active issue."""
        # Start issue
        issue, started_at = repo.start_issue(sample_issue.id)

        # Add a small delay to ensure time difference
        sleep(0.1)

        # Stop issue
        result = repo.stop_issue()
        assert result is not None

        stopped_issue, stopped_started, stopped_at = result
        assert stopped_issue.id == sample_issue.id
        assert stopped_started == started_at
        assert isinstance(stopped_at, datetime)
        assert stopped_at > started_at

        # Verify no active issue
        active = repo.get_active_issue()
        assert active is None

    def test_stop_issue_when_none_active(self, repo):
        """Test stopping when no issue is active."""
        result = repo.stop_issue()
        assert result is None

    def test_stop_issue_with_close(self, repo, sample_issue):
        """Test stopping an issue and closing it."""
        # Start issue
        repo.start_issue(sample_issue.id)

        # Stop and close
        result = repo.stop_issue(close=True)
        assert result is not None

        stopped_issue, _, _ = result
        assert stopped_issue.status == Status.CLOSED

        # Verify in database
        retrieved = repo.get_issue(sample_issue.id)
        assert retrieved.status == Status.CLOSED

    def test_stop_issue_without_close(self, repo, sample_issue):
        """Test stopping an issue without closing it."""
        # Start issue (auto sets to in-progress)
        repo.start_issue(sample_issue.id)

        # Stop without closing
        result = repo.stop_issue(close=False)
        assert result is not None

        stopped_issue, _, _ = result
        assert stopped_issue.status == Status.IN_PROGRESS

        # Verify in database
        retrieved = repo.get_issue(sample_issue.id)
        assert retrieved.status == Status.IN_PROGRESS

    def test_time_calculation(self, repo, sample_issue):
        """Test that time calculation works correctly."""
        # Start issue
        _, started_at = repo.start_issue(sample_issue.id)

        # Wait a bit
        sleep(0.5)

        # Stop issue
        result = repo.stop_issue()
        _, _, stopped_at = result

        # Verify time difference
        time_diff = stopped_at - started_at
        assert time_diff.total_seconds() >= 0.5
        assert time_diff.total_seconds() < 2.0  # Reasonable upper bound

    def test_workspace_status_no_active_issue(self, repo):
        """Test workspace status when no issue is active."""
        status = repo.get_workspace_status()

        assert status["active_issue"] is None
        assert "git_branch" in status
        assert "uncommitted_files" in status
        assert "recent_activity" in status
        assert isinstance(status["recent_activity"], list)

    def test_workspace_status_with_active_issue(self, repo, sample_issue):
        """Test workspace status with an active issue."""
        # Start issue
        issue, started_at = repo.start_issue(sample_issue.id)

        # Get status
        status = repo.get_workspace_status()

        assert status["active_issue"] is not None
        active = status["active_issue"]
        assert active["id"] == sample_issue.id
        assert active["title"] == sample_issue.title
        assert active["status"] == Status.IN_PROGRESS.value
        assert active["priority"] == Priority.MEDIUM.value
        assert "time_spent" in active
        assert "time_spent_seconds" in active
        assert active["time_spent_seconds"] >= 0

    def test_workspace_status_recent_activity(self, repo, sample_issue, another_issue):
        """Test that recent activity is tracked."""
        # Start and stop first issue
        repo.start_issue(sample_issue.id)
        sleep(0.1)
        repo.stop_issue()

        # Start second issue
        repo.start_issue(another_issue.id)

        # Get status
        status = repo.get_workspace_status()

        recent_activity = status["recent_activity"]
        assert len(recent_activity) >= 2  # At least start and stop of first issue

        # Check that activities are in reverse chronological order
        if len(recent_activity) >= 2:
            first_activity = datetime.fromisoformat(recent_activity[0]["timestamp"])
            second_activity = datetime.fromisoformat(recent_activity[1]["timestamp"])
            assert first_activity >= second_activity

    def test_audit_log_workspace_start(self, repo, sample_issue):
        """Test that workspace start is logged in audit log."""
        repo.start_issue(sample_issue.id)

        logs = repo.get_audit_logs(issue_id=sample_issue.id)
        start_logs = [log for log in logs if log.action == "WORKSPACE_START"]

        assert len(start_logs) == 1
        assert start_logs[0].issue_id == sample_issue.id

    def test_audit_log_workspace_stop(self, repo, sample_issue):
        """Test that workspace stop is logged in audit log."""
        repo.start_issue(sample_issue.id)
        repo.stop_issue()

        logs = repo.get_audit_logs(issue_id=sample_issue.id)
        stop_logs = [log for log in logs if log.action == "WORKSPACE_STOP"]

        assert len(stop_logs) == 1
        assert stop_logs[0].issue_id == sample_issue.id

    def test_workspace_persistence(self, repo, sample_issue):
        """Test that workspace state persists across repository instances."""
        # Start issue
        issue, started_at = repo.start_issue(sample_issue.id)

        # Create new repository instance with same database
        repo2 = IssueRepository(repo.db.db_path)

        # Verify active issue is accessible
        active = repo2.get_active_issue()
        assert active is not None
        active_issue, active_started = active
        assert active_issue.id == sample_issue.id
        assert active_started == started_at

    def test_workspace_state_single_row(self, repo, sample_issue, another_issue):
        """Test that workspace_state table maintains only one row."""
        # Start first issue
        repo.start_issue(sample_issue.id)

        # Start second issue
        repo.start_issue(another_issue.id)

        # Verify only one row exists
        with repo.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM workspace_state")
            count = cursor.fetchone()["count"]
            assert count == 1

    def test_deleted_issue_active(self, repo, sample_issue):
        """Test handling when active issue is deleted."""
        # Start issue
        repo.start_issue(sample_issue.id)

        # Delete the issue
        repo.delete_issue(sample_issue.id)

        # Getting active issue should return None (due to ON DELETE SET NULL)
        active = repo.get_active_issue()
        assert active is None

    def test_time_spent_formatting(self, repo, sample_issue):
        """Test that time spent is formatted correctly."""
        # Start issue
        repo.start_issue(sample_issue.id)

        # Get status immediately
        status = repo.get_workspace_status()
        active = status["active_issue"]

        # Time should be "0h 0m" for immediate check
        assert "time_spent" in active
        time_parts = active["time_spent"].split()
        assert len(time_parts) == 2
        assert time_parts[0].endswith("h")
        assert time_parts[1].endswith("m")


class TestWorkspaceCLI:
    """Test workspace CLI commands."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance with temporary database."""
        from issuedb.cli import CLI

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            cli = CLI(f.name)
            yield cli

    @pytest.fixture
    def sample_issue(self, cli):
        """Create a sample issue via CLI."""
        cli.repo.create_issue(
            Issue(
                title="Test Issue",
                description="Test description",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )
        return cli.repo.list_issues()[0]

    def test_workspace_status_cli_no_active(self, cli):
        """Test workspace status CLI command with no active issue."""
        result = cli.workspace_status(as_json=False)
        assert "Workspace Status" in result
        assert "Active Issue: None" in result

    def test_workspace_status_cli_json(self, cli):
        """Test workspace status CLI command with JSON output."""
        import json

        result = cli.workspace_status(as_json=True)
        data = json.loads(result)

        assert "active_issue" in data
        assert "git_branch" in data
        assert "recent_activity" in data

    def test_start_issue_cli(self, cli, sample_issue):
        """Test start issue CLI command."""
        result = cli.start_issue_workspace(sample_issue.id, as_json=False)

        assert f"Started working on issue #{sample_issue.id}" in result
        assert sample_issue.title in result

        # Verify issue is active
        active = cli.repo.get_active_issue()
        assert active is not None
        assert active[0].id == sample_issue.id

    def test_start_issue_cli_json(self, cli, sample_issue):
        """Test start issue CLI command with JSON output."""
        import json

        result = cli.start_issue_workspace(sample_issue.id, as_json=True)
        data = json.loads(result)

        assert data["message"] == f"Started working on issue {sample_issue.id}"
        assert data["issue"]["id"] == sample_issue.id
        assert "started_at" in data

    def test_stop_issue_cli(self, cli, sample_issue):
        """Test stop issue CLI command."""
        # Start issue first
        cli.repo.start_issue(sample_issue.id)

        # Stop issue
        result = cli.stop_issue_workspace(close=False, as_json=False)

        assert f"Stopped working on issue #{sample_issue.id}" in result
        assert "Time spent:" in result

        # Verify no active issue
        active = cli.repo.get_active_issue()
        assert active is None

    def test_stop_issue_cli_with_close(self, cli, sample_issue):
        """Test stop issue CLI command with close flag."""
        # Start issue first
        cli.repo.start_issue(sample_issue.id)

        # Stop and close issue
        result = cli.stop_issue_workspace(close=True, as_json=False)

        assert f"Stopped working on issue #{sample_issue.id}" in result
        assert "Status: closed" in result

        # Verify issue is closed
        issue = cli.repo.get_issue(sample_issue.id)
        assert issue.status == Status.CLOSED

    def test_stop_issue_cli_no_active(self, cli):
        """Test stop issue CLI command when no issue is active."""
        result = cli.stop_issue_workspace(close=False, as_json=False)
        assert "No active issue to stop" in result

    def test_stop_issue_cli_json(self, cli, sample_issue):
        """Test stop issue CLI command with JSON output."""
        import json

        # Start issue first
        cli.repo.start_issue(sample_issue.id)

        # Stop issue
        result = cli.stop_issue_workspace(close=False, as_json=True)
        data = json.loads(result)

        assert data["message"] == f"Stopped working on issue {sample_issue.id}"
        assert "time_spent" in data
        assert "time_spent_seconds" in data

    def test_get_active_issue_cli(self, cli, sample_issue):
        """Test get active issue CLI command."""
        # Start issue first
        cli.repo.start_issue(sample_issue.id)

        # Get active issue
        result = cli.get_active_issue_workspace(as_json=False)

        assert f"Active Issue: #{sample_issue.id}" in result
        assert sample_issue.title in result
        assert "Time spent:" in result

    def test_get_active_issue_cli_none(self, cli):
        """Test get active issue CLI command when none is active."""
        result = cli.get_active_issue_workspace(as_json=False)
        assert "No active issue" in result

    def test_get_active_issue_cli_json(self, cli, sample_issue):
        """Test get active issue CLI command with JSON output."""
        import json

        # Start issue first
        cli.repo.start_issue(sample_issue.id)

        # Get active issue
        result = cli.get_active_issue_workspace(as_json=True)
        data = json.loads(result)

        assert data["issue"]["id"] == sample_issue.id
        assert "time_spent" in data
        assert "started_at" in data

    def test_workflow_integration(self, cli, sample_issue):
        """Test full workflow: start -> check active -> stop."""
        # Start issue
        start_result = cli.start_issue_workspace(sample_issue.id, as_json=False)
        assert "Started working" in start_result

        # Check workspace status
        status_result = cli.workspace_status(as_json=False)
        assert f"Active Issue: #{sample_issue.id}" in status_result

        # Check active issue
        active_result = cli.get_active_issue_workspace(as_json=False)
        assert f"Active Issue: #{sample_issue.id}" in active_result

        # Stop issue
        stop_result = cli.stop_issue_workspace(close=False, as_json=False)
        assert "Stopped working" in stop_result

        # Verify no active issue
        final_status = cli.workspace_status(as_json=False)
        assert "Active Issue: None" in final_status
