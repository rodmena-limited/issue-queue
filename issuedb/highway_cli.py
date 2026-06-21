"""Highway wrapper for running issuedb CLI.

This module provides an entrypoint for running issuedb CLI
commands via Highway's tools.python.run.
"""

import io
import sys
from typing import Any


def run_cli(ctx: Any) -> dict[str, Any]:
    """Run issuedb CLI and capture output.

    Args:
        ctx: DurableContext from Highway

    Returns:
        Dict with stdout output and exit code

    Note:
        Does NOT catch exceptions - let them propagate
        so workflow fails properly on errors.
    """
    # Get args from workflow inputs
    args = ctx.get_variable("cli_args", ["--help"])

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()

    # Patch sys.argv for argparse
    old_argv = sys.argv
    sys.argv = ["issuedb-cli"] + args

    try:
        from issuedb.cli import main
        main()  # Let exceptions propagate!

        return {
            "stdout": captured.getvalue(),
            "exit_code": 0
        }
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv
# v2 - Wed 31 Dec 16:21:43 UTC 2025
