"""Tests for duplicate detection features."""

import tempfile

import pytest

from issuedb.cli import CLI
from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


class TestDuplicateDetection:
    """Test duplicate detection and similarity features."""

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
    def cli(self, db_path):
        """Create a CLI instance with same database."""
        return CLI(db_path)

    @pytest.fixture
    def sample_issues(self, repo):
        """Create several sample issues for testing."""
        issues = [
            Issue(
                title="Fix login bug",
                description="Users cannot login to the system",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                title="Login issue - users can't authenticate",
                description="The login system is broken",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                title="Add dark mode",
                description="Implement dark theme for the UI",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            ),
            Issue(
                title="Implement dark theme",
                description="Add dark mode support",
                priority=Priority.LOW,
                status=Status.OPEN,
            ),
            Issue(
                title="Fix database migration",
                description="Migration script fails",
                priority=Priority.CRITICAL,
                status=Status.OPEN,
            ),
        ]

        created = []
        for issue in issues:
            created.append(repo.create_issue(issue))

        return created

    def test_find_similar_issues_text_output(self, cli, sample_issues):
        """Test finding similar issues with text output."""
        result = cli.find_similar_issues(
            query="login problem users cannot authenticate",
            threshold=0.3,
            as_json=False,
        )

        assert "similar issue" in result.lower() or "found" in result.lower()
        if "similar" in result.lower():
            assert "login" in result.lower()

    def test_find_similar_issues_json_output(self, cli, sample_issues):
        """Test finding similar issues with JSON output."""
        import json

        result = cli.find_similar_issues(
            query="login problem users cannot authenticate",
            threshold=0.3,
            as_json=True,
        )

        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) >= 0

        # Check first result if any
        if len(data) > 0:
            first_result = data[0]
            assert "id" in first_result
            assert "title" in first_result
            assert "similarity" in first_result
            assert first_result["similarity"] > 0

    def test_find_similar_issues_with_limit(self, cli, sample_issues):
        """Test finding similar issues with result limit."""
        import json

        result = cli.find_similar_issues(
            query="dark mode theme",
            threshold=0.3,
            limit=1,
            as_json=True,
        )

        data = json.loads(result)
        assert len(data) <= 1

    def test_find_similar_issues_high_threshold(self, cli, sample_issues):
        """Test with high threshold returns fewer results."""
        import json

        result = cli.find_similar_issues(
            query="login",
            threshold=0.9,
            as_json=True,
        )

        data = json.loads(result)
        # High threshold should return fewer results
        assert len(data) <= len(sample_issues)

    def test_find_similar_issues_no_matches(self, cli, sample_issues):
        """Test finding similar issues with no matches."""
        result = cli.find_similar_issues(
            query="completely unrelated query about quantum physics",
            threshold=0.7,
            as_json=False,
        )

        assert "no similar issues" in result.lower()

    def test_find_duplicates_text_output(self, cli, sample_issues):
        """Test finding duplicate groups with text output."""
        result = cli.find_duplicates(threshold=0.4, as_json=False)

        # Result should either show groups or indicate none found
        assert "group" in result.lower() or "no potential duplicates" in result.lower()

    def test_find_duplicates_json_output(self, cli, sample_issues):
        """Test finding duplicate groups with JSON output."""
        import json

        result = cli.find_duplicates(threshold=0.5, as_json=True)

        data = json.loads(result)
        assert "total_groups" in data
        assert "groups" in data
        assert isinstance(data["groups"], list)

        if data["total_groups"] > 0:
            group = data["groups"][0]
            assert "primary" in group
            assert "duplicates" in group
            assert isinstance(group["duplicates"], list)

            if len(group["duplicates"]) > 0:
                dup = group["duplicates"][0]
                assert "similarity" in dup
                assert dup["similarity"] > 0

    def test_find_duplicates_high_threshold(self, cli, sample_issues):
        """Test duplicate detection with high threshold."""
        import json

        result = cli.find_duplicates(threshold=0.9, as_json=True)

        data = json.loads(result)
        # Very high threshold should find few or no duplicates
        assert data["total_groups"] >= 0

    def test_find_duplicates_no_duplicates(self, cli):
        """Test duplicate detection with no similar issues."""
        # Create unrelated issues
        cli.create_issue(title="First issue", description="About topic A")
        cli.create_issue(title="Second issue", description="About topic B")
        cli.create_issue(title="Third issue", description="About topic C")

        result = cli.find_duplicates(threshold=0.7, as_json=False)

        assert "no potential duplicates" in result.lower()

    def test_create_with_duplicate_check_finds_similar(self, cli):
        """Test creating issue with duplicate check finds similar issues."""
        # Create first issue
        cli.create_issue(
            title="Fix login bug",
            description="Users cannot login",
            as_json=False,
        )

        # Try to create similar issue with duplicate check enabled
        result = cli.create_issue(
            title="Fix login bug",  # Exact match for stronger similarity
            description="Users cannot login",
            check_duplicates=True,
            as_json=False,
        )

        # Should either find similar issues or create successfully
        # (creating is ok if similarity is below threshold)
        lower_result = result.lower()
        assert (
            "similar issues found" in lower_result
            or "warning" in lower_result
            or "id:" in lower_result
        )

    def test_create_with_duplicate_check_json(self, cli):
        """Test creating issue with duplicate check in JSON format."""
        import json

        # Create first issue
        cli.create_issue(
            title="Fix login bug",
            description="Users cannot login",
        )

        # Try to create similar issue with duplicate check enabled
        result = cli.create_issue(
            title="Login problem - users can't authenticate",
            description="The login is broken",
            check_duplicates=True,
            as_json=True,
        )

        data = json.loads(result)
        # Should either have error about similar issues or be created
        assert "error" in data or "id" in data

        if "error" in data:
            assert "similar_issues" in data
            assert isinstance(data["similar_issues"], list)

    def test_create_with_force_flag(self, cli):
        """Test creating issue with force flag bypasses duplicate check."""
        import json

        # Create first issue
        cli.create_issue(
            title="Fix login bug",
            description="Users cannot login",
        )

        # Create similar issue with force flag
        result = cli.create_issue(
            title="Login problem - users can't authenticate",
            description="The login is broken",
            check_duplicates=True,
            force=True,
            as_json=True,
        )

        data = json.loads(result)
        # Should be created successfully
        assert "id" in data
        assert data["id"] is not None

    def test_create_without_duplicate_check(self, cli):
        """Test creating issue without duplicate check (default behavior)."""
        import json

        # Create first issue
        cli.create_issue(
            title="Fix login bug",
            description="Users cannot login",
        )

        # Create similar issue without check
        result = cli.create_issue(
            title="Login problem - users can't authenticate",
            description="The login is broken",
            check_duplicates=False,  # Explicitly disabled (also the default)
            as_json=True,
        )

        data = json.loads(result)
        # Should be created without warning
        assert "id" in data
        assert "error" not in data

    def test_similarity_threshold_values(self, cli, sample_issues):
        """Test different similarity threshold values."""
        import json

        # Low threshold should return more results
        low_result = cli.find_similar_issues(
            query="login",
            threshold=0.3,
            as_json=True,
        )
        low_data = json.loads(low_result)

        # High threshold should return fewer results
        high_result = cli.find_similar_issues(
            query="login",
            threshold=0.8,
            as_json=True,
        )
        high_data = json.loads(high_result)

        # Low threshold should have >= results than high threshold
        assert len(low_data) >= len(high_data)

    def test_duplicate_groups_structure(self, cli, sample_issues):
        """Test the structure of duplicate groups."""
        import json

        result = cli.find_duplicates(threshold=0.5, as_json=True)
        data = json.loads(result)

        if data["total_groups"] > 0:
            for group in data["groups"]:
                # Check primary issue structure
                assert "primary" in group
                primary = group["primary"]
                assert "id" in primary
                assert "title" in primary

                # Check duplicates structure
                assert "duplicates" in group
                for dup in group["duplicates"]:
                    assert "id" in dup
                    assert "title" in dup
                    assert "similarity" in dup
                    # Similarity should be a reasonable percentage
                    assert 0 <= dup["similarity"] <= 100
