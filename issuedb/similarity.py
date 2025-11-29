"""Text similarity functions for duplicate detection.

This module provides simple text similarity calculation using only the standard library.
It combines Levenshtein distance for short texts and Jaccard similarity for longer texts.
"""

import string
from typing import List, Tuple

from issuedb.models import Issue


def _normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase and removing punctuation.

    Args:
        text: Text to normalize.

    Returns:
        Normalized text.
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))

    # Normalize whitespace
    text = " ".join(text.split())

    return text


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Levenshtein distance (number of edits needed).
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row: list[int] = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _normalized_levenshtein_similarity(s1: str, s2: str) -> float:
    """Calculate normalized Levenshtein similarity (0.0 to 1.0).

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Similarity score from 0.0 (completely different) to 1.0 (identical).
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    max_len = max(len(s1), len(s2))
    distance = _levenshtein_distance(s1, s2)

    return 1.0 - (distance / max_len)


def _tokenize(text: str) -> set[str]:
    """Tokenize text into words.

    Args:
        text: Text to tokenize.

    Returns:
        Set of word tokens.
    """
    if not text:
        return set()

    # Split on whitespace and filter out empty strings
    tokens = {token for token in text.split() if token}

    return tokens


def _jaccard_similarity(s1: str, s2: str) -> float:
    """Calculate Jaccard similarity between two strings based on word tokens.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Jaccard similarity score from 0.0 to 1.0.
    """
    tokens1 = _tokenize(s1)
    tokens2 = _tokenize(s2)

    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    if union == 0:
        return 0.0

    return intersection / union


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts.

    Uses a combination of Levenshtein distance for short texts and
    Jaccard similarity for longer texts to provide robust similarity scoring.

    Args:
        text1: First text.
        text2: Second text.

    Returns:
        Similarity score from 0.0 (completely different) to 1.0 (identical).
    """
    # Normalize both texts
    norm1 = _normalize_text(text1)
    norm2 = _normalize_text(text2)

    if not norm1 and not norm2:
        return 1.0
    if not norm1 or not norm2:
        return 0.0

    # For very short texts (< 20 chars), use Levenshtein
    if len(norm1) < 20 or len(norm2) < 20:
        return _normalized_levenshtein_similarity(norm1, norm2)

    # For longer texts, use Jaccard similarity with word tokens
    jaccard = _jaccard_similarity(norm1, norm2)

    # Also calculate character-level similarity for short phrases
    # and combine with Jaccard for better accuracy
    lev = _normalized_levenshtein_similarity(norm1, norm2)

    # Weighted combination: favor Jaccard for longer texts
    # but still consider character-level similarity
    return 0.7 * jaccard + 0.3 * lev


def _combine_issue_text(issue: Issue) -> str:
    """Combine issue title and description for comparison.

    Args:
        issue: Issue object.

    Returns:
        Combined text from title and description.
    """
    parts = [issue.title]
    if issue.description:
        parts.append(issue.description)

    return " ".join(parts)


def find_similar_issues(
    query: str, issues: List[Issue], threshold: float = 0.6
) -> List[Tuple[Issue, float]]:
    """Find issues similar to a query text.

    Args:
        query: Query text to compare against.
        issues: List of issues to search through.
        threshold: Minimum similarity threshold (0.0 to 1.0).

    Returns:
        List of (issue, similarity_score) tuples for issues above threshold,
        sorted by similarity score in descending order.
    """
    results = []

    for issue in issues:
        # Combine title and description for comparison
        issue_text = _combine_issue_text(issue)

        # Calculate similarity
        similarity = calculate_similarity(query, issue_text)

        # Only include if above threshold
        if similarity >= threshold:
            results.append((issue, similarity))

    # Sort by similarity score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)

    return results


def find_duplicate_groups(
    issues: List[Issue], threshold: float = 0.7
) -> List[List[Tuple[Issue, float]]]:
    """Find groups of potentially duplicate issues.

    Args:
        issues: List of all issues to analyze.
        threshold: Minimum similarity threshold for duplicates.

    Returns:
        List of duplicate groups. Each group is a list of (issue, similarity_score)
        tuples, where the first issue in the group is the "primary" and subsequent
        issues are duplicates of it with their similarity scores relative to the primary.
    """
    if not issues:
        return []

    # Keep track of which issues have been grouped
    grouped_ids = set()
    duplicate_groups = []

    # Sort issues by ID to ensure consistent ordering
    sorted_issues = sorted(issues, key=lambda x: x.id if x.id else 0)

    for i, primary_issue in enumerate(sorted_issues):
        # Skip if this issue is already in a group
        if primary_issue.id in grouped_ids:
            continue

        # Find all similar issues to this one
        primary_text = _combine_issue_text(primary_issue)
        group = [(primary_issue, 1.0)]  # Primary has 100% similarity to itself

        # Compare with remaining issues
        for other_issue in sorted_issues[i + 1 :]:
            # Skip if already grouped
            if other_issue.id in grouped_ids:
                continue

            # Calculate similarity
            other_text = _combine_issue_text(other_issue)
            similarity = calculate_similarity(primary_text, other_text)

            # If above threshold, add to group
            if similarity >= threshold:
                group.append((other_issue, similarity))
                grouped_ids.add(other_issue.id)

        # Only add groups with duplicates (more than just the primary)
        if len(group) > 1:
            grouped_ids.add(primary_issue.id)
            duplicate_groups.append(group)

    return duplicate_groups
