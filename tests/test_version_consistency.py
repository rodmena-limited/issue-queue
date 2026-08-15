"""The declared version must agree wherever it is declared.

issuedb shipped with pyproject.toml at 2.12.0 and issuedb/__init__.py at
2.11.0 — a package whose installed metadata and its own ``__version__``
disagreed, so a bug report quoting one of them named a release that did not
contain the code being reported. Nothing errors when these drift, which is
why it survived a release; hence a test rather than a convention.
"""

from __future__ import annotations

import pathlib
import re

import issuedb

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _declared(path: pathlib.Path, pattern: str) -> str | None:
    """Return the version a file declares, or None if the file is absent."""
    if not path.exists():
        return None
    match = re.search(pattern, path.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def test_pyproject_matches_package_dunder_version():
    pyproject = _declared(REPO_ROOT / "pyproject.toml", r'^version = "([^"]+)"')

    # The control: if the pattern stops matching, this test would otherwise
    # compare None against None and pass while checking nothing.
    assert pyproject is not None, "could not read version from pyproject.toml"
    assert issuedb.__version__ == pyproject


def test_docs_release_matches_package_version():
    release = _declared(REPO_ROOT / "docs" / "conf.py", r'^release = "([^"]+)"')
    if release is None:
        return  # docs are optional; absence is not a mismatch
    assert issuedb.__version__ == release
