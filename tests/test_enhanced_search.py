"""Tests for enhanced search functionality."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from issuedb.date_utils import format_date_for_display, parse_date, validate_date_range
from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def repo(temp_db):
    """Create a repository instance with temp database."""
    return IssueRepository(temp_db)


@pytest.fixture
def sample_issues(repo):
    """Create sample issues for testing."""
    now = datetime.now()

    issues = [
        Issue(
            title="Critical bug in production",
            description="System is down",
            priority=Priority.CRITICAL,
            status=Status.OPEN,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(hours=2),
        ),
        Issue(
            title="Add new feature",
            description="User requested feature",
            priority=Priority.MEDIUM,
            status=Status.IN_PROGRESS,
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=1),
        ),
        Issue(
            title="Fix minor UI bug",
            description="Button color is wrong",
            priority=Priority.LOW,
            status=Status.CLOSED,
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=7),
        ),
        Issue(
            title="Performance optimization",
            description="Database queries are slow",
            priority=Priority.HIGH,
            status=Status.OPEN,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(hours=1),
        ),
    ]

    created = []
    for issue in issues:
        created.append(repo.create_issue(issue))

    return created


class TestDateParsing:
    """Test date parsing utilities."""

    def test_parse_date_yyyy_mm_dd(self):
        """Test parsing YYYY-MM-DD format."""
        result = parse_date("2025-11-26")
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 26

    def test_parse_date_today(self):
        """Test parsing 'today'."""
        result = parse_date("today")
        now = datetime.now()
        assert result.year == now.year
        assert result.month == now.month
        assert result.day == now.day
        assert result.hour == 0
        assert result.minute == 0

    def test_parse_date_yesterday(self):
        """Test parsing 'yesterday'."""
        result = parse_date("yesterday")
        yesterday = datetime.now() - timedelta(days=1)
        assert result.year == yesterday.year
        assert result.month == yesterday.month
        assert result.day == yesterday.day

    def test_parse_date_relative_days(self):
        """Test parsing relative days (7d)."""
        result = parse_date("7d")
        expected = datetime.now() - timedelta(days=7)
        # Check within 1 second tolerance
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_date_relative_weeks(self):
        """Test parsing relative weeks (2w)."""
        result = parse_date("2w")
        expected = datetime.now() - timedelta(weeks=2)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_date_relative_months(self):
        """Test parsing relative months (1m)."""
        result = parse_date("1m")
        expected = datetime.now() - timedelta(days=30)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("invalid-date")

    def test_validate_date_range_valid(self):
        """Test valid date range."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 12, 31)
        validate_date_range(start, end)  # Should not raise

    def test_validate_date_range_invalid(self):
        """Test invalid date range."""
        start = datetime(2025, 12, 31)
        end = datetime(2025, 1, 1)
        with pytest.raises(ValueError, match="End date.*cannot be before start date"):
            validate_date_range(start, end)

    def test_format_date_for_display(self):
        """Test date formatting."""
        dt = datetime(2025, 11, 26, 14, 30, 45)
        result = format_date_for_display(dt)
        assert result == "2025-11-26 14:30:45"


