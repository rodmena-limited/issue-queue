"""Git utilities for issue linking and integration."""

import re
import subprocess
from typing import Any, List, Optional, Set


class GitError(Exception):
    """Raised when git operations fail."""

    pass


def _is_safe_ref(ref: str) -> bool:
    """Return True if a user-supplied git ref/branch is safe to pass to git.

    A value beginning with ``-`` could be interpreted by git as an option/flag
    (argument injection), so such values are rejected even when a ``--``
    separator is used (some git subcommands take the ref as the value of a flag
    such as ``--contains`` where ``--`` does not protect it).

    Args:
        ref: User-supplied commit hash or branch name.

    Returns:
        True if the ref is safe to use, False otherwise.
    """
    return bool(ref) and not ref.startswith("-")


def is_git_repo(path: Optional[str] = None) -> bool:
    """Check if the current directory (or given path) is a git repository.

    Args:
        path: Optional path to check. Defaults to current directory.

    Returns:
        True if the path is inside a git repository, False otherwise.
    """
    try:
        cmd = ["git", "rev-parse", "--is-inside-work-tree"]
        cwd = path or None

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # git not installed, or git did not respond in time
        return False


def get_current_branch(path: Optional[str] = None) -> Optional[str]:
    """Get the current git branch name.

    Args:
        path: Optional path to git repository. Defaults to current directory.

    Returns:
        Current branch name, or None if not in a git repository.

    Raises:
        GitError: If git command fails.
    """
    if not is_git_repo(path):
        return None

    try:
        cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        cwd = path or None

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired as e:
        raise GitError("Timed out getting current branch") from e
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get current branch: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def get_recent_commits(n: int = 10, path: Optional[str] = None) -> List[dict[str, Any]]:
    """Get recent commit hashes and messages.

    Args:
        n: Number of recent commits to retrieve (default: 10).
        path: Optional path to git repository. Defaults to current directory.

    Returns:
        List of dictionaries containing commit hash and message.
        Each dict has keys: 'hash', 'message', 'author', 'date'.

    Raises:
        GitError: If git command fails or not in a git repository.
        ValueError: If ``n`` is not a positive integer.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise ValueError("n must be a positive integer")

    if not is_git_repo(path):
        raise GitError("Not in a git repository")

    try:
        # Format: hash|author|date|message
        cmd = [
            "git",
            "log",
            f"-{n}",
            "--pretty=format:%H|%an|%ai|%s",
        ]
        cwd = path or None

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3],
                        }
                    )

        return commits
    except subprocess.TimeoutExpired as e:
        raise GitError("Timed out getting recent commits") from e
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get recent commits: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def parse_issue_refs(message: str) -> Set[int]:
    """Extract issue references from a commit message.

    Supports patterns like:
    - #123
    - fixes #123
    - closes #123
    - resolves #123
    - fix #123
    - close #123
    - resolve #123

    Args:
        message: Commit message to parse.

    Returns:
        Set of issue IDs referenced in the message.
    """
    # Pattern to match issue references
    # Matches: #123, fix #123, fixes #123, close #123, closes #123, etc.
    # Note: fix(?:es)? matches "fix" or "fixes", close(?:s)? matches "close" or "closes"
    pattern = r"(?:fix(?:es)?|close(?:s)?|resolve(?:s)?)\s+#(\d+)|#(\d+)"

    matches = re.finditer(pattern, message, re.IGNORECASE)
    issue_ids = set()

    for match in matches:
        # match.group(1) is for "fix #123" pattern
        # match.group(2) is for "#123" pattern
        issue_id = match.group(1) or match.group(2)
        if issue_id:
            issue_ids.add(int(issue_id))

    return issue_ids


def parse_close_refs(message: str) -> Set[int]:
    """Extract issue references that should auto-close from a commit message.

    Only matches patterns that indicate closing:
    - fixes #123
    - closes #123
    - resolves #123
    - fix #123
    - close #123
    - resolve #123

    Args:
        message: Commit message to parse.

    Returns:
        Set of issue IDs that should be closed based on the message.
    """
    # Pattern to match only closing keywords
    # Note: fix(?:es)? matches "fix" or "fixes", close(?:s)? matches "close" or "closes"
    pattern = r"(?:fix(?:es)?|close(?:s)?|resolve(?:s)?)\s+#(\d+)"

    matches = re.finditer(pattern, message, re.IGNORECASE)
    issue_ids = set()

    for match in matches:
        issue_id = match.group(1)
        if issue_id:
            issue_ids.add(int(issue_id))

    return issue_ids


def get_commit_message(commit_hash: str, path: Optional[str] = None) -> Optional[str]:
    """Get the commit message for a given commit hash.

    Args:
        commit_hash: Git commit hash (full or abbreviated).
        path: Optional path to git repository. Defaults to current directory.

    Returns:
        Commit message, or None if commit not found.

    Raises:
        GitError: If git command fails or not in a git repository.
    """
    if not is_git_repo(path):
        raise GitError("Not in a git repository")

    if not _is_safe_ref(commit_hash):
        # A ref starting with '-' could be parsed as a git option.
        return None

    try:
        cmd = ["git", "log", "-1", "--pretty=format:%B", "--", commit_hash]
        cwd = path or None

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
        )

        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def validate_commit_hash(commit_hash: str, path: Optional[str] = None) -> bool:
    """Validate that a commit hash exists in the repository.

    Args:
        commit_hash: Git commit hash to validate.
        path: Optional path to git repository. Defaults to current directory.

    Returns:
        True if the commit exists, False otherwise.
    """
    if not is_git_repo(path):
        return False

    if not _is_safe_ref(commit_hash):
        # A ref starting with '-' could be parsed as a git option.
        return False

    try:
        cmd = ["git", "cat-file", "-t", "--", commit_hash]
        cwd = path or None

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )

        return result.returncode == 0 and result.stdout.strip() == "commit"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_branches_containing_commit(commit_hash: str, path: Optional[str] = None) -> List[str]:
    """Get list of branches that contain the given commit.

    Args:
        commit_hash: Git commit hash.
        path: Optional path to git repository. Defaults to current directory.

    Returns:
        List of branch names containing the commit.

    Raises:
        GitError: If git command fails or not in a git repository.
    """
    if not is_git_repo(path):
        raise GitError("Not in a git repository")

    if not _is_safe_ref(commit_hash):
        # '--contains' takes the hash as its value, so a leading-dash hash
        # could be parsed as a git option even with a '--' separator.
        raise GitError(f"Invalid commit hash: {commit_hash!r}")

    try:
        cmd = ["git", "branch", "--contains", commit_hash, "--format=%(refname:short)"]
        cwd = path or None

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
        )

        branches = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return branches
    except subprocess.TimeoutExpired as e:
        raise GitError("Timed out getting branches containing commit") from e
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get branches containing commit: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e
