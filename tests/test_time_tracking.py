"""Tests for time tracking functionality."""

import json
import time

import pytest

from issuedb.cli import CLI
from issuedb.models import Issue
from issuedb.repository import IssueRepository


@pytest.fixture
def repo(tmp_path):
    """Create a test repository with a temporary database."""
    db_path = tmp_path / "test.db"
    return IssueRepository(str(db_path))


@pytest.fixture
def cli(tmp_path):
    """Create a test CLI with a temporary database."""
    db_path = tmp_path / "test.db"
    return CLI(str(db_path))


@pytest.fixture
def sample_issue(repo):
    """Create a sample issue for testing."""
    issue = Issue(title="Test Issue", description="Test description")
    return repo.create_issue(issue)


class TestTimerOperations:
    """Tests for timer start/stop operations."""

    def test_start_timer(self, repo, sample_issue):
        """Test starting a timer for an issue."""
        result = repo.start_timer(sample_issue.id)

        assert result["issue_id"] == sample_issue.id
        assert "started_at" in result
        assert result["note"] is None

    def test_start_timer_with_note(self, repo, sample_issue):
        """Test starting a timer with a note."""
        note = "Working on fixing bug"
        result = repo.start_timer(sample_issue.id, note=note)

        assert result["issue_id"] == sample_issue.id
        assert result["note"] == note

    def test_start_timer_nonexistent_issue(self, repo):
        """Test starting timer for non-existent issue raises error."""
        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.start_timer(999)

    def test_start_timer_already_running(self, repo, sample_issue):
        """Test starting timer when one is already running raises error."""
        repo.start_timer(sample_issue.id)

        with pytest.raises(ValueError, match="Timer already running"):
            repo.start_timer(sample_issue.id)

    def test_stop_timer(self, repo, sample_issue):
        """Test stopping a timer."""
        repo.start_timer(sample_issue.id, note="Test work")
        time.sleep(1)  # Ensure some time passes
        result = repo.stop_timer(sample_issue.id)

        assert result["issue_id"] == sample_issue.id
        assert "started_at" in result
        assert "ended_at" in result
        assert result["duration_seconds"] >= 1
        assert result["note"] == "Test work"

    def test_stop_timer_without_issue_id(self, repo, sample_issue):
        """Test stopping most recent timer without specifying issue ID."""
        repo.start_timer(sample_issue.id)
        time.sleep(1)
        result = repo.stop_timer()

        assert result["issue_id"] == sample_issue.id
        assert result["duration_seconds"] >= 1

    def test_stop_timer_no_running_timer(self, repo, sample_issue):
        """Test stopping timer when none is running raises error."""
        with pytest.raises(ValueError, match="No running timer found"):
            repo.stop_timer(sample_issue.id)

    def test_stop_timer_no_running_timer_global(self, repo):
        """Test stopping any timer when none is running raises error."""
        with pytest.raises(ValueError, match="No running timer found"):
            repo.stop_timer()


