"""Tests for CLI module."""

import json
import tempfile

import pytest

from issuedb.cli import CLI
from issuedb.models import Issue


class TestCLI:
    """Test CLI class."""

    @pytest.fixture
    def cli(self):
        """Create CLI with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            cli = CLI(f.name)
            yield cli

    def test_create_issue(self, cli):
        """Test creating an issue via CLI."""
        output = cli.create_issue(
            title="Test Issue",
            description="Test description",
            priority="high",
        )

        assert "Test Issue" in output
        assert "high" in output

        # Test JSON output
        json_output = cli.create_issue(
            title="JSON Issue",
            as_json=True,
        )
        data = json.loads(json_output)
        assert data["title"] == "JSON Issue"

    def test_list_issues(self, cli):
        """Test listing issues via CLI."""
        # Create test issues
        cli.create_issue("Issue 1")
        cli.create_issue("Issue 2")

        output = cli.list_issues()
        assert "Issue 1" in output
        assert "Issue 2" in output

        # Test JSON output
        json_output = cli.list_issues(as_json=True)
        data = json.loads(json_output)
        assert len(data) == 2

    def test_list_issues_empty(self, cli):
        """Test listing issues when none exist."""
        output = cli.list_issues()
        assert output == "No issues found."

        json_output = cli.list_issues(as_json=True)
        data = json.loads(json_output)
        assert data == []

    def test_get_issue(self, cli):
        """Test getting a specific issue."""
        created_output = cli.create_issue("Test")
        # Extract ID from output (assuming format "ID: 1")
        lines = created_output.split("\n")
        id_line = [line for line in lines if line.startswith("ID:")][0]
        issue_id = int(id_line.split(":")[1].strip())

        output = cli.get_issue(issue_id)
        assert "Test" in output

        # Test JSON output
        json_output = cli.get_issue(issue_id, as_json=True)
        data = json.loads(json_output)
        assert data["id"] == issue_id

    def test_get_issue_not_found(self, cli):
        """Test getting non-existent issue raises error."""
        with pytest.raises(ValueError, match="Issue 999 not found"):
            cli.get_issue(999)

    def test_update_issue(self, cli):
        """Test updating an issue."""
        created_output = cli.create_issue("Original")
        lines = created_output.split("\n")
        id_line = [line for line in lines if line.startswith("ID:")][0]
        issue_id = int(id_line.split(":")[1].strip())

        output = cli.update_issue(
            issue_id,
            title="Updated",
            status="in-progress",
        )
        assert "Updated" in output
        assert "in-progress" in output

        # Test JSON output
        json_output = cli.update_issue(
            issue_id,
            priority="critical",
            as_json=True,
        )
        data = json.loads(json_output)
        assert data["priority"] == "critical"

    def test_delete_issue(self, cli):
        """Test deleting an issue."""
        created_output = cli.create_issue("To Delete")
        lines = created_output.split("\n")
        id_line = [line for line in lines if line.startswith("ID:")][0]
        issue_id = int(id_line.split(":")[1].strip())

        output = cli.delete_issue(issue_id)
        assert "deleted successfully" in output

        # Verify deletion
        with pytest.raises(ValueError):
            cli.get_issue(issue_id)

    def test_get_next_issue(self, cli):
        """Test getting next issue."""
        # Create issues with different priorities
        cli.create_issue("Low", priority="low")
        cli.create_issue("High", priority="high")

        output = cli.get_next_issue()
        assert "High" in output  # High priority should be returned

        # Test with no issues
        cli.clear_all(confirm=True)
        output = cli.get_next_issue()
        assert "No issues found" in output

    def test_search_issues(self, cli):
        """Test searching issues."""
        cli.create_issue("Bug in login", description="Login fails")
        cli.create_issue("Feature request", description="New feature")

        output = cli.search_issues("bug")
        assert "Bug in login" in output
        assert "Feature request" not in output

        # Test JSON output
        json_output = cli.search_issues("feature", as_json=True)
        data = json.loads(json_output)
        assert len(data) == 1

    def test_clear_all(self, cli):
        """Test clearing all issues."""
        cli.create_issue("Issue 1")
        cli.create_issue("Issue 2")
        cli.create_issue("Issue 3")

        # Test without confirmation
        with pytest.raises(ValueError, match="Must use --confirm"):
            cli.clear_all()

        # Test with confirmation
        output = cli.clear_all(confirm=True)
        assert "Cleared 3 issues" in output

        # Verify all issues are gone
        remaining = cli.list_issues()
        assert "No issues found" in remaining

    def test_get_audit_logs(self, cli):
        """Test getting audit logs."""
        created_output = cli.create_issue("Test")
        lines = created_output.split("\n")
        id_line = [line for line in lines if line.startswith("ID:")][0]
        issue_id = int(id_line.split(":")[1].strip())

        cli.update_issue(issue_id, status="closed")

        output = cli.get_audit_logs(issue_id=issue_id)
        assert "CREATE" in output
        assert "UPDATE" in output

        # Test JSON output
        json_output = cli.get_audit_logs(issue_id=issue_id, as_json=True)
        data = json.loads(json_output)
        assert len(data) == 2

    def test_get_info(self, cli):
        """Test getting database info."""
        cli.create_issue("Issue 1")
        cli.create_issue("Issue 2")

        output = cli.get_info()
        assert "Issue Count: 2" in output

        # Test JSON output
        json_output = cli.get_info(as_json=True)
        data = json.loads(json_output)
        assert data["issue_count"] == 2

    def test_get_summary(self, cli):
        """Test getting summary statistics."""
        cli.create_issue("Issue 1", priority="high")
        cli.create_issue("Issue 2", status="closed")

        output = cli.get_summary()
        assert "Total Issues: 2" in output

        # Test JSON output
        json_output = cli.get_summary(as_json=True)
        data = json.loads(json_output)
        assert data["total_issues"] == 2

    def test_get_report(self, cli):
        """Test getting detailed report."""
        cli.create_issue("Issue 1", status="open")
        cli.create_issue("Issue 2", status="closed")

        output = cli.get_report()
        assert "Status: open" in output or "open" in output.lower()

        # Test JSON output
        json_output = cli.get_report(as_json=True)
        data = json.loads(json_output)
        assert data["total_issues"] == 2

    def test_format_output_various_types(self, cli):
        """Test formatting various data types."""
        # Test Issue
        issue = Issue(id=1, title="Test")
        output = cli.format_output(issue)
        assert "ID: 1" in output

        # Test list of Issues
        issues = [issue, Issue(id=2, title="Test2")]
        output = cli.format_output(issues)
        assert "ID: 1" in output
        assert "ID: 2" in output

        # Test dict
        data = {"key": "value", "another_key": 123}
        output = cli.format_output(data)
        assert "Key: value" in output
        assert "Another Key: 123" in output

        # Test JSON formatting
        json_output = cli.format_output(issue, as_json=True)
        data = json.loads(json_output)
        assert data["id"] == 1
