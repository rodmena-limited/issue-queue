"""Tests for code reference functionality."""

import os
import tempfile

import pytest

from issuedb.cli import CLI
from issuedb.models import CodeReference, Issue, Priority, Status
from issuedb.repository import IssueRepository


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def repo(temp_db):
    """Create a repository instance with temporary database."""
    return IssueRepository(temp_db)


@pytest.fixture
def cli(temp_db):
    """Create a CLI instance with temporary database."""
    return CLI(temp_db)


@pytest.fixture
def sample_issue(repo):
    """Create a sample issue for testing."""
    issue = Issue(
        title="Test Issue",
        description="Test description",
        priority=Priority.HIGH,
        status=Status.OPEN,
    )
    return repo.create_issue(issue)


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def test():\n    pass\n")
        file_path = f.name
    yield file_path
    if os.path.exists(file_path):
        os.unlink(file_path)


class TestFileSpecParsing:
    """Test file specification parsing."""

    def test_parse_file_only(self, repo):
        """Test parsing file path without line numbers."""
        file_path, start_line, end_line = repo.parse_file_spec("src/main.py")
        assert file_path == "src/main.py"
        assert start_line is None
        assert end_line is None

    def test_parse_file_with_single_line(self, repo):
        """Test parsing file path with single line number."""
        file_path, start_line, end_line = repo.parse_file_spec("src/main.py:45")
        assert file_path == "src/main.py"
        assert start_line == 45
        assert end_line is None

    def test_parse_file_with_line_range(self, repo):
        """Test parsing file path with line range."""
        file_path, start_line, end_line = repo.parse_file_spec("src/main.py:45-60")
        assert file_path == "src/main.py"
        assert start_line == 45
        assert end_line == 60

    def test_parse_file_with_path_containing_colon(self, repo):
        """Test parsing Windows-style paths with colon."""
        # Should use rsplit to handle this properly
        file_path, start_line, end_line = repo.parse_file_spec("C:/path/to/file.py:45")
        assert file_path == "C:/path/to/file.py"
        assert start_line == 45
        assert end_line is None

    def test_parse_invalid_line_number(self, repo):
        """Test parsing with invalid line number."""
        with pytest.raises(ValueError, match="Invalid line number"):
            repo.parse_file_spec("src/main.py:abc")

    def test_parse_invalid_line_range(self, repo):
        """Test parsing with invalid line range."""
        with pytest.raises(ValueError, match="Invalid line range format"):
            repo.parse_file_spec("src/main.py:abc-def")

    def test_parse_reversed_line_range(self, repo):
        """Test parsing with reversed line range."""
        with pytest.raises(ValueError, match="start line must be <= end line"):
            repo.parse_file_spec("src/main.py:60-45")


