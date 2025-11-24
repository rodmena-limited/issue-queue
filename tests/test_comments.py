"""Tests for comment functionality."""

import json
import tempfile

import pytest

from issuedb.cli import CLI
from issuedb.models import Issue
from issuedb.repository import IssueRepository


class TestCommentRepository:
    """Test comment functionality in repository layer."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            repo = IssueRepository(f.name)
            yield repo

    @pytest.fixture
    def sample_issue(self, repo):
        """Create a sample issue."""
        issue = Issue(title="Test Issue", description="Test description")
        return repo.create_issue(issue)

    def test_add_comment(self, repo, sample_issue):
        """Test adding a comment to an issue."""
        comment = repo.add_comment(sample_issue.id, "This is a test comment")

        assert comment.id is not None
        assert comment.issue_id == sample_issue.id
        assert comment.text == "This is a test comment"
        assert comment.created_at is not None

    def test_add_comment_strips_whitespace(self, repo, sample_issue):
        """Test that comment text is stripped of whitespace."""
        comment = repo.add_comment(sample_issue.id, "  Test comment  ")
        assert comment.text == "Test comment"

    def test_add_comment_empty_text(self, repo, sample_issue):
        """Test that adding empty comment raises error."""
        with pytest.raises(ValueError, match="Comment text cannot be empty"):
            repo.add_comment(sample_issue.id, "")

        with pytest.raises(ValueError, match="Comment text cannot be empty"):
            repo.add_comment(sample_issue.id, "   ")

    def test_add_comment_nonexistent_issue(self, repo):
        """Test that adding comment to nonexistent issue raises error."""
        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.add_comment(999, "Test comment")

    def test_get_comments(self, repo, sample_issue):
        """Test getting all comments for an issue."""
        # Add multiple comments
        repo.add_comment(sample_issue.id, "First comment")
        repo.add_comment(sample_issue.id, "Second comment")
        repo.add_comment(sample_issue.id, "Third comment")

        comments = repo.get_comments(sample_issue.id)

        assert len(comments) == 3
        assert comments[0].text == "First comment"
        assert comments[1].text == "Second comment"
        assert comments[2].text == "Third comment"

    def test_get_comments_empty(self, repo, sample_issue):
        """Test getting comments when none exist."""
        comments = repo.get_comments(sample_issue.id)
        assert len(comments) == 0

    def test_get_comments_ordered_by_time(self, repo, sample_issue):
        """Test that comments are returned in chronological order."""
        c1 = repo.add_comment(sample_issue.id, "First")
        c2 = repo.add_comment(sample_issue.id, "Second")
        c3 = repo.add_comment(sample_issue.id, "Third")

        comments = repo.get_comments(sample_issue.id)

        assert comments[0].id == c1.id
        assert comments[1].id == c2.id
        assert comments[2].id == c3.id

    def test_delete_comment(self, repo, sample_issue):
        """Test deleting a comment."""
        comment = repo.add_comment(sample_issue.id, "Test comment")

        result = repo.delete_comment(comment.id)
        assert result is True

        # Verify comment is deleted
        comments = repo.get_comments(sample_issue.id)
        assert len(comments) == 0

    def test_delete_comment_nonexistent(self, repo):
        """Test deleting nonexistent comment returns False."""
        result = repo.delete_comment(999)
        assert result is False

    def test_comments_cascade_delete_with_issue(self, repo, sample_issue):
        """Test that comments are deleted when issue is deleted."""
        repo.add_comment(sample_issue.id, "Comment 1")
        repo.add_comment(sample_issue.id, "Comment 2")

        # Delete the issue
        repo.delete_issue(sample_issue.id)

        # Comments should be deleted (cascade)
        comments = repo.get_comments(sample_issue.id)
        assert len(comments) == 0

    def test_multiple_issues_comments(self, repo):
        """Test comments on multiple issues."""
        issue1 = repo.create_issue(Issue(title="Issue 1"))
        issue2 = repo.create_issue(Issue(title="Issue 2"))

        repo.add_comment(issue1.id, "Comment on issue 1")
        repo.add_comment(issue2.id, "Comment on issue 2")
        repo.add_comment(issue1.id, "Another comment on issue 1")

        comments1 = repo.get_comments(issue1.id)
        comments2 = repo.get_comments(issue2.id)

        assert len(comments1) == 2
        assert len(comments2) == 1
        assert comments1[0].text == "Comment on issue 1"
        assert comments2[0].text == "Comment on issue 2"


class TestCommentCLI:
    """Test comment functionality via CLI."""

    @pytest.fixture
    def cli(self):
        """Create CLI with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            cli = CLI(f.name)
            yield cli

    @pytest.fixture
    def sample_issue(self, cli):
        """Create a sample issue."""
        cli.create_issue("Test Issue", description="Test description")
        # Get the issue ID from JSON output
        all_issues = json.loads(cli.list_issues(as_json=True))
        return all_issues[0]

    def test_add_comment_cli(self, cli, sample_issue):
        """Test adding comment via CLI."""
        output = cli.add_comment(sample_issue["id"], "Test comment")
        assert f"Comment added to issue {sample_issue['id']}" in output

        # Verify comment was added
        comments_json = cli.list_comments(sample_issue["id"], as_json=True)
        comments = json.loads(comments_json)
        assert len(comments) == 1
        assert comments[0]["text"] == "Test comment"

    def test_add_comment_json_output(self, cli, sample_issue):
        """Test adding comment with JSON output."""
        output = cli.add_comment(sample_issue["id"], "Test comment", as_json=True)
        comment = json.loads(output)

        assert comment["issue_id"] == sample_issue["id"]
        assert comment["text"] == "Test comment"
        assert "created_at" in comment

    def test_list_comments_cli(self, cli, sample_issue):
        """Test listing comments via CLI."""
        cli.add_comment(sample_issue["id"], "First comment")
        cli.add_comment(sample_issue["id"], "Second comment")

        output = cli.list_comments(sample_issue["id"])

        assert "First comment" in output
        assert "Second comment" in output

    def test_list_comments_json(self, cli, sample_issue):
        """Test listing comments with JSON output."""
        cli.add_comment(sample_issue["id"], "First")
        cli.add_comment(sample_issue["id"], "Second")

        output = cli.list_comments(sample_issue["id"], as_json=True)
        comments = json.loads(output)

        assert len(comments) == 2
        assert comments[0]["text"] == "First"
        assert comments[1]["text"] == "Second"

    def test_list_comments_empty(self, cli, sample_issue):
        """Test listing comments when none exist."""
        output = cli.list_comments(sample_issue["id"])
        assert f"No comments found for issue {sample_issue['id']}" in output

    def test_delete_comment_cli(self, cli, sample_issue):
        """Test deleting comment via CLI."""
        # Add comment
        comment_json = cli.add_comment(sample_issue["id"], "Test comment", as_json=True)
        comment = json.loads(comment_json)

        # Delete comment
        output = cli.delete_comment(comment["id"])
        assert f"Comment {comment['id']} deleted successfully" in output

        # Verify deletion
        comments_json = cli.list_comments(sample_issue["id"], as_json=True)
        comments = json.loads(comments_json)
        assert len(comments) == 0

    def test_delete_comment_not_found(self, cli):
        """Test deleting nonexistent comment raises error."""
        with pytest.raises(ValueError, match="Comment 999 not found"):
            cli.delete_comment(999)

    def test_add_comment_empty_text(self, cli, sample_issue):
        """Test adding empty comment raises error."""
        with pytest.raises(ValueError, match="Comment text cannot be empty"):
            cli.add_comment(sample_issue["id"], "")

    def test_add_comment_nonexistent_issue(self, cli):
        """Test adding comment to nonexistent issue raises error."""
        with pytest.raises(ValueError, match="Issue 999 not found"):
            cli.add_comment(999, "Test comment")
