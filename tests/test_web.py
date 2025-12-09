"""Tests for the Flask Web UI and API."""

import json
import tempfile
from pathlib import Path

import pytest

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository
from issuedb.web import app


@pytest.fixture
def temp_db() -> Path:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def repo(temp_db: Path) -> IssueRepository:
    """Create a repository with the temp database."""
    return IssueRepository(str(temp_db))


@pytest.fixture
def client(temp_db: Path):
    """Create a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        # Store temp_db path for use in requests
        client.temp_db = str(temp_db)
        yield client


@pytest.fixture
def sample_issue(repo: IssueRepository) -> Issue:
    """Create a sample issue in the repository."""
    issue = Issue(
        title="Test Issue",
        description="Test description",
        priority=Priority.HIGH,
        status=Status.OPEN,
    )
    return repo.create_issue(issue)


class TestDashboardPage:
    """Tests for the dashboard page."""

    def test_dashboard_renders(self, client, temp_db: Path) -> None:
        """Test that the dashboard page renders."""
        response = client.get(f"/?db={temp_db}")
        assert response.status_code == 200
        assert b"Dashboard" in response.data
        assert b".issue.db" in response.data

    def test_dashboard_shows_stats(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test that the dashboard shows statistics."""
        # Create some issues
        repo.create_issue(Issue(title="Issue 1", priority=Priority.HIGH, status=Status.OPEN))
        repo.create_issue(Issue(title="Issue 2", priority=Priority.LOW, status=Status.CLOSED))

        response = client.get(f"/?db={temp_db}")
        assert response.status_code == 200
        assert b"Total Issues" in response.data or b"TOTAL ISSUES" in response.data