class TestAddCodeReference:
    """Test adding code references."""

    def test_add_reference_with_file_only(self, repo, sample_issue, temp_file):
        """Test adding reference with just file path."""
        ref = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
        )
        assert ref.id is not None
        assert ref.issue_id == sample_issue.id
        assert ref.file_path == os.path.relpath(temp_file)
        assert ref.start_line is None
        assert ref.end_line is None
        assert ref.note is None

    def test_add_reference_with_line_number(self, repo, sample_issue, temp_file):
        """Test adding reference with line number."""
        ref = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
        )
        assert ref.start_line == 10
        assert ref.end_line is None

    def test_add_reference_with_line_range(self, repo, sample_issue, temp_file):
        """Test adding reference with line range."""
        ref = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
            end_line=20,
        )
        assert ref.start_line == 10
        assert ref.end_line == 20

    def test_add_reference_with_note(self, repo, sample_issue, temp_file):
        """Test adding reference with note."""
        ref = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            note="This is the main bug location",
        )
        assert ref.note == "This is the main bug location"

    def test_add_reference_nonexistent_issue(self, repo, temp_file):
        """Test adding reference to non-existent issue."""
        with pytest.raises(ValueError, match="Issue 999 not found"):
            repo.add_code_reference(
                issue_id=999,
                file_path=temp_file,
            )

    def test_add_reference_nonexistent_file(self, repo, sample_issue):
        """Test adding reference to non-existent file."""
        with pytest.raises(ValueError, match="File not found"):
            repo.add_code_reference(
                issue_id=sample_issue.id,
                file_path="nonexistent.py",
            )

    def test_add_reference_nonexistent_file_no_validation(self, repo, sample_issue):
        """Test adding reference to non-existent file without validation."""
        ref = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path="nonexistent.py",
            validate_file=False,
        )
        assert ref.file_path == "nonexistent.py"

    def test_add_reference_invalid_line_numbers(self, repo, sample_issue, temp_file):
        """Test adding reference with invalid line numbers."""
        with pytest.raises(ValueError, match="Line numbers must be >= 1"):
            repo.add_code_reference(
                issue_id=sample_issue.id,
                file_path=temp_file,
                start_line=0,
            )

        with pytest.raises(ValueError, match="Line numbers must be >= 1"):
            repo.add_code_reference(
                issue_id=sample_issue.id,
                file_path=temp_file,
                start_line=10,
                end_line=-5,
            )

    def test_add_reference_reversed_range(self, repo, sample_issue, temp_file):
        """Test adding reference with reversed line range."""
        with pytest.raises(ValueError, match="start_line must be <= end_line"):
            repo.add_code_reference(
                issue_id=sample_issue.id,
                file_path=temp_file,
                start_line=20,
                end_line=10,
            )

    def test_add_multiple_references(self, repo, sample_issue, temp_file):
        """Test adding multiple references to same issue."""
        ref1 = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
        )
        ref2 = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=50,
        )
        assert ref1.id != ref2.id
        refs = repo.get_code_references(sample_issue.id)
        assert len(refs) == 2


class TestGetCodeReferences:
    """Test getting code references."""

    def test_get_references_empty(self, repo, sample_issue):
        """Test getting references when none exist."""
        refs = repo.get_code_references(sample_issue.id)
        assert refs == []

    def test_get_references(self, repo, sample_issue, temp_file):
        """Test getting references for an issue."""
        repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
            note="First reference",
        )
        repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=50,
            note="Second reference",
        )

        refs = repo.get_code_references(sample_issue.id)
        assert len(refs) == 2
        assert all(isinstance(ref, CodeReference) for ref in refs)
        assert refs[0].note == "First reference"
        assert refs[1].note == "Second reference"


class TestRemoveCodeReference:
    """Test removing code references."""

    def test_remove_by_file_path(self, repo, sample_issue, temp_file):
        """Test removing references by file path."""
        repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
        )
        repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=50,
        )

        count = repo.remove_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
        )
        assert count == 2

        refs = repo.get_code_references(sample_issue.id)
        assert len(refs) == 0

    def test_remove_by_reference_id(self, repo, sample_issue, temp_file):
        """Test removing specific reference by ID."""
        ref1 = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
        )
        ref2 = repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=50,
        )

        count = repo.remove_code_reference(
            issue_id=sample_issue.id,
            reference_id=ref1.id,
        )
        assert count == 1

        refs = repo.get_code_references(sample_issue.id)
        assert len(refs) == 1
        assert refs[0].id == ref2.id

    def test_remove_no_parameters(self, repo, sample_issue):
        """Test removing without file_path or reference_id."""
        with pytest.raises(ValueError, match="Must provide either file_path or reference_id"):
            repo.remove_code_reference(issue_id=sample_issue.id)

    def test_remove_nonexistent_reference(self, repo, sample_issue):
        """Test removing non-existent reference."""
        count = repo.remove_code_reference(
            issue_id=sample_issue.id,
            file_path="nonexistent.py",
        )
        assert count == 0


