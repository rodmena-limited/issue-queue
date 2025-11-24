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
            project="TestProject",
            description="Test description",
            priority="high",
        )

        assert "Test Issue" in output
        assert "TestProject" in output
        assert "high" in output

        # Test JSON output
        json_output = cli.create_issue(
            title="JSON Issue",
            project="TestProject",
            as_json=True,
        )
        data = json.loads(json_output)
        assert data["title"] == "JSON Issue"
        assert data["project"] == "TestProject"

    def test_list_issues(self, cli):
        """Test listing issues via CLI."""
        # Create test issues
        cli.create_issue("Issue 1", "ProjectA")
        cli.create_issue("Issue 2", "ProjectB")

        output = cli.list_issues()
        assert "Issue 1" in output
        assert "Issue 2" in output

        # Test with filter
        output = cli.list_issues(project="ProjectA")
        assert "Issue 1" in output
        assert "Issue 2" not in output

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
        created_output = cli.create_issue("Test", "Project")
        # Extract ID from output (assuming format "ID: 1")
        lines = created_output.split("\n")
        id_line = [line for line in lines if line.startswith("ID:")][0]
        issue_id = int(id_line.split(":")[1].strip())

        output = cli.get_issue(issue_id)
        assert "Test" in output
        assert "Project" in output

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
        created_output = cli.create_issue("Original", "Project")
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
        created_output = cli.create_issue("To Delete", "Project")
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
        cli.create_issue("Low", "Project", priority="low")
        cli.create_issue("High", "Project", priority="high")

        output = cli.get_next_issue()
        assert "High" in output  # High priority should be returned

        # Test with no issues
        cli.clear_project("Project", confirm=True)
        output = cli.get_next_issue()
        assert "No issues found" in output

    def test_search_issues(self, cli):
        """Test searching issues."""
        cli.create_issue("Bug in login", "Project", description="Login fails")
        cli.create_issue("Feature request", "Project", description="New feature")

        output = cli.search_issues("bug")
        assert "Bug in login" in output
        assert "Feature request" not in output

        # Test JSON output
        json_output = cli.search_issues("feature", as_json=True)
        data = json.loads(json_output)
        assert len(data) == 1

    def test_clear_project(self, cli):
        """Test clearing project."""
        cli.create_issue("Issue 1", "ProjectA")
        cli.create_issue("Issue 2", "ProjectA")
        cli.create_issue("Issue 3", "ProjectB")

        # Test without confirmation
        with pytest.raises(ValueError, match="Must use --confirm"):
            cli.clear_project("ProjectA")

        # Test with confirmation
        output = cli.clear_project("ProjectA", confirm=True)
        assert "Cleared 2 issues" in output

        # Verify only ProjectB remains
        remaining = cli.list_issues()
        assert "ProjectA" not in remaining
        assert "ProjectB" in remaining

    def test_get_audit_logs(self, cli):
        """Test getting audit logs."""
        created_output = cli.create_issue("Test", "Project")
        lines = created_output.split("\n")
        id_line = [line for line in lines if line.startswith("ID:")][0]
        issue_id = int(id_line.split(":")[1].strip())

        cli.update_issue(issue_id, status="closed")

        output = cli.get_audit_logs(issue_id=issue_id)
        assert "CREATE" in output
        assert "UPDATE" in output

        # Test JSON output
        json_output = cli.get_audit_logs(project="Project", as_json=True)
        data = json.loads(json_output)
        assert len(data) == 2

    def test_get_info(self, cli):
        """Test getting database info."""
        cli.create_issue("Issue 1", "ProjectA")
        cli.create_issue("Issue 2", "ProjectB")

        output = cli.get_info()
        assert "Issue Count: 2" in output
        assert "Project Count: 2" in output

        # Test JSON output
        json_output = cli.get_info(as_json=True)
        data = json.loads(json_output)
        assert data["issue_count"] == 2
        assert data["project_count"] == 2

    def test_format_output_various_types(self, cli):
        """Test formatting various data types."""
        # Test Issue
        issue = Issue(id=1, title="Test", project="Project")
        output = cli.format_output(issue)
        assert "ID: 1" in output

        # Test list of Issues
        issues = [issue, Issue(id=2, title="Test2", project="Project")]
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
