"""Text similarity functions for duplicate detection.

This module provides simple text similarity calculation using only the standard library.
It combines Levenshtein distance for short texts and Jaccard similarity for longer texts.
"""

import string

from issuedb.models import Issue

# Maximum string length for running the full character-level Levenshtein DP.
# The DP is O(len1 * len2); above this cap we fall back to token-based
# (Jaccard) similarity to avoid pathological O(n*m) blowups when many long
# descriptions are compared pairwise (find_duplicate_groups is O(issues^2)).
MAX_LEVENSHTEIN_LEN = 200

# When the two strings differ in length by more than this ratio, a raw
# character Levenshtein score is dominated by the length difference (a short
# query contained in a long text scores near 0). In that case we prefer
# token-set / Jaccard similarity, which captures containment far better.
LENGTH_RATIO_THRESHOLD = 2.0


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


def _overlap_coefficient(s1: str, s2: str) -> float:
    """Calculate the token overlap (containment) coefficient between two texts.

    Unlike Jaccard, this divides the intersection by the size of the *smaller*
    token set, so a short text fully contained in a longer one scores high.
    This is the key signal for the "short query vs long description" case.

    Args:
        s1: First text.
        s2: Second text.

    Returns:
        Overlap coefficient from 0.0 to 1.0.
    """
    tokens1 = _tokenize(s1)
    tokens2 = _tokenize(s2)

    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    smaller = min(len(tokens1), len(tokens2))

    if smaller == 0:
        return 0.0

    return intersection / smaller


def _token_similarity_sets(tokens1: set[str], tokens2: set[str]) -> float:
    """Token-based similarity from precomputed token sets (see _token_similarity)."""
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    jaccard = intersection / union if union else 0.0
    smaller = min(len(tokens1), len(tokens2))
    overlap = intersection / smaller if smaller else 0.0

    # Weighted blend; favor Jaccard but let overlap rescue containment cases.
    return 0.6 * jaccard + 0.4 * overlap


def _token_similarity(s1: str, s2: str) -> float:
    """Token-based similarity blending Jaccard with overlap (containment).

    Jaccard rewards strings of similar size with high overlap, while the
    overlap coefficient rewards containment (a short text inside a long one).
    Blending the two gives a robust score that does not collapse to ~0 when
    the two strings differ greatly in length.

    Args:
        s1: First text.
        s2: Second text.

    Returns:
        Token similarity score from 0.0 to 1.0.
    """
    return _token_similarity_sets(_tokenize(s1), _tokenize(s2))


def _similarity_from_normalized(
    norm1: str,
    norm2: str,
    tokens1: "set[str] | None" = None,
    tokens2: "set[str] | None" = None,
) -> float:
    """Similarity of two already-normalized, non-empty texts.

    Accepts optional precomputed token sets so O(n^2) callers
    (find_duplicate_groups) do not re-tokenize the same text per pair.
    """
    if tokens1 is None:
        tokens1 = _tokenize(norm1)
    if tokens2 is None:
        tokens2 = _tokenize(norm2)

    len1 = len(norm1)
    len2 = len(norm2)

    # If either string is too long, the character DP is too expensive; fall
    # back entirely to token-based similarity.
    too_long = len1 > MAX_LEVENSHTEIN_LEN or len2 > MAX_LEVENSHTEIN_LEN

    # Detect a large length mismatch (e.g. short query vs long description).
    longer = max(len1, len2)
    shorter = min(len1, len2)
    length_mismatch = shorter > 0 and (longer / shorter) > LENGTH_RATIO_THRESHOLD

    if too_long or length_mismatch:
        # Token-based path: robust to length differences and cheap to compute.
        return _token_similarity_sets(tokens1, tokens2)

    # Use pure character Levenshtein only when BOTH strings are short and of
    # comparable length (the original short-text fast path).
    if len1 < 20 and len2 < 20:
        return _normalized_levenshtein_similarity(norm1, norm2)

    # For longer (but still capped) texts of comparable length, combine
    # Jaccard with character-level similarity for better accuracy.
    union = len(tokens1 | tokens2)
    jaccard = len(tokens1 & tokens2) / union if union else 0.0
    lev = _normalized_levenshtein_similarity(norm1, norm2)

    # Weighted combination: favor Jaccard for longer texts
    # but still consider character-level similarity.
    return 0.7 * jaccard + 0.3 * lev


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts.

    Uses a combination of Levenshtein distance for short texts and
    Jaccard similarity for longer texts to provide robust similarity scoring.

    Pure character-level Levenshtein is only used when BOTH strings are short
    and of comparable length. When either string is long (exceeds
    ``MAX_LEVENSHTEIN_LEN``) or the two strings differ greatly in length, the
    full character DP is skipped and token-based (Jaccard / overlap) similarity
    is used instead. This keeps the comparison fast (avoids the O(n*m) DP on
    long inputs) and avoids the "short query vs long description scores ~0"
    failure mode.

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
        # No token signal survives normalization (e.g. all-punctuation
        # strings): only literal equality counts as similar — "???" and "!!!"
        # are not duplicates of each other.
        return 1.0 if text1.strip() == text2.strip() else 0.0
    if not norm1 or not norm2:
        return 0.0

    return _similarity_from_normalized(norm1, norm2)


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
    query: str, issues: list[Issue], threshold: float = 0.6
) -> list[tuple[Issue, float]]:
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
    issues: list[Issue], threshold: float = 0.7
) -> list[list[tuple[Issue, float]]]:
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

    # Normalize and tokenize each issue ONCE up front: the pairwise loop below
    # is O(n^2) and used to redo this text processing for every single pair.
    raw_texts = [_combine_issue_text(issue).strip() for issue in sorted_issues]
    norm_texts = [_normalize_text(text) for text in raw_texts]
    token_sets = [_tokenize(norm) for norm in norm_texts]

    def _pair_similarity(a: int, b: int) -> float:
        if not norm_texts[a] and not norm_texts[b]:
            return 1.0 if raw_texts[a] == raw_texts[b] else 0.0
        if not norm_texts[a] or not norm_texts[b]:
            return 0.0
        return _similarity_from_normalized(
            norm_texts[a], norm_texts[b], token_sets[a], token_sets[b]
        )

    for i, primary_issue in enumerate(sorted_issues):
        # Skip if this issue is already in a group
        if primary_issue.id in grouped_ids:
            continue

        group = [(primary_issue, 1.0)]  # Primary has 100% similarity to itself

        # Compare with remaining issues
        for j in range(i + 1, len(sorted_issues)):
            other_issue = sorted_issues[j]
            # Skip if already grouped
            if other_issue.id in grouped_ids:
                continue

            similarity = _pair_similarity(i, j)

            # If above threshold, add to group
            if similarity >= threshold:
                group.append((other_issue, similarity))
                grouped_ids.add(other_issue.id)

        # Only add groups with duplicates (more than just the primary)
        if len(group) > 1:
            grouped_ids.add(primary_issue.id)
            duplicate_groups.append(group)

    return duplicate_groups