class TestIssuesListPage:
    """Tests for the issues list page."""

    def test_issues_list_renders(self, client, temp_db: Path) -> None:
        """Test that the issues list page renders."""
        response = client.get(f"/issues?db={temp_db}")
        assert response.status_code == 200
        assert b"Issues" in response.data

    def test_issues_list_shows_issues(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test that the issues list shows created issues."""
        repo.create_issue(Issue(title="Test Issue ABC", priority=Priority.HIGH))

        response = client.get(f"/issues?db={temp_db}")
        assert response.status_code == 200
        assert b"Test Issue ABC" in response.data

    def test_issues_list_filter_by_status(
        self, client, temp_db: Path, repo: IssueRepository
    ) -> None:
        """Test filtering issues by status."""
        repo.create_issue(Issue(title="Open Issue", status=Status.OPEN))
        repo.create_issue(Issue(title="Closed Issue", status=Status.CLOSED))

        response = client.get(f"/issues?db={temp_db}&status=open")
        assert response.status_code == 200
        assert b"Open Issue" in response.data

    def test_issues_list_filter_by_priority(
        self, client, temp_db: Path, repo: IssueRepository
    ) -> None:
        """Test filtering issues by priority."""
        repo.create_issue(Issue(title="Critical Issue", priority=Priority.CRITICAL))
        repo.create_issue(Issue(title="Low Issue", priority=Priority.LOW))

        response = client.get(f"/issues?db={temp_db}&priority=critical")
        assert response.status_code == 200
        assert b"Critical Issue" in response.data

    def test_issues_list_search(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test searching issues."""
        repo.create_issue(Issue(title="Bug in login"))
        repo.create_issue(Issue(title="Feature request"))

        response = client.get(f"/issues?db={temp_db}&q=login")
        assert response.status_code == 200
        assert b"Bug in login" in response.data


class TestIssueDetailPage:
    """Tests for the issue detail page."""

    def test_issue_detail_renders(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test that the issue detail page renders."""
        issue = repo.create_issue(Issue(title="Detail Test"))

        response = client.get(f"/issues/{issue.id}?db={temp_db}")
        assert response.status_code == 200
        assert b"Detail Test" in response.data

    def test_issue_detail_shows_description(
        self, client, temp_db: Path, repo: IssueRepository
    ) -> None:
        """Test that the issue detail shows description."""
        issue = repo.create_issue(
            Issue(title="With Description", description="This is a detailed description")
        )

        response = client.get(f"/issues/{issue.id}?db={temp_db}")
        assert response.status_code == 200
        assert b"This is a detailed description" in response.data

    def test_issue_detail_not_found_redirects(self, client, temp_db: Path) -> None:
        """Test that non-existent issue redirects to issues list."""
        response = client.get(f"/issues/99999?db={temp_db}")
        assert response.status_code == 302  # Redirect


class TestIssueFormPages:
    """Tests for issue form pages."""

    def test_new_issue_form_renders(self, client, temp_db: Path) -> None:
        """Test that the new issue form renders."""
        response = client.get(f"/issues/new?db={temp_db}")
        assert response.status_code == 200
        assert b"New Issue" in response.data
        assert b"Title" in response.data

    def test_edit_issue_form_renders(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test that the edit issue form renders."""
        issue = repo.create_issue(Issue(title="Edit Test"))

        response = client.get(f"/issues/{issue.id}/edit?db={temp_db}")
        assert response.status_code == 200
        assert b"Edit Issue" in response.data
        assert b"Edit Test" in response.data


class TestAPIEndpoints:
    """Tests for API endpoints."""

    def test_api_list_issues(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test GET /api/issues."""
        repo.create_issue(Issue(title="API Test Issue"))

        response = client.get(f"/api/issues?db={temp_db}")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["title"] == "API Test Issue"

    def test_api_create_issue(self, client, temp_db: Path) -> None:
        """Test POST /api/issues."""
        response = client.post(
            f"/api/issues?db={temp_db}",
            json={"title": "New API Issue", "description": "Created via API"},
            content_type="application/json",
        )
        assert response.status_code == 201

        data = json.loads(response.data)
        assert data["title"] == "New API Issue"
        assert data["description"] == "Created via API"
        assert data["id"] is not None

    def test_api_create_issue_form(self, client, temp_db: Path) -> None:
        """Test POST /api/issues with form data."""
        response = client.post(
            f"/api/issues?db={temp_db}",
            data={"title": "Form Issue", "priority": "high"},
        )
        assert response.status_code == 302  # Redirect after creation

    def test_api_create_issue_missing_title(self, client, temp_db: Path) -> None:
        """Test POST /api/issues without title."""
        response = client.post(
            f"/api/issues?db={temp_db}",
            json={"description": "No title"},
            content_type="application/json",
        )
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data

    def test_api_get_issue(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test GET /api/issues/<id>."""
        issue = repo.create_issue(Issue(title="Get Test"))

        response = client.get(f"/api/issues/{issue.id}?db={temp_db}")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["title"] == "Get Test"
        assert data["id"] == issue.id

    def test_api_get_issue_not_found(self, client, temp_db: Path) -> None:
        """Test GET /api/issues/<id> with non-existent ID."""
        response = client.get(f"/api/issues/99999?db={temp_db}")
        assert response.status_code == 404

    def test_api_update_issue(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test PUT /api/issues/<id>."""
        issue = repo.create_issue(Issue(title="Original Title"))

        response = client.put(
            f"/api/issues/{issue.id}?db={temp_db}",
            json={"title": "Updated Title"},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["title"] == "Updated Title"

    def test_api_update_issue_status(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test PATCH /api/issues/<id> to update status."""
        issue = repo.create_issue(Issue(title="Status Test", status=Status.OPEN))

        response = client.patch(
            f"/api/issues/{issue.id}?db={temp_db}",
            json={"status": "closed"},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "closed"

    def test_api_delete_issue(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test DELETE /api/issues/<id>."""
        issue = repo.create_issue(Issue(title="Delete Test"))

        response = client.delete(f"/api/issues/{issue.id}?db={temp_db}")
        assert response.status_code == 200

        # Verify deletion
        response = client.get(f"/api/issues/{issue.id}?db={temp_db}")
        assert response.status_code == 404

    def test_api_summary(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test GET /api/summary."""
        repo.create_issue(Issue(title="Issue 1", status=Status.OPEN))
        repo.create_issue(Issue(title="Issue 2", status=Status.CLOSED))

        response = client.get(f"/api/summary?db={temp_db}")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "total_issues" in data
        assert "by_status" in data
        assert data["total_issues"] == 2

    def test_api_next_issue(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test GET /api/next."""
        repo.create_issue(Issue(title="Critical Issue", priority=Priority.CRITICAL))
        repo.create_issue(Issue(title="Low Issue", priority=Priority.LOW))

        response = client.get(f"/api/next?db={temp_db}")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["title"] == "Critical Issue"


class TestCommentEndpoints:
    """Tests for comment-related endpoints."""

    def test_api_add_comment(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST /api/issues/<id>/comments."""
        issue = repo.create_issue(Issue(title="Comment Test"))

        response = client.post(
            f"/api/issues/{issue.id}/comments?db={temp_db}",
            json={"text": "This is a test comment"},
            content_type="application/json",
        )
        assert response.status_code == 201

        data = json.loads(response.data)
        assert data["text"] == "This is a test comment"
        assert data["issue_id"] == issue.id

    def test_api_add_comment_empty(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST /api/issues/<id>/comments with empty text."""
        issue = repo.create_issue(Issue(title="Comment Test"))

        response = client.post(
            f"/api/issues/{issue.id}/comments?db={temp_db}",
            json={"text": "   "},
            content_type="application/json",
        )
        assert response.status_code == 400


class TestWorkflowEndpoints:
    """Tests for workflow-related endpoints."""

    def test_api_start_issue(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST /api/issues/<id>/start."""
        issue = repo.create_issue(Issue(title="Start Test"))

        response = client.post(f"/api/issues/{issue.id}/start?db={temp_db}")
        assert response.status_code == 302  # Redirect

    def test_api_stop_issue(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST /api/issues/stop."""
        issue = repo.create_issue(Issue(title="Stop Test"))
        repo.start_issue(issue.id)

        response = client.post(f"/api/issues/stop?db={temp_db}")
        assert response.status_code == 302  # Redirect

    def test_api_stop_issue_and_close(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST /api/issues/stop?close=1."""
        issue = repo.create_issue(Issue(title="Stop Close Test"))
        repo.start_issue(issue.id)

        response = client.post(f"/api/issues/stop?db={temp_db}&close=1")
        assert response.status_code == 302  # Redirect


class TestMethodOverride:
    """Tests for HTML form method override."""

    def test_method_override_patch(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST with _method=PATCH."""
        issue = repo.create_issue(Issue(title="Override Test", status=Status.OPEN))

        response = client.post(
            f"/api/issues/{issue.id}?db={temp_db}",
            data={"_method": "PATCH", "status": "closed"},
        )
        assert response.status_code == 302  # Redirect

    def test_method_override_delete(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test POST with _method=DELETE."""
        issue = repo.create_issue(Issue(title="Delete Override Test"))

        response = client.post(
            f"/api/issues/{issue.id}?db={temp_db}",
            data={"_method": "DELETE"},
        )
        assert response.status_code == 302  # Redirect


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_database(self, client, temp_db: Path) -> None:
        """Test dashboard with empty database."""
        response = client.get(f"/?db={temp_db}")
        assert response.status_code == 200

    def test_api_no_updates_provided(self, client, temp_db: Path, repo: IssueRepository) -> None:
        """Test PATCH with no updates."""
        issue = repo.create_issue(Issue(title="No Update Test"))

        response = client.patch(
            f"/api/issues/{issue.id}?db={temp_db}",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_special_characters_in_title(self, client, temp_db: Path) -> None:
        """Test creating issue with special characters."""
        response = client.post(
            f"/api/issues?db={temp_db}",
            json={"title": "Test <script>alert('xss')</script>"},
            content_type="application/json",
        )
        assert response.status_code == 201

        data = json.loads(response.data)
        # Title should be preserved but won't execute as script
        assert "<script>" in data["title"]
