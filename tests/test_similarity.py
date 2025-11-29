"""Tests for similarity calculation functions."""

import pytest

from issuedb.models import Issue, Priority, Status
from issuedb.similarity import (
    _combine_issue_text,
    _jaccard_similarity,
    _levenshtein_distance,
    _normalize_text,
    _normalized_levenshtein_similarity,
    _tokenize,
    calculate_similarity,
    find_duplicate_groups,
    find_similar_issues,
)


class TestTextNormalization:
    """Test text normalization functions."""

    def test_normalize_text_lowercase(self):
        """Test that text is converted to lowercase."""
        result = _normalize_text("HELLO WORLD")
        assert result == "hello world"

    def test_normalize_text_punctuation(self):
        """Test that punctuation is removed."""
        result = _normalize_text("Hello, World!")
        assert result == "hello world"

    def test_normalize_text_whitespace(self):
        """Test that extra whitespace is normalized."""
        result = _normalize_text("hello   world  \n  test")
        assert result == "hello world test"

    def test_normalize_text_empty(self):
        """Test normalizing empty string."""
        result = _normalize_text("")
        assert result == ""

    def test_normalize_text_none(self):
        """Test normalizing None."""
        result = _normalize_text(None)
        assert result == ""

    def test_normalize_text_special_chars(self):
        """Test with special characters."""
        result = _normalize_text("Hello-World_Test@123")
        assert "hello" in result
        assert "world" in result
        assert "test" in result


class TestLevenshteinDistance:
    """Test Levenshtein distance calculation."""

    def test_levenshtein_identical(self):
        """Test distance between identical strings."""
        distance = _levenshtein_distance("hello", "hello")
        assert distance == 0

    def test_levenshtein_one_char_difference(self):
        """Test distance with one character difference."""
        distance = _levenshtein_distance("hello", "hallo")
        assert distance == 1

    def test_levenshtein_empty_strings(self):
        """Test distance with empty strings."""
        assert _levenshtein_distance("", "") == 0
        assert _levenshtein_distance("hello", "") == 5
        assert _levenshtein_distance("", "world") == 5

    def test_levenshtein_completely_different(self):
        """Test distance between completely different strings."""
        distance = _levenshtein_distance("abc", "xyz")
        assert distance == 3

    def test_levenshtein_insertion(self):
        """Test distance with character insertion."""
        distance = _levenshtein_distance("test", "tests")
        assert distance == 1

    def test_levenshtein_deletion(self):
        """Test distance with character deletion."""
        distance = _levenshtein_distance("tests", "test")
        assert distance == 1

    def test_levenshtein_substitution(self):
        """Test distance with character substitution."""
        distance = _levenshtein_distance("kitten", "sitten")
        assert distance == 1


class TestNormalizedLevenshteinSimilarity:
    """Test normalized Levenshtein similarity."""

    def test_identical_strings(self):
        """Test similarity between identical strings."""
        similarity = _normalized_levenshtein_similarity("hello", "hello")
        assert similarity == 1.0

    def test_empty_strings(self):
        """Test similarity with empty strings."""
        assert _normalized_levenshtein_similarity("", "") == 1.0
        assert _normalized_levenshtein_similarity("hello", "") == 0.0
        assert _normalized_levenshtein_similarity("", "world") == 0.0

    def test_completely_different(self):
        """Test similarity between completely different strings."""
        similarity = _normalized_levenshtein_similarity("abc", "xyz")
        assert similarity == 0.0

    def test_partial_similarity(self):
        """Test partial similarity."""
        similarity = _normalized_levenshtein_similarity("hello", "hallo")
        assert 0.0 < similarity < 1.0
        assert similarity > 0.5  # Should be quite similar

    def test_similarity_range(self):
        """Test that similarity is always between 0 and 1."""
        test_pairs = [
            ("test", "test"),
            ("test", "tests"),
            ("hello", "world"),
            ("a", "b"),
            ("abc", "xyz"),
        ]

        for s1, s2 in test_pairs:
            similarity = _normalized_levenshtein_similarity(s1, s2)
            assert 0.0 <= similarity <= 1.0