class TestGetIssuesByFile:
    """Test getting issues by file."""

    def test_get_issues_no_references(self, repo):
        """Test getting issues when file has no references."""
        issues = repo.get_issues_by_file("src/main.py")
        assert issues == []

    def test_get_issues_by_file(self, repo, temp_file):
        """Test getting issues that reference a file."""
        issue1 = repo.create_issue(
            Issue(title="Issue 1", priority=Priority.HIGH, status=Status.OPEN)
        )
        issue2 = repo.create_issue(
            Issue(title="Issue 2", priority=Priority.MEDIUM, status=Status.OPEN)
        )
        issue3 = repo.create_issue(
            Issue(title="Issue 3", priority=Priority.LOW, status=Status.CLOSED)
        )

        # Add references to same file from different issues
        repo.add_code_reference(issue_id=issue1.id, file_path=temp_file)
        repo.add_code_reference(issue_id=issue2.id, file_path=temp_file)

        issues = repo.get_issues_by_file(temp_file)
        assert len(issues) == 2
        issue_ids = {issue.id for issue in issues}
        assert issue1.id in issue_ids
        assert issue2.id in issue_ids
        assert issue3.id not in issue_ids

    def test_get_issues_by_file_relative_path(self, repo, temp_file):
        """Test getting issues using relative path."""
        issue = repo.create_issue(Issue(title="Issue", priority=Priority.HIGH, status=Status.OPEN))
        repo.add_code_reference(issue_id=issue.id, file_path=temp_file)

        # Query with relative path
        rel_path = os.path.relpath(temp_file)
        issues = repo.get_issues_by_file(rel_path)
        assert len(issues) == 1
        assert issues[0].id == issue.id


class TestCLIAttach:
    """Test CLI attach command."""

    def test_attach_file_only(self, cli, sample_issue, temp_file):
        """Test attaching file without line numbers."""
        result = cli.attach_code_reference(
            issue_id=sample_issue.id,
            file_spec=temp_file,
        )
        assert "Code reference added" in result
        assert temp_file in result or os.path.relpath(temp_file) in result

    def test_attach_file_with_line(self, cli, sample_issue, temp_file):
        """Test attaching file with line number."""
        result = cli.attach_code_reference(
            issue_id=sample_issue.id,
            file_spec=f"{temp_file}:10",
        )
        assert "Code reference added" in result
        assert "Line: 10" in result

    def test_attach_file_with_range(self, cli, sample_issue, temp_file):
        """Test attaching file with line range."""
        result = cli.attach_code_reference(
            issue_id=sample_issue.id,
            file_spec=f"{temp_file}:10-20",
        )
        assert "Code reference added" in result
        assert "Lines: 10-20" in result

    def test_attach_with_note(self, cli, sample_issue, temp_file):
        """Test attaching with note."""
        result = cli.attach_code_reference(
            issue_id=sample_issue.id,
            file_spec=temp_file,
            note="Main bug location",
        )
        assert "Note: Main bug location" in result

    def test_attach_json_output(self, cli, sample_issue, temp_file):
        """Test attach with JSON output."""
        import json

        result = cli.attach_code_reference(
            issue_id=sample_issue.id,
            file_spec=temp_file,
            as_json=True,
        )
        data = json.loads(result)
        assert data["issue_id"] == sample_issue.id
        assert "file_path" in data


class TestCLIDetach:
    """Test CLI detach command."""

    def test_detach(self, cli, repo, sample_issue, temp_file):
        """Test detaching code reference."""
        repo.add_code_reference(issue_id=sample_issue.id, file_path=temp_file)

        result = cli.detach_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
        )
        assert "Removed 1 code reference" in result

    def test_detach_no_file(self, cli, sample_issue):
        """Test detach without file path."""
        with pytest.raises(ValueError, match="Must provide --file"):
            cli.detach_code_reference(issue_id=sample_issue.id)