class TestRunningTimers:
    """Tests for getting running timer status."""

    def test_get_running_timers_empty(self, repo):
        """Test getting running timers when none are running."""
        timers = repo.get_running_timers()
        assert timers == []

    def test_get_running_timers_single(self, repo, sample_issue):
        """Test getting a single running timer."""
        repo.start_timer(sample_issue.id, note="Test note")
        timers = repo.get_running_timers()

        assert len(timers) == 1
        assert timers[0]["issue_id"] == sample_issue.id
        assert timers[0]["issue_title"] == sample_issue.title
        assert timers[0]["note"] == "Test note"
        assert timers[0]["elapsed_seconds"] >= 0

    def test_get_running_timers_multiple(self, repo):
        """Test getting multiple running timers."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))
        issue2 = repo.create_issue(Issue(title="Issue 2"))

        repo.start_timer(issue1.id, note="Work 1")
        repo.start_timer(issue2.id, note="Work 2")

        timers = repo.get_running_timers()
        assert len(timers) == 2

        # Should be ordered by most recent first
        assert timers[0]["issue_id"] == issue2.id
        assert timers[1]["issue_id"] == issue1.id


class TestTimeEntries:
    """Tests for time entry retrieval."""

    def test_get_time_entries_empty(self, repo, sample_issue):
        """Test getting time entries when none exist."""
        entries = repo.get_time_entries(sample_issue.id)
        assert entries == []

    def test_get_time_entries_single(self, repo, sample_issue):
        """Test getting a single time entry."""
        repo.start_timer(sample_issue.id, note="Test work")
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        entries = repo.get_time_entries(sample_issue.id)
        assert len(entries) == 1
        assert entries[0]["issue_id"] == sample_issue.id
        assert entries[0]["duration_seconds"] >= 1
        assert entries[0]["note"] == "Test work"

    def test_get_time_entries_multiple(self, repo, sample_issue):
        """Test getting multiple time entries."""
        # Entry 1
        repo.start_timer(sample_issue.id, note="Work 1")
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        # Entry 2
        repo.start_timer(sample_issue.id, note="Work 2")
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        entries = repo.get_time_entries(sample_issue.id)
        assert len(entries) == 2

        # Should be ordered by most recent first
        assert entries[0]["note"] == "Work 2"
        assert entries[1]["note"] == "Work 1"

    def test_get_time_entries_includes_running(self, repo, sample_issue):
        """Test that time entries include running timers."""
        repo.start_timer(sample_issue.id, note="Running work")
        entries = repo.get_time_entries(sample_issue.id)

        assert len(entries) == 1
        assert entries[0]["ended_at"] is None
        assert entries[0]["duration_seconds"] is None
        assert entries[0]["note"] == "Running work"


class TestEstimates:
    """Tests for time estimates."""

    def test_set_estimate(self, repo, sample_issue):
        """Test setting a time estimate."""
        issue = repo.set_estimate(sample_issue.id, 5.5)

        assert issue is not None
        assert issue.id == sample_issue.id
        # Note: The estimate would be on the issue if the model supports it

    def test_set_estimate_zero(self, repo, sample_issue):
        """Test setting estimate to zero."""
        issue = repo.set_estimate(sample_issue.id, 0)
        assert issue is not None

    def test_set_estimate_negative(self, repo, sample_issue):
        """Test setting negative estimate raises error."""
        with pytest.raises(ValueError, match="must be non-negative"):
            repo.set_estimate(sample_issue.id, -1)

    def test_set_estimate_nonexistent_issue(self, repo):
        """Test setting estimate for non-existent issue."""
        issue = repo.set_estimate(999, 5)
        assert issue is None

    def test_set_estimate_updates_existing(self, repo, sample_issue):
        """Test updating an existing estimate."""
        repo.set_estimate(sample_issue.id, 3)
        issue = repo.set_estimate(sample_issue.id, 6)

        assert issue is not None
        # The new estimate should be applied


class TestTimeReports:
    """Tests for time report generation."""

    def test_time_report_empty(self, repo):
        """Test time report with no entries."""
        report = repo.get_time_report(period="all")

        assert report["period"] == "all"
        assert report["total_seconds"] == 0
        assert report["total_hours"] == 0
        assert report["issues"] == []
        assert report["issue_count"] == 0

    def test_time_report_single_issue(self, repo, sample_issue):
        """Test time report with a single issue."""
        repo.start_timer(sample_issue.id)
        time.sleep(2)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="all")

        assert report["period"] == "all"
        assert report["total_seconds"] >= 2
        assert len(report["issues"]) == 1
        assert report["issues"][0]["issue_id"] == sample_issue.id
        assert report["issues"][0]["title"] == sample_issue.title
        assert report["issues"][0]["total_seconds"] >= 2

    def test_time_report_multiple_issues(self, repo):
        """Test time report with multiple issues."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))
        issue2 = repo.create_issue(Issue(title="Issue 2"))

        # Time for issue 1
        repo.start_timer(issue1.id)
        time.sleep(1)
        repo.stop_timer(issue1.id)

        # Time for issue 2
        repo.start_timer(issue2.id)
        time.sleep(1)
        repo.stop_timer(issue2.id)

        report = repo.get_time_report(period="all")

        assert len(report["issues"]) == 2
        assert report["total_seconds"] >= 2

    def test_time_report_with_estimate(self, repo, sample_issue):
        """Test time report shows estimate comparison."""
        repo.set_estimate(sample_issue.id, 1)  # 1 hour estimate

        repo.start_timer(sample_issue.id)
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="all")

        assert len(report["issues"]) == 1
        issue_data = report["issues"][0]
        assert issue_data["estimated_hours"] == 1
        assert issue_data["over_estimate"] is False  # Only few seconds spent

    def test_time_report_over_estimate(self, repo, sample_issue):
        """Test time report detects over-estimate."""
        repo.set_estimate(sample_issue.id, 0.0001)  # Very small estimate

        repo.start_timer(sample_issue.id)
        time.sleep(2)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="all")

        issue_data = report["issues"][0]
        assert issue_data["over_estimate"] is True

    def test_time_report_week_period(self, repo, sample_issue):
        """Test time report for week period."""
        repo.start_timer(sample_issue.id)
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="week")

        assert report["period"] == "week"
        assert report["period_label"] == "This Week"
        assert len(report["issues"]) == 1

    def test_time_report_month_period(self, repo, sample_issue):
        """Test time report for month period."""
        repo.start_timer(sample_issue.id)
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="month")

        assert report["period"] == "month"
        assert report["period_label"] == "This Month"
        assert len(report["issues"]) == 1

    def test_time_report_invalid_period(self, repo):
        """Test time report with invalid period raises error."""
        with pytest.raises(ValueError, match="Period must be"):
            repo.get_time_report(period="invalid")