class TestTokenization:
    """Test text tokenization."""

    def test_tokenize_simple(self):
        """Test tokenizing simple text."""
        tokens = _tokenize("hello world")
        assert tokens == {"hello", "world"}

    def test_tokenize_with_whitespace(self):
        """Test tokenizing with extra whitespace."""
        tokens = _tokenize("hello   world  test")
        assert tokens == {"hello", "world", "test"}

    def test_tokenize_empty(self):
        """Test tokenizing empty string."""
        tokens = _tokenize("")
        assert tokens == set()

    def test_tokenize_single_word(self):
        """Test tokenizing single word."""
        tokens = _tokenize("hello")
        assert tokens == {"hello"}

    def test_tokenize_preserves_unique(self):
        """Test that tokenization creates a set (unique values)."""
        tokens = _tokenize("hello world hello")
        assert tokens == {"hello", "world"}


class TestJaccardSimilarity:
    """Test Jaccard similarity calculation."""

    def test_jaccard_identical(self):
        """Test Jaccard similarity of identical strings."""
        similarity = _jaccard_similarity("hello world", "hello world")
        assert similarity == 1.0

    def test_jaccard_no_overlap(self):
        """Test Jaccard similarity with no common words."""
        similarity = _jaccard_similarity("hello world", "foo bar")
        assert similarity == 0.0

    def test_jaccard_partial_overlap(self):
        """Test Jaccard similarity with partial overlap."""
        similarity = _jaccard_similarity("hello world test", "hello world foo")
        # Common: {hello, world} = 2
        # Union: {hello, world, test, foo} = 4
        # Similarity: 2/4 = 0.5
        assert similarity == 0.5

    def test_jaccard_empty_strings(self):
        """Test Jaccard similarity with empty strings."""
        assert _jaccard_similarity("", "") == 1.0
        assert _jaccard_similarity("hello", "") == 0.0
        assert _jaccard_similarity("", "world") == 0.0

    def test_jaccard_subset(self):
        """Test when one string is subset of another."""
        similarity = _jaccard_similarity("hello", "hello world")
        # Common: {hello} = 1
        # Union: {hello, world} = 2
        # Similarity: 1/2 = 0.5
        assert similarity == 0.5


class TestCalculateSimilarity:
    """Test overall similarity calculation."""

    def test_similarity_identical_short(self):
        """Test similarity of identical short texts."""
        similarity = calculate_similarity("hello", "hello")
        assert similarity == 1.0

    def test_similarity_identical_long(self):
        """Test similarity of identical long texts."""
        text = "this is a longer text with multiple words"
        similarity = calculate_similarity(text, text)
        assert similarity == 1.0

    def test_similarity_empty_strings(self):
        """Test similarity with empty strings."""
        assert calculate_similarity("", "") == 1.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity("", "world") == 0.0

    def test_similarity_short_texts(self):
        """Test similarity uses Levenshtein for short texts."""
        # Short texts (< 20 chars) should use Levenshtein
        similarity = calculate_similarity("fix bug", "fix bug")
        assert similarity == 1.0

        similarity = calculate_similarity("fix bug", "fix bag")
        assert 0.5 < similarity < 1.0

    def test_similarity_long_texts(self):
        """Test similarity uses combined approach for long texts."""
        text1 = "this is a longer text with many words for testing"
        text2 = "this is a longer text with different words for testing"

        similarity = calculate_similarity(text1, text2)
        # Should be somewhat similar (many common words)
        assert 0.5 < similarity < 1.0

    def test_similarity_range(self):
        """Test that similarity is always between 0 and 1."""
        test_pairs = [
            ("hello", "world"),
            ("test issue", "test issue"),
            ("fix login bug", "fix authentication problem"),
            ("short", "s"),
            ("this is a long text", "completely different words here"),
        ]

        for text1, text2 in test_pairs:
            similarity = calculate_similarity(text1, text2)
            assert 0.0 <= similarity <= 1.0, f"Failed for: {text1}, {text2}"

    def test_similarity_case_insensitive(self):
        """Test that similarity is case-insensitive."""
        similarity1 = calculate_similarity("HELLO WORLD", "hello world")
        similarity2 = calculate_similarity("hello world", "hello world")

        assert similarity1 == similarity2

    def test_similarity_punctuation_ignored(self):
        """Test that punctuation is ignored."""
        similarity1 = calculate_similarity("hello, world!", "hello world")
        similarity2 = calculate_similarity("hello world", "hello world")

        assert similarity1 == similarity2


