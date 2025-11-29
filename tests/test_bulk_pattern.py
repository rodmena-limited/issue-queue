"""Tests for bulk pattern operations."""

import tempfile

import pytest

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


class TestBulkPatternOperations:
    """Test bulk pattern matching and operations."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            repo = IssueRepository(f.name)
            yield repo

    @pytest.fixture
    def sample_issues(self, repo):
        """Create sample issues for testing pattern matching."""
        issues = [
            Issue(
                title="SonarQube issue 1",
                description="First SonarQube issue",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                title="SonarQube issue 2",
                description="Second SonarQube issue",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            ),
            Issue(
                title="sonarqube lowercase",
                description="Lowercase test",
                priority=Priority.LOW,
                status=Status.OPEN,
            ),
            Issue(
                title="Different issue",
                description="Something completely different",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                title="Bug in authentication",
                description="Users cannot log in",
                priority=Priority.CRITICAL,
                status=Status.IN_PROGRESS,
            ),
            Issue(
                title="Bug in authorization",
                description="Permission check failing",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
        ]

        created_issues = []
        for issue in issues:
            created = repo.create_issue(issue)
            created_issues.append(created)

        return created_issues

    def test_find_by_pattern_glob_title(self, repo, sample_issues):
        """Test finding issues by glob pattern in title."""
        # Match "SonarQube*" (case-insensitive by default)
        matches = repo.find_by_pattern(title_pattern="sonarqube*", use_regex=False)
        assert len(matches) == 3
        titles = [issue.title for issue in matches]
        assert "SonarQube issue 1" in titles
        assert "SonarQube issue 2" in titles
        assert "sonarqube lowercase" in titles

    def test_find_by_pattern_glob_title_case_sensitive(self, repo, sample_issues):
        """Test finding issues by glob pattern with case sensitivity."""
        # Match "SonarQube*" (case-sensitive)
        matches = repo.find_by_pattern(
            title_pattern="SonarQube*", use_regex=False, case_sensitive=True
        )
        assert len(matches) == 2
        titles = [issue.title for issue in matches]
        assert "SonarQube issue 1" in titles
        assert "SonarQube issue 2" in titles
        assert "sonarqube lowercase" not in titles

    def test_find_by_pattern_regex_title(self, repo, sample_issues):
        """Test finding issues by regex pattern in title."""
        # Match anything starting with "Bug"
        matches = repo.find_by_pattern(title_pattern="^Bug", use_regex=True)
        assert len(matches) == 2
        titles = [issue.title for issue in matches]
        assert "Bug in authentication" in titles
        assert "Bug in authorization" in titles

    def test_find_by_pattern_regex_title_case_sensitive(self, repo, sample_issues):
        """Test finding issues by regex pattern with case sensitivity."""
        # Match anything with "sonarqube" (lowercase) using regex
        matches = repo.find_by_pattern(
            title_pattern="sonarqube", use_regex=True, case_sensitive=True
        )
        assert len(matches) == 1
        assert matches[0].title == "sonarqube lowercase"

        # Match anything with "SonarQube" (mixed case) using regex
        matches = repo.find_by_pattern(
            title_pattern="SonarQube", use_regex=True, case_sensitive=True
        )
        assert len(matches) == 2

    def test_find_by_pattern_description_glob(self, repo, sample_issues):
        """Test finding issues by glob pattern in description."""
        # Match descriptions containing "SonarQube"
        matches = repo.find_by_pattern(desc_pattern="*sonarqube*", use_regex=False)
        assert len(matches) == 2
        descriptions = [issue.description for issue in matches]
        assert "First SonarQube issue" in descriptions
        assert "Second SonarQube issue" in descriptions

    def test_find_by_pattern_description_regex(self, repo, sample_issues):
        """Test finding issues by regex pattern in description."""
        # Match descriptions containing "log in" or "failing"
        matches = repo.find_by_pattern(desc_pattern="log in|failing", use_regex=True)
        assert len(matches) == 2

    def test_find_by_pattern_title_and_description(self, repo, sample_issues):
        """Test finding issues by both title and description patterns."""
        # Match title "Bug*" AND description containing "cannot" or "check"
        matches = repo.find_by_pattern(
            title_pattern="Bug*", desc_pattern="*check*", use_regex=False
        )
        # Only "Bug in authorization" has "check" in description
        assert len(matches) == 1
        assert matches[0].title == "Bug in authorization"

        # Match title "Bug*" AND description containing "Users" or "Permission"
        matches = repo.find_by_pattern(
            title_pattern="Bug*", desc_pattern="*Users*", use_regex=False
        )
        # Only "Bug in authentication" has "Users" in description
        assert len(matches) == 1
        assert matches[0].title == "Bug in authentication"

    def test_find_by_pattern_no_matches(self, repo, sample_issues):
        """Test finding issues with pattern that matches nothing."""
        matches = repo.find_by_pattern(title_pattern="NonExistent*", use_regex=False)
        assert len(matches) == 0

    def test_find_by_pattern_wildcard(self, repo, sample_issues):
        """Test finding all issues with wildcard pattern."""
        matches = repo.find_by_pattern(title_pattern="*", use_regex=False)
        assert len(matches) == 6  # All sample issues

    def test_bulk_close_by_pattern_glob(self, repo, sample_issues):
        """Test bulk closing issues by glob pattern."""
        # Close all SonarQube issues
        closed = repo.bulk_close_by_pattern(title_pattern="sonarqube*", use_regex=False)
        assert len(closed) == 3

        # Verify they are closed
        for issue in closed:
            assert issue.status == Status.CLOSED
            retrieved = repo.get_issue(issue.id)
            assert retrieved is not None
            assert retrieved.status == Status.CLOSED

    def test_bulk_close_by_pattern_regex(self, repo, sample_issues):
        """Test bulk closing issues by regex pattern."""
        # Close all Bug issues
        closed = repo.bulk_close_by_pattern(title_pattern="^Bug", use_regex=True)
        assert len(closed) == 2

        # Verify they are closed
        for issue in closed:
            assert issue.status == Status.CLOSED

    def test_bulk_close_by_pattern_dry_run(self, repo, sample_issues):
        """Test bulk close dry-run mode."""
        # Dry run should return matches without changing anything
        matches = repo.bulk_close_by_pattern(
            title_pattern="sonarqube*", use_regex=False, dry_run=True
        )
        assert len(matches) == 3

        # Verify nothing was actually closed
        for issue in matches:
            retrieved = repo.get_issue(issue.id)
            assert retrieved is not None
            assert retrieved.status == Status.OPEN

    def test_bulk_update_by_pattern_status(self, repo, sample_issues):
        """Test bulk updating issue status by pattern."""
        # Update all SonarQube issues to in-progress
        updated = repo.bulk_update_by_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            new_status="in-progress",
        )
        assert len(updated) == 3

        # Verify they are updated
        for issue in updated:
            assert issue.status == Status.IN_PROGRESS

    def test_bulk_update_by_pattern_priority(self, repo, sample_issues):
        """Test bulk updating issue priority by pattern."""
        # Update all Bug issues to critical priority
        updated = repo.bulk_update_by_pattern(
            title_pattern="^Bug",
            use_regex=True,
            new_priority="critical",
        )
        assert len(updated) == 2

        # Verify they are updated
        for issue in updated:
            assert issue.priority == Priority.CRITICAL

    def test_bulk_update_by_pattern_both(self, repo, sample_issues):
        """Test bulk updating both status and priority by pattern."""
        # Update all SonarQube issues to closed and high priority
        updated = repo.bulk_update_by_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            new_status="closed",
            new_priority="high",
        )
        assert len(updated) == 3

        # Verify both fields are updated
        for issue in updated:
            assert issue.status == Status.CLOSED
            assert issue.priority == Priority.HIGH

    def test_bulk_update_by_pattern_dry_run(self, repo, sample_issues):
        """Test bulk update dry-run mode."""
        # Get original state
        original_issues = repo.find_by_pattern(title_pattern="sonarqube*", use_regex=False)
        original_statuses = {issue.id: issue.status for issue in original_issues}

        # Dry run should return matches without changing anything
        matches = repo.bulk_update_by_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            new_status="closed",
            dry_run=True,
        )
        assert len(matches) == 3

        # Verify nothing was actually updated
        for issue in matches:
            retrieved = repo.get_issue(issue.id)
            assert retrieved is not None
            assert retrieved.status == original_statuses[issue.id]

    def test_bulk_update_by_pattern_no_updates(self, repo, sample_issues):
        """Test bulk update with no update fields specified."""
        # Should return empty list if no updates
        updated = repo.bulk_update_by_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
        )
        assert len(updated) == 0

    def test_bulk_delete_by_pattern_glob(self, repo, sample_issues):
        """Test bulk deleting issues by glob pattern."""
        # Get IDs before deletion
        to_delete = repo.find_by_pattern(title_pattern="sonarqube*", use_regex=False)
        deleted_ids = [issue.id for issue in to_delete]

        # Delete all SonarQube issues
        deleted = repo.bulk_delete_by_pattern(title_pattern="sonarqube*", use_regex=False)
        assert len(deleted) == 3

        # Verify they are deleted
        for issue_id in deleted_ids:
            retrieved = repo.get_issue(issue_id)
            assert retrieved is None

    def test_bulk_delete_by_pattern_regex(self, repo, sample_issues):
        """Test bulk deleting issues by regex pattern."""
        # Get IDs before deletion
        to_delete = repo.find_by_pattern(title_pattern="^Bug", use_regex=True)
        deleted_ids = [issue.id for issue in to_delete]

        # Delete all Bug issues
        deleted = repo.bulk_delete_by_pattern(title_pattern="^Bug", use_regex=True)
        assert len(deleted) == 2

        # Verify they are deleted
        for issue_id in deleted_ids:
            retrieved = repo.get_issue(issue_id)
            assert retrieved is None

    def test_bulk_delete_by_pattern_dry_run(self, repo, sample_issues):
        """Test bulk delete dry-run mode."""
        # Dry run should return matches without deleting anything
        matches = repo.bulk_delete_by_pattern(
            title_pattern="sonarqube*", use_regex=False, dry_run=True
        )
        assert len(matches) == 3

        # Verify nothing was actually deleted
        for issue in matches:
            retrieved = repo.get_issue(issue.id)
            assert retrieved is not None

    def test_bulk_delete_by_pattern_with_audit(self, repo, sample_issues):
        """Test that bulk delete creates audit logs."""
        # Get an issue to delete
        to_delete = repo.find_by_pattern(title_pattern="sonarqube issue 1", use_regex=False)
        assert len(to_delete) == 1
        issue_id = to_delete[0].id

        # Delete it
        deleted = repo.bulk_delete_by_pattern(title_pattern="sonarqube issue 1", use_regex=False)
        assert len(deleted) == 1

        # Check audit log
        logs = repo.get_audit_logs(issue_id=issue_id)
        delete_logs = [log for log in logs if log.action == "DELETE"]
        assert len(delete_logs) == 1

    def test_pattern_matching_special_chars(self, repo):
        """Test pattern matching with special characters."""
        # Create issues with special characters
        repo.create_issue(
            Issue(
                title="Issue #123",
                description="Test",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )
        repo.create_issue(
            Issue(
                title="Issue [ABC]",
                description="Test",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )
        repo.create_issue(
            Issue(
                title="Issue (XYZ)",
                description="Test",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )

        # Test glob pattern
        matches = repo.find_by_pattern(title_pattern="Issue #*", use_regex=False)
        assert len(matches) == 1
        assert matches[0].title == "Issue #123"

        # Test regex pattern (need to escape special chars)
        matches = repo.find_by_pattern(title_pattern=r"Issue \[ABC\]", use_regex=True)
        assert len(matches) == 1
        assert matches[0].title == "Issue [ABC]"

    def test_pattern_matching_empty_description(self, repo):
        """Test pattern matching with empty descriptions."""
        # Create issue with no description
        repo.create_issue(
            Issue(
                title="No description",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )

        # Should not match description pattern if description is None
        matches = repo.find_by_pattern(desc_pattern="*test*", use_regex=False)
        assert len(matches) == 0

        # Should match title pattern even without description
        matches = repo.find_by_pattern(title_pattern="No*", use_regex=False)
        assert len(matches) == 1
        assert matches[0].title == "No description"

    def test_case_insensitive_default(self, repo):
        """Test that case-insensitive matching is the default."""
        # Create mixed case issues
        repo.create_issue(
            Issue(
                title="UPPERCASE",
                description="Test",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )
        repo.create_issue(
            Issue(
                title="lowercase",
                description="Test",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )
        repo.create_issue(
            Issue(
                title="MixedCase",
                description="Test",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            )
        )

        # Should match all variations with case-insensitive search (default)
        matches = repo.find_by_pattern(title_pattern="*case", use_regex=False)
        assert len(matches) == 3

    def test_audit_log_bulk_operations(self, repo, sample_issues):
        """Test that bulk operations create proper audit logs."""
        # Close issues by pattern
        closed = repo.bulk_close_by_pattern(title_pattern="sonarqube*", use_regex=False)
        assert len(closed) == 3

        # Check audit logs for one of the closed issues
        issue_id = closed[0].id
        logs = repo.get_audit_logs(issue_id=issue_id)
        update_logs = [log for log in logs if log.action == "UPDATE"]

        # Should have UPDATE log for status change
        assert len(update_logs) >= 1
        status_updates = [log for log in update_logs if log.field_name == "status"]
        assert len(status_updates) == 1
        assert status_updates[0].new_value == "closed"


class TestBulkPatternCLI:
    """Test CLI commands for bulk pattern operations."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance with temporary database."""
        from issuedb.cli import CLI

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            cli_instance = CLI(f.name)
            yield cli_instance

    @pytest.fixture
    def sample_issues(self, cli):
        """Create sample issues for CLI testing."""
        # Create several SonarQube issues
        cli.create_issue("SonarQube issue 1", description="First issue", priority="high")
        cli.create_issue("SonarQube issue 2", description="Second issue", priority="medium")
        cli.create_issue("Different issue", description="Something else", priority="low")

    def test_cli_bulk_close_pattern_json(self, cli, sample_issues):
        """Test CLI bulk-close-pattern with JSON output."""
        import json

        result = cli.bulk_close_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            as_json=True,
        )

        data = json.loads(result)
        assert data["count"] == 2
        assert "Closed" in data["message"]

    def test_cli_bulk_close_pattern_dry_run(self, cli, sample_issues):
        """Test CLI bulk-close-pattern with dry-run."""
        import json

        result = cli.bulk_close_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            dry_run=True,
            as_json=True,
        )

        data = json.loads(result)
        assert data["count"] == 2
        assert "Would close" in data["message"]
        assert "dry-run" in data["message"]

    def test_cli_bulk_update_pattern_json(self, cli, sample_issues):
        """Test CLI bulk-update-pattern with JSON output."""
        import json

        result = cli.bulk_update_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            new_status="in-progress",
            as_json=True,
        )

        data = json.loads(result)
        assert data["count"] == 2
        assert "Updated" in data["message"]

    def test_cli_bulk_delete_pattern_requires_confirm(self, cli, sample_issues):
        """Test CLI bulk-delete-pattern requires confirmation."""
        with pytest.raises(ValueError, match="Must use --confirm flag"):
            cli.bulk_delete_pattern(
                title_pattern="sonarqube*",
                use_regex=False,
                confirm=False,
                as_json=True,
            )

    def test_cli_bulk_delete_pattern_with_confirm(self, cli, sample_issues):
        """Test CLI bulk-delete-pattern with confirmation."""
        import json

        result = cli.bulk_delete_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            confirm=True,
            as_json=True,
        )

        data = json.loads(result)
        assert data["count"] == 2
        assert "Deleted" in data["message"]

    def test_cli_bulk_delete_pattern_dry_run_no_confirm(self, cli, sample_issues):
        """Test CLI bulk-delete-pattern dry-run doesn't require confirmation."""
        import json

        # Dry-run should work without confirm
        result = cli.bulk_delete_pattern(
            title_pattern="sonarqube*",
            use_regex=False,
            dry_run=True,
            confirm=False,
            as_json=True,
        )

        data = json.loads(result)
        assert data["count"] == 2
        assert "Would delete" in data["message"]
