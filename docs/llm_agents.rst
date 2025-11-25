LLM Agent Integration
=====================

IssueDB is designed to work seamlessly with LLM (Large Language Model) agents. This guide covers how to integrate IssueDB with AI assistants, automation tools, and natural language interfaces.

Overview
--------

IssueDB provides several features for LLM integration:

1. **JSON output**: Machine-readable output for all commands
2. **Built-in prompt**: Comprehensive agent guide accessible via ``--prompt``
3. **Natural language interface**: Ollama integration for conversational commands
4. **Predictable CLI**: Consistent, parseable command structure

Built-in Agent Prompt
---------------------

Access the LLM agent prompt guide:

.. code-block:: bash

   issuedb-cli --prompt

This outputs a comprehensive guide that can be included in an LLM's system prompt. It includes:

- Critical rules for output format
- Complete command reference
- Example interactions
- Quoting rules

Using the Prompt
~~~~~~~~~~~~~~~~

For LLM agents (like Claude, GPT, etc.), include the prompt in the system instructions:

.. code-block:: text

   You are an AI assistant that can manage issues using issuedb-cli.

   [Include output of: issuedb-cli --prompt]

The agent will then output executable shell commands.

Ollama Integration
------------------

IssueDB includes native Ollama integration for natural language commands.

**Setup:**

1. Install Ollama: https://ollama.ai
2. Pull a model: ``ollama pull llama3.2``
3. Use the ``--ollama`` flag

**Usage:**

.. code-block:: bash

   # Natural language commands
   issuedb-cli --ollama "create a high priority bug about login issues"
   issuedb-cli --ollama "show me all open critical issues"
   issuedb-cli --ollama "close issue 5 with a comment saying it's fixed"

**Configuration:**

Environment variables:

.. code-block:: bash

   export OLLAMA_MODEL=llama3.2
   export OLLAMA_HOST=localhost
   export OLLAMA_PORT=11434

Or command-line options:

.. code-block:: bash

   issuedb-cli --ollama "create an issue" --ollama-model codellama --ollama-host 192.168.1.100 --ollama-port 11434

JSON Output for Automation
--------------------------

All commands support ``--json`` for machine-readable output:

.. code-block:: bash

   # List issues as JSON
   issuedb-cli --json list

   # Create issue and get JSON response
   issuedb-cli --json create -t "New issue" --priority high

   # Get structured data for processing
   issuedb-cli --json summary

**Parsing JSON in scripts:**

.. code-block:: bash

   # Using jq
   OPEN_COUNT=$(issuedb-cli --json summary | jq '.by_status.open.count')

   # Using Python
   python -c "
   import json, subprocess
   result = subprocess.run(['issuedb-cli', '--json', 'list'], capture_output=True, text=True)
   issues = json.loads(result.stdout)
   print(f'Found {len(issues)} issues')
   "

Agent Command Patterns
----------------------

Common patterns for LLM agents:

Creating Issues
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Basic creation
   issuedb-cli create -t "Fix bug in login" --priority high

   # With description
   issuedb-cli create -t "Add dark mode" -d "Users want a dark theme option" --priority medium

Querying Issues
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Get next issue to work on
   issuedb-cli --json get-next

   # Get the last issue fetched (useful for context continuity)
   issuedb-cli --json get-last

   # Get last 5 fetched issues
   issuedb-cli --json get-last -n 5

   # Search for specific issues
   issuedb-cli --json search -k "authentication"

   # Get summary
   issuedb-cli --json summary

Updating Issues
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Update status
   issuedb-cli update 1 -s in-progress

   # Close with comment
   issuedb-cli update 1 -s closed && issuedb-cli comment 1 -t "Fixed in PR #123"

Bulk Operations
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Bulk create from JSON
   echo '[{"title": "Issue 1"}, {"title": "Issue 2"}]' | issuedb-cli --json bulk-create

   # Bulk close
   echo '[1, 2, 3]' | issuedb-cli --json bulk-close

Example: Claude Code Integration
--------------------------------

When using IssueDB with Claude Code or similar assistants:

**System prompt addition:**