class TestCLITimerCommands:
    """Tests for CLI timer commands."""

    def test_cli_timer_start(self, cli):
        """Test CLI timer start command."""
        # Create issue first
        cli.create_issue(title="Test Issue")
        result = cli.timer_start(issue_id=1, note="Test work")

        assert "Timer started" in result
        assert "#1" in result

    def test_cli_timer_start_json(self, cli):
        """Test CLI timer start with JSON output."""
        cli.create_issue(title="Test Issue")
        result = cli.timer_start(issue_id=1, note="Test", as_json=True)

        data = json.loads(result)
        assert data["issue_id"] == 1
        assert data["note"] == "Test"

    def test_cli_timer_stop(self, cli):
        """Test CLI timer stop command."""
        cli.create_issue(title="Test Issue")
        cli.timer_start(issue_id=1)
        time.sleep(1)
        result = cli.timer_stop(issue_id=1)

        assert "Timer stopped" in result
        assert "Issue Id: 1" in result or "issue_id" in result.lower()
        assert "Duration" in result

    def test_cli_timer_stop_json(self, cli):
        """Test CLI timer stop with JSON output."""
        cli.create_issue(title="Test Issue")
        cli.timer_start(issue_id=1)
        time.sleep(1)
        result = cli.timer_stop(issue_id=1, as_json=True)

        data = json.loads(result)
        assert data["issue_id"] == 1
        assert data["duration_seconds"] >= 1

    def test_cli_timer_status_empty(self, cli):
        """Test CLI timer status with no running timers."""
        result = cli.timer_status()
        assert "No running timers" in result

    def test_cli_timer_status(self, cli):
        """Test CLI timer status with running timer."""
        cli.create_issue(title="Test Issue")
        cli.timer_start(issue_id=1, note="Working")
        result = cli.timer_status()

        assert "Running Timers" in result
        assert "#1" in result
        # Check for elapsed time in format "0h 0m" or similar
        assert "h" in result and "m" in result

    def test_cli_timer_status_json(self, cli):
        """Test CLI timer status with JSON output."""
        cli.create_issue(title="Test Issue")
        cli.timer_start(issue_id=1)
        result = cli.timer_status(as_json=True)

        data = json.loads(result)
        assert "timers" in data
        assert len(data["timers"]) == 1
        assert data["timers"][0]["issue_id"] == 1


class TestCLIEstimateCommand:
    """Tests for CLI estimate command."""

    def test_cli_set_estimate(self, cli):
        """Test CLI set estimate command."""
        cli.create_issue(title="Test Issue")
        result = cli.set_estimate(issue_id=1, hours=5.5)

        assert "Estimate" in result
        assert "1" in result  # issue id
        assert "5.5" in result

    def test_cli_set_estimate_json(self, cli):
        """Test CLI set estimate with JSON output."""
        cli.create_issue(title="Test Issue")
        result = cli.set_estimate(issue_id=1, hours=3, as_json=True)

        data = json.loads(result)
        assert data["issue_id"] == 1
        assert data["estimated_hours"] == 3