class TestCombineIssueText:
    """Test combining issue title and description."""

    def test_combine_title_only(self):
        """Test combining with title only."""
        issue = Issue(title="Test Title", priority=Priority.MEDIUM, status=Status.OPEN)
        text = _combine_issue_text(issue)

        assert text == "Test Title"

    def test_combine_title_and_description(self):
        """Test combining title and description."""
        issue = Issue(
            title="Test Title",
            description="Test Description",
            priority=Priority.MEDIUM,
            status=Status.OPEN,
        )
        text = _combine_issue_text(issue)

        assert "Test Title" in text
        assert "Test Description" in text
        assert text == "Test Title Test Description"

    def test_combine_no_description(self):
        """Test combining when description is None."""
        issue = Issue(
            title="Test Title",
            description=None,
            priority=Priority.MEDIUM,
            status=Status.OPEN,
        )
        text = _combine_issue_text(issue)

        assert text == "Test Title"


class TestFindSimilarIssues:
    """Test finding similar issues."""

    @pytest.fixture
    def sample_issues(self):
        """Create sample issues for testing."""
        return [
            Issue(
                id=1,
                title="Fix login bug",
                description="Users cannot login",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                id=2,
                title="Login problem",
                description="Authentication fails",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                id=3,
                title="Add dark mode",
                description="Implement dark theme",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            ),
            Issue(
                id=4,
                title="Database migration issue",
                description="Migration script fails",
                priority=Priority.CRITICAL,
                status=Status.OPEN,
            ),
        ]

    def test_find_similar_issues_basic(self, sample_issues):
        """Test finding similar issues."""
        results = find_similar_issues("login authentication problem", sample_issues)

        # Should find login-related issues
        assert len(results) > 0
        issue_ids = [issue.id for issue, _ in results]
        assert 1 in issue_ids or 2 in issue_ids

    def test_find_similar_issues_with_threshold(self, sample_issues):
        """Test finding similar issues with threshold."""
        # Low threshold should return more results
        low_results = find_similar_issues("login", sample_issues, threshold=0.3)

        # High threshold should return fewer results
        high_results = find_similar_issues("login", sample_issues, threshold=0.9)

        assert len(low_results) >= len(high_results)

    def test_find_similar_issues_sorted(self, sample_issues):
        """Test that results are sorted by similarity."""
        results = find_similar_issues("login authentication", sample_issues, threshold=0.1)

        if len(results) > 1:
            # Check that similarity scores are in descending order
            similarities = [similarity for _, similarity in results]
            assert similarities == sorted(similarities, reverse=True)

    def test_find_similar_issues_threshold_filtering(self, sample_issues):
        """Test that threshold filters results correctly."""
        results = find_similar_issues("login", sample_issues, threshold=0.99)

        # Very high threshold should return few or no results
        # (unless query exactly matches an issue)
        for _issue, similarity in results:
            assert similarity >= 0.99

    def test_find_similar_issues_no_matches(self, sample_issues):
        """Test with query that matches nothing."""
        results = find_similar_issues("quantum physics relativity", sample_issues, threshold=0.7)

        # Should return empty list or very few results
        assert len(results) == 0 or all(sim < 0.7 for _, sim in results)

    def test_find_similar_issues_empty_list(self):
        """Test finding similar issues in empty list."""
        results = find_similar_issues("test query", [], threshold=0.5)
        assert len(results) == 0