.. code-block:: text

   You can manage project issues using the issuedb-cli tool.

   Key commands:
   - issuedb-cli create -t "TITLE" [--priority PRIORITY]
   - issuedb-cli list [--status STATUS]
   - issuedb-cli update ID -s STATUS
   - issuedb-cli comment ID -t "COMMENT"
   - issuedb-cli --json COMMAND (for machine-readable output)

   Always use --json for output you need to parse.
   Priorities: low, medium, high, critical
   Statuses: open, in-progress, closed

**Example interaction:**

.. code-block:: text

   User: Create an issue for the login bug we discussed

   Agent: I'll create a high-priority issue for the login bug.

   $ issuedb-cli --json create -t "Fix login bug with special characters" \
       -d "Users cannot log in when password contains special characters" \
       --priority high

Example: GitHub Actions
-----------------------

Using IssueDB in CI/CD:

.. code-block:: yaml

   name: Issue Management

   on:
     workflow_dispatch:
       inputs:
         action:
           description: 'Action to perform'
           required: true
           type: choice
           options:
             - create
             - close-completed

   jobs:
     manage-issues:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - name: Set up Python
           uses: actions/setup-python@v4
           with:
             python-version: '3.11'

         - name: Install IssueDB
           run: pip install issuedb

         - name: Create Issue
           if: github.event.inputs.action == 'create'
           run: |
             issuedb-cli create -t "Automated issue from CI" \
               -d "Created by GitHub Actions" \
               --priority medium

         - name: Close Completed Issues
           if: github.event.inputs.action == 'close-completed'
           run: |
             issuedb-cli bulk-update --filter-status in-progress -s closed

Example: Python Script Integration
----------------------------------

Using IssueDB from Python:

.. code-block:: python

   import json
   import subprocess
   from typing import List, Dict, Any

   def run_issuedb(args: List[str]) -> Dict[str, Any]:
       """Run issuedb-cli command and return JSON result."""
       result = subprocess.run(
           ['issuedb-cli', '--json'] + args,
           capture_output=True,
           text=True,
           check=True
       )
       return json.loads(result.stdout)

   def create_issue(title: str, priority: str = 'medium', description: str = None) -> Dict:
       """Create a new issue."""
       args = ['create', '-t', title, '--priority', priority]
       if description:
           args.extend(['-d', description])
       return run_issuedb(args)

   def get_open_issues() -> List[Dict]:
       """Get all open issues."""
       return run_issuedb(['list', '-s', 'open'])

   def close_issue(issue_id: int, comment: str = None) -> Dict:
       """Close an issue with optional comment."""
       run_issuedb(['update', str(issue_id), '-s', 'closed'])
       if comment:
           return run_issuedb(['comment', str(issue_id), '-t', comment])
       return run_issuedb(['get', str(issue_id)])

   # Usage
   if __name__ == '__main__':
       # Create an issue
       issue = create_issue("Test from Python", priority="high")
       print(f"Created issue #{issue['id']}")

       # List open issues
       open_issues = get_open_issues()
       print(f"Found {len(open_issues)} open issues")

       # Close with comment
       close_issue(issue['id'], "Closed from Python script")

Best Practices
--------------

1. **Always use --json**: For programmatic access, always use JSON output
2. **Check exit codes**: Non-zero exit code indicates an error
3. **Parse errors from stderr**: Error messages go to stderr, not stdout
4. **Use bulk operations**: For multiple issues, use bulk commands for efficiency
5. **Include the prompt**: For LLM agents, include the full ``--prompt`` output
6. **Test commands**: Verify commands work before automating

Troubleshooting
---------------

**Command not found:**

Ensure IssueDB is installed and in PATH:

.. code-block:: bash

   pip install issuedb
   which issuedb-cli

**JSON parsing errors:**

Ensure you're capturing stdout only:

.. code-block:: bash

   # Correct
   OUTPUT=$(issuedb-cli --json list 2>/dev/null)

   # Parse only if successful
   if [ $? -eq 0 ]; then
       echo "$OUTPUT" | jq '.'
   fi

**Ollama not responding:**

Check Ollama is running:

.. code-block:: bash

   curl http://localhost:11434/api/tags
