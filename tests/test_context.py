"""Tests for agent context feature."""

import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from issuedb.cli import CLI
from issuedb.repository import IssueRepository


class TestAgentContext:
    """Test the context command for LLM agents."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            repo = IssueRepository(f.name)
            yield repo

    @pytest.fixture
    def cli(self):
        """Create a CLI instance with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cli_instance = CLI(f.name)
            yield cli_instance

    @pytest.fixture
    def issue_with_history(self, cli):
        """Create an issue with comments and update history."""
        # Create issue
        result = cli.create_issue(
            title="Test Issue",
            description="This is a test issue",
            priority="high",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        # Add comments
        cli.add_comment(issue_id, "First comment")
        cli.add_comment(issue_id, "Second comment with details")

        # Update issue status
        cli.update_issue(issue_id, status="in-progress")

        # Add more comments
        cli.add_comment(issue_id, "Working on this now")

        return issue_id

    def test_context_basic_structure_json(self, cli, issue_with_history):
        """Test basic context output structure in JSON format."""
        result = cli.get_issue_context(issue_with_history, as_json=True)

        data = json.loads(result)

        # Check required fields
        assert "issue" in data
        assert "comments" in data
        assert "comments_count" in data

        # Check issue structure
        assert data["issue"]["id"] == issue_with_history
        assert data["issue"]["title"] == "Test Issue"

        # Check comments
        assert isinstance(data["comments"], list)
        assert data["comments_count"] >= 3  # We added 3 comments

    def test_context_full_output_json(self, cli, issue_with_history):
        """Test full context output with all fields in JSON format."""
        result = cli.get_issue_context(
            issue_with_history,
            as_json=True,
            compact=False,
        )

        data = json.loads(result)

        # Full output should include additional fields
        assert "audit_history" in data
        assert "audit_history_count" in data
        assert "related_issues" in data
        assert "related_issues_count" in data
        assert "suggested_actions" in data

        # Check audit history
        assert isinstance(data["audit_history"], list)
        assert data["audit_history_count"] >= 0

        # Check suggested actions
        assert isinstance(data["suggested_actions"], list)

    def test_context_compact_mode_json(self, cli, issue_with_history):
        """Test compact context output in JSON format."""
        result = cli.get_issue_context(
            issue_with_history,
            as_json=True,
            compact=True,
        )

        data = json.loads(result)

        # Compact mode should only have issue and comments
        assert "issue" in data
        assert "comments" in data
        assert "comments_count" in data

        # Should not include extra fields
        assert "audit_history" not in data
        assert "related_issues" not in data
        assert "suggested_actions" not in data

    def test_context_text_output(self, cli, issue_with_history):
        """Test text format output for context."""
        result = cli.get_issue_context(
            issue_with_history,
            as_json=False,
            compact=False,
        )

        # Check for expected sections
        assert "ISSUE CONTEXT" in result
        assert "Test Issue" in result
        assert "## Comments" in result

        # Should include suggested actions in non-compact mode
        assert "## Suggested Actions" in result or "Suggested Actions" in result

    def test_context_text_output_compact(self, cli, issue_with_history):
        """Test compact text format output."""
        result = cli.get_issue_context(
            issue_with_history,
            as_json=False,
            compact=True,
        )

        # Should include basic info
        assert "Test Issue" in result
        assert "## Comments" in result

        # Should not include suggested actions in compact mode
        # (no "##" sections beyond basic info)
        assert "## Suggested Actions" not in result

    def test_context_comments_included(self, cli, issue_with_history):
        """Test that comments are included in context."""
        result = cli.get_issue_context(issue_with_history, as_json=True)

        data = json.loads(result)

        # Check comments are present
        assert len(data["comments"]) >= 3

        # Check comment structure
        for comment in data["comments"]:
            assert "id" in comment
            assert "text" in comment
            assert "created_at" in comment

        # Check specific comment texts
        comment_texts = [c["text"] for c in data["comments"]]
        assert "First comment" in comment_texts
        assert "Second comment with details" in comment_texts

    def test_context_no_comments(self, cli):
        """Test context for issue with no comments."""
        # Create issue without comments
        result = cli.create_issue(
            title="Issue without comments",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        # Get context
        context = cli.get_issue_context(issue_id, as_json=True)
        data = json.loads(context)

        assert data["comments_count"] == 0
        assert len(data["comments"]) == 0

    def test_context_suggested_actions_open_issue(self, cli):
        """Test suggested actions for open issue."""
        # Create open issue
        result = cli.create_issue(
            title="Open Issue",
            status="open",
            priority="high",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        # Get context
        context = cli.get_issue_context(issue_id, as_json=True, compact=False)
        data = json.loads(context)

        # Check suggested actions
        assert "suggested_actions" in data
        actions = data["suggested_actions"]
        assert isinstance(actions, list)

        # Should suggest starting work or mention priority
        action_text = " ".join(actions).lower()
        assert "open" in action_text or "in-progress" in action_text

    def test_context_suggested_actions_in_progress(self, cli):
        """Test suggested actions for in-progress issue."""
        # Create in-progress issue
        result = cli.create_issue(
            title="In Progress Issue",
            status="in-progress",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        # Get context
        context = cli.get_issue_context(issue_id, as_json=True, compact=False)
        data = json.loads(context)

        actions = data["suggested_actions"]
        action_text = " ".join(actions).lower()

        # Should suggest adding update or closing
        assert "in-progress" in action_text or "comment" in action_text or "close" in action_text

    def test_context_suggested_actions_closed_issue(self, cli):
        """Test suggested actions for closed issue."""
        # Create closed issue
        result = cli.create_issue(
            title="Closed Issue",
            status="closed",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        # Get context
        context = cli.get_issue_context(issue_id, as_json=True, compact=False)
        data = json.loads(context)

        actions = data["suggested_actions"]
        action_text = " ".join(actions).lower()

        # Should mention issue is closed
        assert "closed" in action_text or "reopen" in action_text

    def test_context_audit_history(self, cli, issue_with_history):
        """Test that audit history is included in full context."""
        result = cli.get_issue_context(
            issue_with_history,
            as_json=True,
            compact=False,
        )

        data = json.loads(result)

        # Check audit history exists
        assert "audit_history" in data
        assert isinstance(data["audit_history"], list)

        # Should have some audit entries (create, updates)
        assert len(data["audit_history"]) > 0

        # Check audit entry structure
        if len(data["audit_history"]) > 0:
            entry = data["audit_history"][0]
            assert "action" in entry
            assert "timestamp" in entry

    def test_context_related_issues(self, cli):
        """Test related issues in context."""
        # Create several related issues
        cli.create_issue(title="Login bug fix", description="Fix login issue")
        cli.create_issue(title="Login problem", description="Users can't login")
        result = cli.create_issue(
            title="Another login issue",
            description="Login fails",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        # Get context
        context = cli.get_issue_context(issue_id, as_json=True, compact=False)
        data = json.loads(context)

        # Should have related issues
        assert "related_issues" in data
        assert isinstance(data["related_issues"], list)

    def test_context_issue_not_found(self, cli):
        """Test context for non-existent issue."""
        with pytest.raises(ValueError, match="not found"):
            cli.get_issue_context(99999, as_json=True)

    def test_context_with_git_info_mocked(self, cli, issue_with_history):
        """Test context includes git info when available."""
        # Mock subprocess to simulate git repository
        mock_git_result = MagicMock()
        mock_git_result.returncode = 0
        mock_git_result.stdout = "true"

        mock_branch_result = MagicMock()
        mock_branch_result.returncode = 0
        mock_branch_result.stdout = "main"

        # Mock for git log calls (3 patterns searched)
        mock_log_result = MagicMock()
        mock_log_result.returncode = 0
        mock_log_result.stdout = ""

        with patch("subprocess.run") as mock_run:
            # First call checks if git repo
            # Second call gets current branch
            # Next 3 calls are for git log with different patterns
            mock_run.side_effect = [
                mock_git_result,
                mock_branch_result,
                mock_log_result,
                mock_log_result,
                mock_log_result,
            ]

            result = cli.get_issue_context(
                issue_with_history,
                as_json=True,
                compact=False,
            )

            data = json.loads(result)

            # Git info might be included
            if "git_info" in data:
                assert isinstance(data["git_info"], dict)

    def test_context_json_serializable(self, cli, issue_with_history):
        """Test that all context data is JSON serializable."""
        result = cli.get_issue_context(
            issue_with_history,
            as_json=True,
            compact=False,
        )

        # Should be valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)

        # Should be able to re-serialize
        re_serialized = json.dumps(data)
        assert isinstance(re_serialized, str)

    def test_context_output_format_consistency(self, cli, issue_with_history):
        """Test that JSON and text outputs are consistent."""
        json_result = cli.get_issue_context(
            issue_with_history,
            as_json=True,
            compact=False,
        )
        text_result = cli.get_issue_context(
            issue_with_history,
            as_json=False,
            compact=False,
        )

        data = json.loads(json_result)

        # Key information should be in both formats
        assert str(data["issue"]["id"]) in text_result
        assert data["issue"]["title"] in text_result

        # Comments should be in text output
        for comment in data["comments"]:
            assert comment["text"] in text_result

    def test_context_high_priority_suggestions(self, cli):
        """Test suggestions for high priority issues."""
        result = cli.create_issue(
            title="Critical Bug",
            priority="critical",
            status="open",
            as_json=True,
        )
        issue_data = json.loads(result)
        issue_id = issue_data["id"]

        context = cli.get_issue_context(issue_id, as_json=True, compact=False)
        data = json.loads(context)

        actions = data["suggested_actions"]
        action_text = " ".join(actions).lower()

        # Should mention high priority
        assert "priority" in action_text or "critical" in action_text or "high" in action_text