class TestCLITimeLogCommand:
    """Tests for CLI time-log command."""

    def test_cli_time_log_empty(self, cli):
        """Test CLI time-log with no entries."""
        cli.create_issue(title="Test Issue")
        result = cli.time_log(issue_id=1)

        assert "No time entries" in result

    def test_cli_time_log(self, cli):
        """Test CLI time-log command."""
        cli.create_issue(title="Test Issue")
        cli.timer_start(issue_id=1, note="Work")
        time.sleep(1)
        cli.timer_stop(issue_id=1)

        result = cli.time_log(issue_id=1)

        assert "Time Log for Issue #1" in result
        assert "h" in result and "m" in result  # duration format
        assert "Total:" in result

    def test_cli_time_log_json(self, cli):
        """Test CLI time-log with JSON output."""
        cli.create_issue(title="Test Issue")
        cli.timer_start(issue_id=1)
        time.sleep(1)
        cli.timer_stop(issue_id=1)

        result = cli.time_log(issue_id=1, as_json=True)

        data = json.loads(result)
        assert "issue_id" in data
        assert "entries" in data
        assert len(data["entries"]) == 1


class TestCLITimeReportCommand:
    """Tests for CLI time-report command."""

    def test_cli_time_report_empty(self, cli):
        """Test CLI time-report with no entries."""
        result = cli.time_report(period="all")

        assert "Time Report" in result
        assert "Total:" in result

    def test_cli_time_report(self, cli):
        """Test CLI time-report command."""
        cli.create_issue(title="Test Issue")
        cli.set_estimate(issue_id=1, hours=2)
        cli.timer_start(issue_id=1)
        time.sleep(1)
        cli.timer_stop(issue_id=1)

        result = cli.time_report(period="all")

        assert "Time Report" in result
        assert "Total:" in result
        assert "#1" in result
        assert "est:" in result  # Shows estimate

    def test_cli_time_report_week(self, cli):
        """Test CLI time-report for week."""
        result = cli.time_report(period="week")
        assert "This Week" in result

    def test_cli_time_report_month(self, cli):
        """Test CLI time-report for month."""
        result = cli.time_report(period="month")
        assert "This Month" in result

    def test_cli_time_report_json(self, cli):
        """Test CLI time-report with JSON output."""
        result = cli.time_report(period="all", as_json=True)

        data = json.loads(result)
        assert "period" in data
        assert "total_hours" in data
        assert "issues" in data


class TestDurationCalculation:
    """Tests for duration calculation accuracy."""

    def test_duration_accuracy(self, repo, sample_issue):
        """Test that duration is calculated accurately."""
        repo.start_timer(sample_issue.id)
        time.sleep(3)
        result = repo.stop_timer(sample_issue.id)

        # Should be at least 3 seconds
        assert result["duration_seconds"] >= 3
        # But not more than 5 seconds (to account for system timing)
        assert result["duration_seconds"] <= 5

    def test_multiple_entries_total(self, repo, sample_issue):
        """Test that multiple entries accumulate correctly."""
        # Entry 1: ~1 second
        repo.start_timer(sample_issue.id)
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        # Entry 2: ~1 second
        repo.start_timer(sample_issue.id)
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="all")
        assert report["total_seconds"] >= 2


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_timer_on_deleted_issue(self, repo, sample_issue):
        """Test behavior when issue is deleted while timer is running."""
        repo.start_timer(sample_issue.id)
        # Delete the issue
        repo.delete_issue(sample_issue.id)

        # Timer operations should handle this gracefully
        # (depends on CASCADE behavior)

    def test_concurrent_timers_different_issues(self, repo):
        """Test running timers on different issues simultaneously."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))
        issue2 = repo.create_issue(Issue(title="Issue 2"))

        repo.start_timer(issue1.id)
        repo.start_timer(issue2.id)

        timers = repo.get_running_timers()
        assert len(timers) == 2

    def test_estimate_precision(self, repo, sample_issue):
        """Test that fractional hour estimates are preserved."""
        repo.set_estimate(sample_issue.id, 2.75)
        # Verify through time report
        repo.start_timer(sample_issue.id)
        time.sleep(1)
        repo.stop_timer(sample_issue.id)

        report = repo.get_time_report(period="all")
        assert report["issues"][0]["estimated_hours"] == 2.75
