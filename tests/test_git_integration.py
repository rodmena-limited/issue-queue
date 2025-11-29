"""Tests for git integration features."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from issuedb.git_repository import GitLinkRepository
from issuedb.git_utils import (
    get_commit_message,
    get_current_branch,
    get_recent_commits,
    is_git_repo,
    parse_close_refs,
    parse_issue_refs,
    validate_commit_hash,
)
from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


class TestGitUtils:
    """Test git utility functions."""

    def test_parse_issue_refs_single_hash(self):
        """Test parsing single #123 reference."""
        message = "Fix bug in login system #123"
        refs = parse_issue_refs(message)

        assert 123 in refs

    def test_parse_issue_refs_multiple_hashes(self):
        """Test parsing multiple issue references."""
        message = "Fix #123 and #456 related to #789"
        refs = parse_issue_refs(message)

        assert 123 in refs
        assert 456 in refs
        assert 789 in refs

    def test_parse_issue_refs_with_keywords(self):
        """Test parsing with fix/close/resolve keywords."""
        test_cases = [
            ("Fixes #123", 123),
            ("fixes #456", 456),
            ("Closes #789", 789),
            ("closes #111", 111),
            ("Resolves #222", 222),
            ("resolves #333", 333),
            ("Fix #444", 444),
            ("Close #555", 555),
            ("Resolve #666", 666),
        ]

        for message, expected_id in test_cases:
            refs = parse_issue_refs(message)
            assert expected_id in refs, f"Failed to parse: {message}"

    def test_parse_issue_refs_mixed_format(self):
        """Test parsing mixed reference formats."""
        message = "Fixes #123, also addresses #456 and relates to #789"
        refs = parse_issue_refs(message)

        assert len(refs) == 3
        assert 123 in refs
        assert 456 in refs
        assert 789 in refs

    def test_parse_issue_refs_no_refs(self):
        """Test parsing message with no issue references."""
        message = "This is a regular commit message without any issue refs"
        refs = parse_issue_refs(message)

        assert len(refs) == 0

    def test_parse_close_refs_only_closing_keywords(self):
        """Test that parse_close_refs only matches closing keywords."""
        # Should match
        close_message = "Fixes #123"
        close_refs = parse_close_refs(close_message)
        assert 123 in close_refs

        # Should NOT match plain #123
        plain_message = "Related to #456"
        plain_refs = parse_close_refs(plain_message)
        assert 456 not in plain_refs

    def test_parse_close_refs_all_keywords(self):
        """Test all closing keyword variations."""
        test_cases = [
            ("fixes #123", True),
            ("closes #123", True),
            ("resolves #123", True),
            ("fix #123", True),
            ("close #123", True),
            ("resolve #123", True),
            ("#123", False),  # Without keyword
            ("see #123", False),  # Non-closing keyword
        ]

        for message, should_match in test_cases:
            refs = parse_close_refs(message)
            if should_match:
                assert 123 in refs, f"Should match: {message}"
            else:
                assert 123 not in refs, f"Should not match: {message}"

    def test_parse_issue_refs_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        test_cases = [
            "FIXES #123",
            "Fixes #123",
            "fixes #123",
            "FiXeS #123",
        ]

        for message in test_cases:
            refs = parse_issue_refs(message)
            assert 123 in refs, f"Failed for: {message}"

    @patch("subprocess.run")
    def test_is_git_repo_true(self, mock_run):
        """Test is_git_repo when in a git repository."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "true"
        mock_run.return_value = mock_result

        assert is_git_repo() is True

    @patch("subprocess.run")
    def test_is_git_repo_false(self, mock_run):
        """Test is_git_repo when not in a git repository."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        assert is_git_repo() is False

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run):
        """Test getting current git branch."""
        # Mock is_git_repo check
        mock_git_check = MagicMock()
        mock_git_check.returncode = 0
        mock_git_check.stdout = "true"

        # Mock branch name retrieval
        mock_branch = MagicMock()
        mock_branch.returncode = 0
        mock_branch.stdout = "main\n"

        mock_run.side_effect = [mock_git_check, mock_branch]

        branch = get_current_branch()
        assert branch == "main"

    @patch("subprocess.run")
    def test_get_current_branch_not_git_repo(self, mock_run):
        """Test get_current_branch when not in git repo."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        branch = get_current_branch()
        assert branch is None

    @patch("subprocess.run")
    def test_get_recent_commits(self, mock_run):
        """Test getting recent commits."""
        # Mock is_git_repo check
        mock_git_check = MagicMock()
        mock_git_check.returncode = 0
        mock_git_check.stdout = "true"

        # Mock git log output
        mock_log = MagicMock()
        mock_log.returncode = 0
        mock_log.stdout = (
            "abc123|John Doe|2024-01-01 12:00:00|Fix login bug #123\n"
            "def456|Jane Smith|2024-01-02 13:00:00|Add feature closes #456\n"
        )

        mock_run.side_effect = [mock_git_check, mock_log]

        commits = get_recent_commits(n=2)

        assert len(commits) == 2
        assert commits[0]["hash"] == "abc123"
        assert commits[0]["author"] == "John Doe"
        assert commits[0]["message"] == "Fix login bug #123"
        assert commits[1]["hash"] == "def456"

    @patch("subprocess.run")
    def test_get_commit_message(self, mock_run):
        """Test getting commit message."""
        # Mock is_git_repo check
        mock_git_check = MagicMock()
        mock_git_check.returncode = 0
        mock_git_check.stdout = "true"

        # Mock git log for specific commit
        mock_log = MagicMock()
        mock_log.returncode = 0
        mock_log.stdout = "Fix login bug\n\nDetailed description here."

        mock_run.side_effect = [mock_git_check, mock_log]

        message = get_commit_message("abc123")
        assert "Fix login bug" in message

    @patch("subprocess.run")
    def test_validate_commit_hash_valid(self, mock_run):
        """Test validating a valid commit hash."""
        # Mock is_git_repo check
        mock_git_check = MagicMock()
        mock_git_check.returncode = 0
        mock_git_check.stdout = "true"

        # Mock git cat-file
        mock_cat_file = MagicMock()
        mock_cat_file.returncode = 0
        mock_cat_file.stdout = "commit"

        mock_run.side_effect = [mock_git_check, mock_cat_file]

        assert validate_commit_hash("abc123") is True

    @patch("subprocess.run")
    def test_validate_commit_hash_invalid(self, mock_run):
        """Test validating an invalid commit hash."""
        # Mock is_git_repo check
        mock_git_check = MagicMock()
        mock_git_check.returncode = 0
        mock_git_check.stdout = "true"

        # Mock git cat-file failure
        mock_cat_file = MagicMock()
        mock_cat_file.returncode = 1

        mock_run.side_effect = [mock_git_check, mock_cat_file]

        assert validate_commit_hash("invalid") is False


class TestGitLinkRepository:
    """Test git link repository operations."""

    @pytest.fixture
    def db_path(self):
        """Create a shared temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name

    @pytest.fixture
    def repo(self, db_path):
        """Create a repository with temporary database."""
        return IssueRepository(db_path)

    @pytest.fixture
    def git_repo(self, db_path):
        """Create a git link repository with same database."""
        return GitLinkRepository(db_path)

    @pytest.fixture
    def sample_issue(self, repo):
        """Create a sample issue."""
        issue = Issue(
            title="Test Issue",
            description="Test description",
            priority=Priority.MEDIUM,
            status=Status.OPEN,
        )
        return repo.create_issue(issue)

    def test_add_commit_link(self, git_repo, sample_issue):
        """Test adding a commit link to an issue."""
        link = git_repo.add_link(
            sample_issue.id,
            "commit",
            "abc123def456",
        )

        assert link is not None
        assert link.id is not None
        assert link.issue_id == sample_issue.id
        assert link.link_type == "commit"
        assert link.reference == "abc123def456"

    def test_add_branch_link(self, git_repo, sample_issue):
        """Test adding a branch link to an issue."""
        link = git_repo.add_link(
            sample_issue.id,
            "branch",
            "feature/login-fix",
        )

        assert link is not None
        assert link.link_type == "branch"
        assert link.reference == "feature/login-fix"

    def test_add_link_invalid_type(self, git_repo, sample_issue):
        """Test adding link with invalid type."""
        with pytest.raises(ValueError, match="Invalid link_type"):
            git_repo.add_link(sample_issue.id, "invalid_type", "some_ref")

    def test_add_link_issue_not_found(self, git_repo):
        """Test adding link to non-existent issue."""
        link = git_repo.add_link(99999, "commit", "abc123")
        assert link is None

    def test_add_duplicate_link(self, git_repo, sample_issue):
        """Test adding duplicate link raises error."""
        git_repo.add_link(sample_issue.id, "commit", "abc123")

        with pytest.raises(ValueError, match="Link already exists"):
            git_repo.add_link(sample_issue.id, "commit", "abc123")

    def test_get_links(self, git_repo, sample_issue):
        """Test getting all links for an issue."""
        # Add multiple links
        git_repo.add_link(sample_issue.id, "commit", "abc123")
        git_repo.add_link(sample_issue.id, "commit", "def456")
        git_repo.add_link(sample_issue.id, "branch", "main")

        links = git_repo.get_links(sample_issue.id)

        assert len(links) == 3
        link_types = [link.link_type for link in links]
        assert "commit" in link_types
        assert "branch" in link_types

    def test_get_links_empty(self, git_repo, sample_issue):
        """Test getting links when there are none."""
        links = git_repo.get_links(sample_issue.id)
        assert len(links) == 0

    def test_remove_link_by_commit(self, git_repo, sample_issue):
        """Test removing link by commit hash."""
        git_repo.add_link(sample_issue.id, "commit", "abc123")

        count = git_repo.remove_link(
            sample_issue.id,
            link_type="commit",
            reference="abc123",
        )

        assert count == 1

        # Verify link is removed
        links = git_repo.get_links(sample_issue.id)
        assert len(links) == 0

    def test_remove_link_by_type(self, git_repo, sample_issue):
        """Test removing all links of a specific type."""
        git_repo.add_link(sample_issue.id, "commit", "abc123")
        git_repo.add_link(sample_issue.id, "commit", "def456")
        git_repo.add_link(sample_issue.id, "branch", "main")

        count = git_repo.remove_link(sample_issue.id, link_type="commit")

        assert count == 2

        # Verify only branch link remains
        links = git_repo.get_links(sample_issue.id)
        assert len(links) == 1
        assert links[0].link_type == "branch"

    def test_remove_link_requires_filter(self, git_repo, sample_issue):
        """Test that remove_link requires at least one filter."""
        with pytest.raises(ValueError, match="Must specify at least one"):
            git_repo.remove_link(sample_issue.id)

    def test_get_issues_by_commit(self, git_repo, repo):
        """Test finding issues linked to a commit."""
        # Create multiple issues
        issue1 = repo.create_issue(
            Issue(title="Issue 1", priority=Priority.HIGH, status=Status.OPEN)
        )
        issue2 = repo.create_issue(
            Issue(title="Issue 2", priority=Priority.MEDIUM, status=Status.OPEN)
        )

        # Link both to same commit
        git_repo.add_link(issue1.id, "commit", "abc123")
        git_repo.add_link(issue2.id, "commit", "abc123")

        # Find issues
        issues = git_repo.get_issues_by_link(link_type="commit", reference="abc123")

        assert len(issues) == 2
        issue_ids = [issue.id for issue in issues]
        assert issue1.id in issue_ids
        assert issue2.id in issue_ids

    def test_get_issues_by_branch(self, git_repo, repo):
        """Test finding issues linked to a branch."""
        issue = repo.create_issue(Issue(title="Issue", priority=Priority.HIGH, status=Status.OPEN))
        git_repo.add_link(issue.id, "branch", "feature/test")

        issues = git_repo.get_issues_by_link(link_type="branch", reference="feature/test")

        assert len(issues) == 1
        assert issues[0].id == issue.id

    def test_scan_commits_and_create_links(self, git_repo, repo):
        """Test scanning commits and creating links."""
        # Create issues
        issue1 = repo.create_issue(
            Issue(title="Issue 1", priority=Priority.HIGH, status=Status.OPEN)
        )
        issue2 = repo.create_issue(
            Issue(title="Issue 2", priority=Priority.MEDIUM, status=Status.OPEN)
        )

        # Mock commits
        commits = [
            {
                "hash": "abc123",
                "message": "Fix bug #1",
                "author": "Test User",
                "date": "2024-01-01",
            },
            {
                "hash": "def456",
                "message": "Add feature relates to #2",
                "author": "Test User",
                "date": "2024-01-02",
            },
        ]

        result = git_repo.scan_commits_and_close_issues(commits, auto_close=False)

        assert result["scanned"] == 2
        assert result["links_created"] == 2
        assert result["issues_closed"] == 0

        # Verify links were created
        links1 = git_repo.get_links(issue1.id)
        assert len(links1) == 1
        assert links1[0].reference == "abc123"

        links2 = git_repo.get_links(issue2.id)
        assert len(links2) == 1
        assert links2[0].reference == "def456"

    def test_scan_commits_auto_close(self, git_repo, repo):
        """Test scanning commits with auto-close."""
        # Create issue
        issue = repo.create_issue(Issue(title="Issue", priority=Priority.HIGH, status=Status.OPEN))

        # Mock commit with closing keyword
        commits = [
            {
                "hash": "abc123",
                "message": f"Fixes #{issue.id}",
                "author": "Test User",
                "date": "2024-01-01",
            },
        ]

        result = git_repo.scan_commits_and_close_issues(commits, auto_close=True)

        assert result["scanned"] == 1
        assert result["links_created"] == 1
        assert result["issues_closed"] == 1

        # Verify issue was closed
        updated_issue = repo.get_issue(issue.id)
        assert updated_issue.status == Status.CLOSED

    def test_scan_commits_no_auto_close(self, git_repo, repo):
        """Test scanning commits without auto-close."""
        issue = repo.create_issue(Issue(title="Issue", priority=Priority.HIGH, status=Status.OPEN))

        commits = [
            {
                "hash": "abc123",
                "message": f"Fixes #{issue.id}",
                "author": "Test User",
                "date": "2024-01-01",
            },
        ]

        result = git_repo.scan_commits_and_close_issues(commits, auto_close=False)

        assert result["scanned"] == 1
        assert result["links_created"] == 1
        assert result["issues_closed"] == 0

        # Verify issue was NOT closed
        updated_issue = repo.get_issue(issue.id)
        assert updated_issue.status == Status.OPEN

    def test_scan_commits_issue_not_found(self, git_repo):
        """Test scanning commits with non-existent issue reference."""
        commits = [
            {
                "hash": "abc123",
                "message": "Fix #99999",
                "author": "Test User",
                "date": "2024-01-01",
            },
        ]

        result = git_repo.scan_commits_and_close_issues(commits)

        assert result["scanned"] == 1
        assert result["links_created"] == 0

        # Check details for skip reason
        assert len(result["details"]) > 0
        assert result["details"][0]["action"] == "skipped"
        assert "not found" in result["details"][0]["reason"]

    def test_scan_commits_duplicate_link(self, git_repo, repo):
        """Test scanning same commit twice doesn't create duplicate links."""
        issue = repo.create_issue(Issue(title="Issue", priority=Priority.HIGH, status=Status.OPEN))

        commits = [
            {
                "hash": "abc123",
                "message": f"Fix #{issue.id}",
                "author": "Test User",
                "date": "2024-01-01",
            },
        ]

        # Scan first time
        result1 = git_repo.scan_commits_and_close_issues(commits)
        assert result1["links_created"] == 1

        # Scan second time
        result2 = git_repo.scan_commits_and_close_issues(commits)
        assert result2["links_created"] == 0

        # Check details indicate link exists
        assert result2["details"][0]["action"] == "skipped"
        assert "already exists" in result2["details"][0]["reason"]