class TestAdvancedSearch:
    """Test advanced search functionality."""

    def test_search_by_keyword(self, repo, sample_issues):
        """Test search by keyword."""
        results = repo.search_issues_advanced(keyword="bug")
        assert len(results) == 2  # "Critical bug" and "Fix minor UI bug"

    def test_search_by_created_after(self, repo, sample_issues):
        """Test search by created_after date."""
        results = repo.search_issues_advanced(created_after="7d")
        # Should get issues created in last 7 days
        assert len(results) >= 2

    def test_search_by_created_before(self, repo, sample_issues):
        """Test search by created_before date."""
        results = repo.search_issues_advanced(created_before="7d")
        # Should get issues created more than 7 days ago
        assert len(results) >= 1

    def test_search_by_updated_after(self, repo, sample_issues):
        """Test search by updated_after date."""
        results = repo.search_issues_advanced(updated_after="1d")
        # Should get recently updated issues
        assert len(results) >= 2

    def test_search_by_updated_before(self, repo, sample_issues):
        """Test search by updated_before date."""
        results = repo.search_issues_advanced(updated_before="7d")
        # Should get issues updated more than 7 days ago
        assert len(results) >= 1

    def test_search_by_priority_single(self, repo, sample_issues):
        """Test search by single priority."""
        results = repo.search_issues_advanced(priorities=["critical"])
        assert len(results) == 1
        assert results[0].priority == Priority.CRITICAL

    def test_search_by_priority_multiple(self, repo, sample_issues):
        """Test search by multiple priorities."""
        results = repo.search_issues_advanced(priorities=["high", "critical"])
        assert len(results) == 2
        for issue in results:
            assert issue.priority in [Priority.HIGH, Priority.CRITICAL]

    def test_search_by_status_single(self, repo, sample_issues):
        """Test search by single status."""
        results = repo.search_issues_advanced(statuses=["open"])
        assert len(results) == 2
        for issue in results:
            assert issue.status == Status.OPEN

    def test_search_by_status_multiple(self, repo, sample_issues):
        """Test search by multiple statuses."""
        results = repo.search_issues_advanced(statuses=["open", "in-progress"])
        assert len(results) == 3
        for issue in results:
            assert issue.status in [Status.OPEN, Status.IN_PROGRESS]

    def test_search_combined_filters(self, repo, sample_issues):
        """Test search with multiple filters combined."""
        results = repo.search_issues_advanced(
            keyword="bug", priorities=["critical", "low"], statuses=["open", "closed"]
        )
        assert len(results) == 2  # Critical bug (open) and minor UI bug (closed)

    def test_search_sort_by_created_desc(self, repo, sample_issues):
        """Test sorting by created date descending."""
        results = repo.search_issues_advanced(sort_by="created", order="desc")
        # Most recent first
        assert results[0].title == "Critical bug in production"

    def test_search_sort_by_created_asc(self, repo, sample_issues):
        """Test sorting by created date ascending."""
        results = repo.search_issues_advanced(sort_by="created", order="asc")
        # Oldest first
        assert results[0].title == "Fix minor UI bug"

    def test_search_sort_by_updated_desc(self, repo, sample_issues):
        """Test sorting by updated date descending."""
        results = repo.search_issues_advanced(sort_by="updated", order="desc")
        # Most recently updated first
        assert results[0].title == "Performance optimization"

    def test_search_sort_by_priority_desc(self, repo, sample_issues):
        """Test sorting by priority descending (critical first)."""
        results = repo.search_issues_advanced(sort_by="priority", order="desc")
        # Critical should be first
        assert results[0].priority == Priority.CRITICAL
        assert results[-1].priority == Priority.LOW

    def test_search_sort_by_priority_asc(self, repo, sample_issues):
        """Test sorting by priority ascending (low first)."""
        results = repo.search_issues_advanced(sort_by="priority", order="asc")
        # Low should be first
        assert results[0].priority == Priority.LOW
        assert results[-1].priority == Priority.CRITICAL

    def test_search_with_limit(self, repo, sample_issues):
        """Test search with result limit."""
        results = repo.search_issues_advanced(limit=2)
        assert len(results) == 2

    def test_search_date_range_filtering(self, repo, sample_issues):
        """Test filtering with date range."""
        results = repo.search_issues_advanced(created_after="14d", created_before="2d")
        # Should get issues created between 14 and 2 days ago
        assert len(results) >= 1

    def test_search_invalid_sort_by(self, repo, sample_issues):
        """Test search with invalid sort_by parameter."""
        with pytest.raises(ValueError, match="Invalid sort_by"):
            repo.search_issues_advanced(sort_by="invalid")

    def test_search_invalid_order(self, repo, sample_issues):
        """Test search with invalid order parameter."""
        with pytest.raises(ValueError, match="Invalid order"):
            repo.search_issues_advanced(order="invalid")

    def test_search_invalid_priority(self, repo, sample_issues):
        """Test search with invalid priority."""
        with pytest.raises(ValueError, match="Invalid priority"):
            repo.search_issues_advanced(priorities=["invalid"])

    def test_search_invalid_status(self, repo, sample_issues):
        """Test search with invalid status."""
        with pytest.raises(ValueError, match="Invalid status"):
            repo.search_issues_advanced(statuses=["invalid"])

    def test_search_no_results(self, repo, sample_issues):
        """Test search that returns no results."""
        results = repo.search_issues_advanced(keyword="nonexistent")
        assert len(results) == 0