class TestCLIRefs:
    """Test CLI refs command."""

    def test_refs_empty(self, cli, sample_issue):
        """Test refs when no references exist."""
        result = cli.list_code_references(issue_id=sample_issue.id)
        assert "No code references found" in result

    def test_refs_list(self, cli, repo, sample_issue, temp_file):
        """Test listing code references."""
        repo.add_code_reference(
            issue_id=sample_issue.id,
            file_path=temp_file,
            start_line=10,
            note="Test note",
        )

        result = cli.list_code_references(issue_id=sample_issue.id)
        assert "Code references for issue" in result
        assert temp_file in result or os.path.relpath(temp_file) in result
        assert "Line: 10" in result
        assert "Note: Test note" in result

    def test_refs_json_output(self, cli, repo, sample_issue, temp_file):
        """Test refs with JSON output."""
        import json

        repo.add_code_reference(issue_id=sample_issue.id, file_path=temp_file)

        result = cli.list_code_references(issue_id=sample_issue.id, as_json=True)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["issue_id"] == sample_issue.id


class TestCLIAffected:
    """Test CLI affected command."""

    def test_affected_no_issues(self, cli):
        """Test affected when no issues reference the file."""
        result = cli.list_affected_issues(file_path="nonexistent.py")
        assert "No issues found" in result

    def test_affected_list(self, cli, repo, temp_file):
        """Test listing affected issues."""
        issue1 = repo.create_issue(Issue(title="Bug 1", priority=Priority.HIGH, status=Status.OPEN))
        issue2 = repo.create_issue(
            Issue(title="Bug 2", priority=Priority.MEDIUM, status=Status.CLOSED)
        )

        repo.add_code_reference(issue_id=issue1.id, file_path=temp_file)
        repo.add_code_reference(issue_id=issue2.id, file_path=temp_file)

        result = cli.list_affected_issues(file_path=temp_file)
        assert "Issues referencing" in result
        assert "Bug 1" in result
        assert "Bug 2" in result

    def test_affected_json_output(self, cli, repo, temp_file):
        """Test affected with JSON output."""
        import json

        issue = repo.create_issue(Issue(title="Bug", priority=Priority.HIGH, status=Status.OPEN))
        repo.add_code_reference(issue_id=issue.id, file_path=temp_file)

        result = cli.list_affected_issues(file_path=temp_file, as_json=True)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Bug"


class TestIntegration:
    """Integration tests for code references."""

    def test_full_workflow(self, cli, repo, temp_file):
        """Test complete workflow of adding, viewing, and removing references."""
        # Create issue
        issue = repo.create_issue(
            Issue(title="Test Bug", priority=Priority.HIGH, status=Status.OPEN)
        )

        # Attach reference
        result = cli.attach_code_reference(
            issue_id=issue.id,
            file_spec=f"{temp_file}:10-20",
            note="Bug location",
        )
        assert "Code reference added" in result

        # View references
        result = cli.list_code_references(issue_id=issue.id)
        assert "Lines: 10-20" in result
        assert "Bug location" in result

        # View affected issues
        result = cli.list_affected_issues(file_path=temp_file)
        assert "Test Bug" in result

        # View issue details (should include references)
        result = cli.get_issue(issue.id)
        assert "Code References:" in result

        # Detach reference
        result = cli.detach_code_reference(issue_id=issue.id, file_path=temp_file)
        assert "Removed 1 code reference" in result

        # Verify removed
        result = cli.list_code_references(issue_id=issue.id)
        assert "No code references found" in result

    def test_references_deleted_with_issue(self, repo, temp_file):
        """Test that references are deleted when issue is deleted."""
        issue = repo.create_issue(Issue(title="Test", priority=Priority.HIGH, status=Status.OPEN))
        repo.add_code_reference(issue_id=issue.id, file_path=temp_file)

        # Verify reference exists
        refs = repo.get_code_references(issue.id)
        assert len(refs) == 1

        # Delete issue
        repo.delete_issue(issue.id)

        # Verify references are gone (cascade delete)
        refs = repo.get_code_references(issue.id)
        assert len(refs) == 0
