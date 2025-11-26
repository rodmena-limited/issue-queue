"""Tests for issue dependencies functionality."""

import tempfile

import pytest

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


class TestIssueDependencies:
    """Test issue dependency management."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            repo = IssueRepository(f.name)
            yield repo

    @pytest.fixture
    def sample_issues(self, repo):
        """Create sample issues for testing dependencies."""
        issue1 = repo.create_issue(
            Issue(title="Issue 1", priority=Priority.HIGH, status=Status.OPEN)
        )
        issue2 = repo.create_issue(
            Issue(title="Issue 2", priority=Priority.MEDIUM, status=Status.OPEN)
        )
        issue3 = repo.create_issue(
            Issue(title="Issue 3", priority=Priority.LOW, status=Status.OPEN)
        )
        return issue1, issue2, issue3

    def test_add_dependency(self, repo, sample_issues):
        """Test adding a dependency between issues."""
        issue1, issue2, _ = sample_issues

        # Add dependency: issue2 is blocked by issue1
        result = repo.add_dependency(issue2.id, issue1.id)
        assert result is True

        # Verify the dependency
        blockers = repo.get_blockers(issue2.id)
        assert len(blockers) == 1
        assert blockers[0].id == issue1.id

    def test_add_duplicate_dependency(self, repo, sample_issues):
        """Test that adding duplicate dependency returns False."""
        issue1, issue2, _ = sample_issues

        # Add dependency
        repo.add_dependency(issue2.id, issue1.id)

        # Try to add same dependency again
        result = repo.add_dependency(issue2.id, issue1.id)
        assert result is False

    def test_add_dependency_nonexistent_issue(self, repo, sample_issues):
        """Test that adding dependency with nonexistent issue raises error."""
        issue1, _, _ = sample_issues

        with pytest.raises(ValueError, match="not found"):
            repo.add_dependency(999, issue1.id)

        with pytest.raises(ValueError, match="not found"):
            repo.add_dependency(issue1.id, 999)

    def test_add_self_dependency(self, repo, sample_issues):
        """Test that issue cannot block itself."""
        issue1, _, _ = sample_issues

        with pytest.raises(ValueError, match="cannot block itself"):
            repo.add_dependency(issue1.id, issue1.id)

    def test_add_dependency_creates_cycle(self, repo, sample_issues):
        """Test that circular dependencies are prevented."""
        issue1, issue2, issue3 = sample_issues

        # Create a chain: issue3 blocked by issue2 blocked by issue1
        repo.add_dependency(issue2.id, issue1.id)
        repo.add_dependency(issue3.id, issue2.id)

        # Try to create a cycle: issue1 blocked by issue3
        with pytest.raises(ValueError, match="would create a cycle"):
            repo.add_dependency(issue1.id, issue3.id)

    def test_remove_dependency(self, repo, sample_issues):
        """Test removing a specific dependency."""
        issue1, issue2, _ = sample_issues

        # Add dependency
        repo.add_dependency(issue2.id, issue1.id)

        # Remove it
        count = repo.remove_dependency(issue2.id, issue1.id)
        assert count == 1

        # Verify it's gone
        blockers = repo.get_blockers(issue2.id)
        assert len(blockers) == 0

    def test_remove_all_dependencies(self, repo, sample_issues):
        """Test removing all dependencies from an issue."""
        issue1, issue2, issue3 = sample_issues

        # Add multiple blockers
        repo.add_dependency(issue3.id, issue1.id)
        repo.add_dependency(issue3.id, issue2.id)

        # Remove all
        count = repo.remove_dependency(issue3.id)
        assert count == 2

        # Verify they're gone
        blockers = repo.get_blockers(issue3.id)
        assert len(blockers) == 0

    def test_remove_nonexistent_dependency(self, repo, sample_issues):
        """Test removing a dependency that doesn't exist."""
        issue1, issue2, _ = sample_issues

        count = repo.remove_dependency(issue2.id, issue1.id)
        assert count == 0

    def test_get_blockers(self, repo, sample_issues):
        """Test getting all issues blocking a given issue."""
        issue1, issue2, issue3 = sample_issues

        # Add multiple blockers for issue3
        repo.add_dependency(issue3.id, issue1.id)
        repo.add_dependency(issue3.id, issue2.id)

        blockers = repo.get_blockers(issue3.id)
        assert len(blockers) == 2
        blocker_ids = {b.id for b in blockers}
        assert blocker_ids == {issue1.id, issue2.id}

    def test_get_blocking(self, repo, sample_issues):
        """Test getting all issues that a given issue is blocking."""
        issue1, issue2, issue3 = sample_issues

        # issue1 blocks both issue2 and issue3
        repo.add_dependency(issue2.id, issue1.id)
        repo.add_dependency(issue3.id, issue1.id)

        blocking = repo.get_blocking(issue1.id)
        assert len(blocking) == 2
        blocking_ids = {b.id for b in blocking}
        assert blocking_ids == {issue2.id, issue3.id}

    def test_is_blocked_with_open_blocker(self, repo, sample_issues):
        """Test that issue is blocked if it has open blocker."""
        issue1, issue2, _ = sample_issues

        repo.add_dependency(issue2.id, issue1.id)
        assert repo.is_blocked(issue2.id) is True

    def test_is_blocked_with_closed_blocker(self, repo, sample_issues):
        """Test that issue is not blocked if blocker is closed."""
        issue1, issue2, _ = sample_issues

        repo.add_dependency(issue2.id, issue1.id)

        # Close the blocker
        repo.update_issue(issue1.id, status="closed")

        assert repo.is_blocked(issue2.id) is False

    def test_is_blocked_no_blockers(self, repo, sample_issues):
        """Test that issue without blockers is not blocked."""
        _, issue2, _ = sample_issues

        assert repo.is_blocked(issue2.id) is False

    def test_get_all_blocked_issues(self, repo, sample_issues):
        """Test getting all issues that are currently blocked."""
        issue1, issue2, issue3 = sample_issues

        # Block issue2 and issue3
        repo.add_dependency(issue2.id, issue1.id)
        repo.add_dependency(issue3.id, issue1.id)

        blocked_issues = repo.get_all_blocked_issues()
        assert len(blocked_issues) == 2
        blocked_ids = {i.id for i in blocked_issues}
        assert blocked_ids == {issue2.id, issue3.id}

    def test_get_all_blocked_issues_excludes_closed_blockers(self, repo, sample_issues):
        """Test that issues with only closed blockers are not included."""
        issue1, issue2, issue3 = sample_issues

        # Block both issues
        repo.add_dependency(issue2.id, issue1.id)
        repo.add_dependency(issue3.id, issue1.id)

        # Close the blocker
        repo.update_issue(issue1.id, status="closed")

        blocked_issues = repo.get_all_blocked_issues()
        assert len(blocked_issues) == 0

    def test_get_all_blocked_issues_with_status_filter(self, repo, sample_issues):
        """Test filtering blocked issues by status."""
        issue1, issue2, issue3 = sample_issues

        # Block both issues
        repo.add_dependency(issue2.id, issue1.id)
        repo.add_dependency(issue3.id, issue1.id)

        # Update issue2 to in-progress
        repo.update_issue(issue2.id, status="in-progress")

        # Get only open blocked issues
        blocked_issues = repo.get_all_blocked_issues(status="open")
        assert len(blocked_issues) == 1
        assert blocked_issues[0].id == issue3.id

    def test_get_next_issue_skips_blocked(self, repo, sample_issues):
        """Test that get_next_issue skips blocked issues."""
        issue1, issue2, issue3 = sample_issues

        # Block issue2 (which has higher priority than issue3)
        repo.add_dependency(issue2.id, issue1.id)

        # get_next should return issue1 (highest priority, not blocked)
        next_issue = repo.get_next_issue(log_fetch=False)
        assert next_issue.id == issue1.id

        # Close issue1
        repo.update_issue(issue1.id, status="closed")

        # Now get_next should return issue2 (no longer blocked since blocker is closed)
        next_issue = repo.get_next_issue(log_fetch=False)
        assert next_issue.id == issue2.id

    def test_get_next_issue_unblocked_after_blocker_closed(self, repo, sample_issues):
        """Test that issue becomes available after blocker is closed."""
        issue1, issue2, _ = sample_issues

        # Block issue2
        repo.add_dependency(issue2.id, issue1.id)

        # Close issue1 to unblock issue2
        repo.update_issue(issue1.id, status="closed")

        # get_next should now return issue2
        next_issue = repo.get_next_issue(log_fetch=False)
        assert next_issue.id == issue2.id

    def test_cycle_detection_simple(self, repo, sample_issues):
        """Test cycle detection for simple 2-issue cycle."""
        issue1, issue2, _ = sample_issues

        # Add: issue2 blocked by issue1
        repo.add_dependency(issue2.id, issue1.id)

        # Try to add: issue1 blocked by issue2 (creates cycle)
        with pytest.raises(ValueError, match="would create a cycle"):
            repo.add_dependency(issue1.id, issue2.id)

    def test_cycle_detection_complex(self, repo, sample_issues):
        """Test cycle detection for complex multi-issue cycle."""
        issue1, issue2, issue3 = sample_issues
        issue4 = repo.create_issue(
            Issue(title="Issue 4", priority=Priority.LOW, status=Status.OPEN)
        )

        # Create chain: 4 -> 3 -> 2 -> 1
        repo.add_dependency(issue2.id, issue1.id)
        repo.add_dependency(issue3.id, issue2.id)
        repo.add_dependency(issue4.id, issue3.id)

        # Try to create cycle: 1 -> 4
        with pytest.raises(ValueError, match="would create a cycle"):
            repo.add_dependency(issue1.id, issue4.id)

    def test_dependencies_cascade_delete(self, repo, sample_issues):
        """Test that dependencies are deleted when issue is deleted."""
        issue1, issue2, _ = sample_issues

        # Add dependency
        repo.add_dependency(issue2.id, issue1.id)

        # Delete issue1
        repo.delete_issue(issue1.id)

        # Dependency should be gone
        blockers = repo.get_blockers(issue2.id)
        assert len(blockers) == 0

    def test_multiple_blockers_priority_order(self, repo, sample_issues):
        """Test that blockers are returned in priority order."""
        _, issue2, issue3 = sample_issues
        issue4 = repo.create_issue(
            Issue(title="Issue 4", priority=Priority.CRITICAL, status=Status.OPEN)
        )
        issue5 = repo.create_issue(
            Issue(title="Issue 5", priority=Priority.LOW, status=Status.OPEN)
        )

        # Add multiple blockers with different priorities
        repo.add_dependency(issue3.id, issue2.id)  # medium
        repo.add_dependency(issue3.id, issue4.id)  # critical
        repo.add_dependency(issue3.id, issue5.id)  # low

        blockers = repo.get_blockers(issue3.id)
        assert len(blockers) == 3
        # Should be ordered by priority: critical, medium, low
        assert blockers[0].priority == Priority.CRITICAL
        assert blockers[1].priority == Priority.MEDIUM
        assert blockers[2].priority == Priority.LOW