class TestSavedSearches:
    """Test saved search functionality."""

    def test_save_search(self, repo):
        """Test saving a search."""
        params = {
            "keyword": "bug",
            "priorities": ["high", "critical"],
            "statuses": ["open"],
            "sort_by": "created",
            "order": "desc",
        }
        search_id = repo.save_search("high-priority-bugs", params)
        assert search_id > 0

    def test_save_search_duplicate_name(self, repo):
        """Test saving search with duplicate name."""
        params = {"keyword": "test"}
        repo.save_search("test-search", params)

        with pytest.raises(ValueError, match="already exists"):
            repo.save_search("test-search", params)

    def test_save_search_empty_name(self, repo):
        """Test saving search with empty name."""
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.save_search("", {"keyword": "test"})

    def test_get_saved_search(self, repo):
        """Test retrieving a saved search."""
        params = {
            "keyword": "bug",
            "priorities": ["high"],
        }
        repo.save_search("my-search", params)

        result = repo.get_saved_search("my-search")
        assert result is not None
        assert result["name"] == "my-search"
        assert result["query_params"]["keyword"] == "bug"
        assert result["query_params"]["priorities"] == ["high"]

    def test_get_saved_search_not_found(self, repo):
        """Test retrieving non-existent saved search."""
        result = repo.get_saved_search("nonexistent")
        assert result is None

    def test_list_saved_searches(self, repo):
        """Test listing all saved searches."""
        repo.save_search("search1", {"keyword": "bug"})
        repo.save_search("search2", {"priorities": ["high"]})

        searches = repo.list_saved_searches()
        assert len(searches) == 2
        names = [s["name"] for s in searches]
        assert "search1" in names
        assert "search2" in names

    def test_list_saved_searches_empty(self, repo):
        """Test listing when no saved searches exist."""
        searches = repo.list_saved_searches()
        assert len(searches) == 0

    def test_delete_saved_search(self, repo):
        """Test deleting a saved search."""
        repo.save_search("to-delete", {"keyword": "test"})
        result = repo.delete_saved_search("to-delete")
        assert result is True

        # Verify it's deleted
        assert repo.get_saved_search("to-delete") is None

    def test_delete_saved_search_not_found(self, repo):
        """Test deleting non-existent saved search."""
        result = repo.delete_saved_search("nonexistent")
        assert result is False

    def test_run_saved_search(self, repo, sample_issues):
        """Test executing a saved search."""
        params = {
            "keyword": "bug",
            "priorities": ["critical", "low"],
        }
        repo.save_search("bug-search", params)

        results = repo.run_saved_search("bug-search")
        assert len(results) == 2  # Critical bug and minor UI bug

    def test_run_saved_search_not_found(self, repo):
        """Test executing non-existent saved search."""
        with pytest.raises(ValueError, match="not found"):
            repo.run_saved_search("nonexistent")

    def test_saved_search_persistence(self, repo, sample_issues):
        """Test that saved searches persist and work correctly."""
        # Save a complex search
        params = {
            "priorities": ["high", "critical"],
            "statuses": ["open"],
            "sort_by": "priority",
            "order": "desc",
        }
        repo.save_search("urgent-issues", params)

        # Execute it
        results = repo.run_saved_search("urgent-issues")
        assert len(results) == 2  # Critical and high priority open issues
        assert results[0].priority == Priority.CRITICAL  # Sorted by priority desc

    def test_saved_search_with_all_parameters(self, repo, sample_issues):
        """Test saved search with all possible parameters."""
        params = {
            "keyword": "bug",
            "created_after": "30d",
            "created_before": "today",
            "updated_after": "14d",
            "updated_before": "today",
            "priorities": ["high", "critical"],
            "statuses": ["open", "in-progress"],
            "sort_by": "updated",
            "order": "desc",
            "limit": 10,
        }
        repo.save_search("comprehensive-search", params)

        # Should not raise any errors
        results = repo.run_saved_search("comprehensive-search")
        assert isinstance(results, list)


class TestCLIIntegration:
    """Test CLI integration with enhanced search."""

    def test_cli_search_with_date_filters(self, repo, sample_issues):
        """Test CLI-like usage of advanced search."""
        # Simulate CLI call with date filters
        results = repo.search_issues_advanced(
            created_after="7d",
            statuses=["open", "in-progress"],
        )
        assert len(results) >= 2

    def test_cli_search_with_multiple_priorities(self, repo, sample_issues):
        """Test CLI-like usage with comma-separated priorities."""
        # This simulates: --priority high,critical
        results = repo.search_issues_advanced(
            priorities=["high", "critical"],
        )
        assert len(results) == 2

    def test_cli_search_with_sorting(self, repo, sample_issues):
        """Test CLI-like usage with sorting options."""
        # This simulates: --sort priority --order desc
        results = repo.search_issues_advanced(
            sort_by="priority",
            order="desc",
        )
        assert results[0].priority == Priority.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
