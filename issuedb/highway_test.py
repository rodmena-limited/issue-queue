"""Highway test entrypoint for issuedb package."""

import os
import tempfile
from typing import Any


def test_issuedb(ctx: Any) -> dict[str, Any]:
    """Test issuedb package functionality."""
    results: dict[str, Any] = {"tests_passed": [], "tests_failed": []}

    # Test 1: Import models
    try:
        from issuedb.models import Issue, Priority, Status
        results["tests_passed"].append("import_models")
    except Exception as e:
        results["tests_failed"].append(f"import_models: {e}")
        results["success"] = False
        return results

    # Test 2: Import repository
    try:
        from issuedb.repository import IssueRepository
        results["tests_passed"].append("import_repository")
    except Exception as e:
        results["tests_failed"].append(f"import_repository: {e}")
        results["success"] = False
        return results

    # Test 3: Create temp database and repository
    try:
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        repo = IssueRepository(db_path)
        results["tests_passed"].append("create_repository")

        # Test 4: Create an issue (correct API)
        issue = Issue(
            title="Test Issue from Highway",
            description="Created via tools.python.run",
            priority=Priority.MEDIUM,
            status=Status.OPEN
        )
        created = repo.create_issue(issue)
        results["tests_passed"].append("create_issue")
        results["issue_id"] = created.id

        # Test 5: List issues
        issues = repo.list_issues()
        results["tests_passed"].append("list_issues")
        results["issue_count"] = len(issues)

        # Cleanup
        os.unlink(db_path)

    except Exception as e:
        results["tests_failed"].append(f"repository_ops: {e}")

    # Store results in ctx
    ctx.set_variable("issuedb_test_passed", len(results["tests_failed"]) == 0)
    ctx.set_variable("tests_passed_count", len(results["tests_passed"]))

    results["success"] = len(results["tests_failed"]) == 0
    return results