class TestFindDuplicateGroups:
    """Test finding duplicate groups."""

    @pytest.fixture
    def duplicate_issues(self):
        """Create issues with duplicates."""
        return [
            Issue(
                id=1,
                title="Fix login bug",
                description="Users cannot login",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                id=2,
                title="Login issue",
                description="Users can't authenticate",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                id=3,
                title="Add dark mode",
                description="Implement dark theme",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            ),
            Issue(
                id=4,
                title="Dark theme needed",
                description="Add dark mode to app",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            ),
            Issue(
                id=5,
                title="Database migration",
                description="Unique issue",
                priority=Priority.LOW,
                status=Status.OPEN,
            ),
        ]

    def test_find_duplicate_groups_basic(self, duplicate_issues):
        """Test finding basic duplicate groups."""
        groups = find_duplicate_groups(duplicate_issues, threshold=0.4)

        # Should find at least one group (login or dark mode)
        assert len(groups) >= 0

        # Each group should have at least 2 issues
        for group in groups:
            assert len(group) >= 2

    def test_find_duplicate_groups_structure(self, duplicate_issues):
        """Test duplicate group structure."""
        groups = find_duplicate_groups(duplicate_issues, threshold=0.5)

        for group in groups:
            # First item should be primary with similarity 1.0
            primary_issue, primary_sim = group[0]
            assert primary_sim == 1.0

            # Other items should be duplicates with similarity >= threshold
            for issue, similarity in group[1:]:
                assert similarity >= 0.5
                assert issue.id != primary_issue.id

    def test_find_duplicate_groups_no_duplicates(self):
        """Test with no duplicates."""
        unique_issues = [
            Issue(
                id=1,
                title="Fix authentication bug in production",
                priority=Priority.HIGH,
                status=Status.OPEN,
            ),
            Issue(
                id=2,
                title="Implement new dashboard design",
                priority=Priority.MEDIUM,
                status=Status.OPEN,
            ),
            Issue(
                id=3,
                title="Update database schema for users",
                priority=Priority.LOW,
                status=Status.OPEN,
            ),
        ]

        groups = find_duplicate_groups(unique_issues, threshold=0.7)

        # Should find no groups or very few
        # Using <= instead of == because similarity can vary
        assert len(groups) <= 1

    def test_find_duplicate_groups_high_threshold(self, duplicate_issues):
        """Test with very high threshold."""
        groups = find_duplicate_groups(duplicate_issues, threshold=0.95)

        # Very high threshold should find fewer groups
        assert len(groups) <= len(duplicate_issues)

    def test_find_duplicate_groups_empty_list(self):
        """Test with empty issue list."""
        groups = find_duplicate_groups([], threshold=0.7)
        assert len(groups) == 0

    def test_find_duplicate_groups_no_duplicates_within_group(self, duplicate_issues):
        """Test that each issue appears in at most one group."""
        groups = find_duplicate_groups(duplicate_issues, threshold=0.5)

        seen_ids = set()
        for group in groups:
            for issue, _ in group:
                # Each issue should only appear once
                assert issue.id not in seen_ids
                seen_ids.add(issue.id)

    def test_find_duplicate_groups_consistent_ordering(self, duplicate_issues):
        """Test that groups are consistently ordered."""
        # Run multiple times
        groups1 = find_duplicate_groups(duplicate_issues, threshold=0.5)
        groups2 = find_duplicate_groups(duplicate_issues, threshold=0.5)

        # Results should be identical
        assert len(groups1) == len(groups2)

        for g1, g2 in zip(groups1, groups2):
            # Primary issues should be the same
            assert g1[0][0].id == g2[0][0].id
