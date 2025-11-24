# IssueDB

A command-line issue tracking system for software development projects. IssueDB provides a simple yet concrete way to manage issues, bugs, and tasks directly from your terminal.

## Features

- **Simple Issue Management**: Create, update, delete, and list issues
- **Bulk Operations**: Update multiple issues at once with filters
- **Project-based Organization**: Group issues by project
- **Priority Levels**: Categorize issues as low, medium, high, or critical
- **Status Tracking**: Track issues through open, in-progress, and closed states
- **FIFO Queue Management**: Get the next issue to work on based on priority and creation date
- **Full-text Search**: Search issues by keyword in title and description
- **Summary & Reports**: Aggregate statistics and detailed breakdowns by status/priority
- **Audit Logging**: Complete immutable history of all changes
- **JSON Output**: Machine-readable output for scripting and automation
- **LLM Agent Integration**: Built-in prompt for programmatic usage
- **Natural Language Interface**: Ollama integration for conversational issue management
- **Local Storage**: SQLite database stored locally with no external dependencies
- **Zero Dependencies**: Uses only Python standard library

## Installation

### From PyPI (when published)

```bash
pip install issuedb
```

### From Source

```bash
git clone https://github.com/rodmena-limited/issue-queue
cd issuedb
pip install -e .
```

## Quick Start

### Create your first issue

```bash
issuedb-cli create --title "Fix login bug" --project MyApp --description "Users cannot log in with special characters" --priority high
```

### List all open issues

```bash
issuedb-cli list --status open
```

### Get the next issue to work on

```bash
issuedb-cli get-next --project MyApp
```

## Usage

### Creating Issues

Create a new issue with required title and project:

```bash
issuedb-cli create -t "Add user authentication" -p WebApp
```

With additional details:

```bash
issuedb-cli create \
  --title "Implement OAuth2" \
  --project WebApp \
  --description "Add Google and GitHub OAuth providers" \
  --priority high \
  --status open
```

### Listing Issues

List all issues:

```bash
issuedb-cli list
```

Filter by project:

```bash
issuedb-cli list --project WebApp
```

Filter by status and priority:

```bash
issuedb-cli list --status open --priority high
```

Limit results:

```bash
issuedb-cli list --limit 10
```

### Getting Issue Details

View a specific issue:

```bash
issuedb-cli get 42
```

### Updating Issues

Update issue status:

```bash
issuedb-cli update 42 --status in-progress
```

Update multiple fields:

```bash
issuedb-cli update 42 \
  --title "Updated title" \
  --priority critical \
  --status in-progress
```

### Deleting Issues

Delete an issue (with audit trail preserved):

```bash
issuedb-cli delete 42
```

### Getting Next Issue

Get the highest priority oldest issue:

```bash
issuedb-cli get-next
```

For a specific project:

```bash
issuedb-cli get-next --project WebApp
```

### Searching Issues

Search by keyword:

```bash
issuedb-cli search --keyword "login" --project WebApp
```

### Clearing Project Issues

Clear all issues for a project (requires confirmation):

```bash
issuedb-cli clear --project OldProject --confirm
```

### Viewing Audit Logs

View all changes for an issue:

```bash
issuedb-cli audit --issue 42
```

View all changes in a project:

```bash
issuedb-cli audit --project WebApp
```

### Database Information

Get database statistics:

```bash
issuedb-cli info
```

### Summary Statistics

Get aggregate statistics of all issues:

```bash
issuedb-cli summary
```

Get summary for a specific project:

```bash
issuedb-cli summary --project MyApp
```

Summary shows:
- Total issue count
- Count by status (open, in-progress, closed)
- Count by priority (low, medium, high, critical)
- Percentage breakdowns

### Detailed Report

Get a detailed report grouped by status:

```bash
issuedb-cli report
```

Get report for a specific project grouped by priority:

```bash
issuedb-cli report --project Backend --group-by priority
```

Reports include:
- Full issue details grouped by status or priority
- Count for each group
- Total issues

## JSON Output

All commands support JSON output for scripting and automation:

```bash
issuedb-cli list --project WebApp --json | jq '.[].title'
```

```bash
issuedb-cli get-next --json | jq '.id'
```

## Command Reference

### Commands

- `create` - Create a new issue
- `list` - List issues with optional filters
- `get` - Get details of a specific issue
- `update` - Update issue fields
- `bulk-update` - Bulk update multiple issues
- `delete` - Delete an issue
- `get-next` - Get the next issue to work on
- `search` - Search issues by keyword
- `clear` - Clear all issues for a project
- `audit` - View audit logs
- `info` - Get database information
- `summary` - Get summary statistics of issues
- `report` - Get detailed report of issues grouped by status or priority

### Global Options

- `--db PATH` - Use a custom database file (default: ~/.issuedb/issuedb.sqlite)
- `--json` - Output results in JSON format
- `--prompt` - Display LLM agent guide for automated usage
- `--ollama REQUEST` - Generate and execute command from natural language via Ollama
- `--ollama-model MODEL` - Ollama model to use (default: llama3)
- `--ollama-host HOST` - Ollama server host (default: localhost)
- `--ollama-port PORT` - Ollama server port (default: 11434)

### Priority Levels

- `low` - Low priority
- `medium` - Medium priority (default)
- `high` - High priority
- `critical` - Critical priority

### Status Values

- `open` - Issue is open (default)
- `in-progress` - Issue is being worked on
- `closed` - Issue is resolved

## Examples

### Example Workflow

```bash
# Create a new project's issues
issuedb-cli create -t "Setup CI/CD pipeline" -p DevOps --priority high
issuedb-cli create -t "Add unit tests" -p DevOps --priority medium
issuedb-cli create -t "Update documentation" -p DevOps --priority low

# Get the next issue to work on
issuedb-cli get-next -p DevOps

# Start working on it
issuedb-cli update 1 --status in-progress

# Complete the issue
issuedb-cli update 1 --status closed

# Check remaining open issues
issuedb-cli list -p DevOps --status open
```

### Integration with Scripts

```bash
#!/bin/bash
# Get next issue ID and mark it as in-progress
ISSUE_ID=$(issuedb-cli get-next --project MyApp --json | jq -r '.id')
if [ "$ISSUE_ID" != "null" ]; then
    echo "Working on issue $ISSUE_ID"
    issuedb-cli update $ISSUE_ID --status in-progress
fi
```

### LLM Agent Integration

IssueDB is designed to be easily used by LLM agents:

```python
import subprocess
import json

def get_next_issue(project):
    result = subprocess.run(
        ["issuedb-cli", "get-next", "--project", project, "--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout) if result.returncode == 0 else None

def create_issue(title, project, description=None, priority="medium"):
    cmd = ["issuedb-cli", "create",
           "--title", title,
           "--project", project,
           "--priority", priority,
           "--json"]
    if description:
        cmd.extend(["--description", description])

    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout) if result.returncode == 0 else None
```

### Advanced LLM Agent Integration

IssueDB provides a specialized prompt optimized for LLM agents to use the CLI directly:

```bash
# Get the LLM agent guide
issuedb-cli --prompt
```

This outputs a comprehensive guide that instructs LLM agents to:
- Output **only executable shell commands** (no markdown, no explanations)
- Use proper syntax and quoting
- Leverage JSON output for machine parsing
- Follow FIFO priority-based workflows

Example LLM agent workflow:
```python
import subprocess
import json

# Get the agent prompt to include in your LLM context
prompt = subprocess.run(["issuedb-cli", "--prompt"], capture_output=True, text=True).stdout

# Your LLM can now generate direct issuedb-cli commands
# Example: User says "Create a high priority bug for login issues"
# LLM outputs: issuedb-cli create -t "Fix login bug" -p MyApp --priority high

# Execute the command
result = subprocess.run(llm_generated_command.split(), capture_output=True, text=True)
```

The prompt ensures LLM agents generate commands that are:
- **Directly executable** without post-processing
- **Properly quoted** for shell safety
- **Machine-readable** when using --json flag
- **Priority-aware** for optimal workflow

### Natural Language Interface with Ollama

IssueDB can integrate directly with Ollama for natural language command generation:

```bash
# Use natural language to create issues
issuedb-cli --ollama "we have many junk files in the highway project and we need to fix it fast"

# Get the next task to work on
issuedb-cli --ollama "what should I work on next for the backend project?"

# Search for issues
issuedb-cli --ollama "find all critical bugs in the frontend"

# Update issues
issuedb-cli --ollama "mark issue 42 as completed"
```

#### Setup

1. Install and start Ollama:
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model (e.g., llama3, mistral, codellama)
ollama pull llama3

# Start Ollama server
ollama serve
```

2. Use issuedb-cli with natural language:
```bash
issuedb-cli --ollama "create a critical bug for login failures in the auth service"
```

#### Configuration

Configure Ollama connection via command-line flags or environment variables:

```bash
# Command-line flags
issuedb-cli --ollama "your request" \
  --ollama-model mistral \
  --ollama-host localhost \
  --ollama-port 11434

# Environment variables
export OLLAMA_HOST=localhost
export OLLAMA_PORT=11434
export OLLAMA_MODEL=llama3

issuedb-cli --ollama "your request"
```

Default values:
- **Model**: `llama3` (or from `OLLAMA_MODEL` env)
- **Host**: `localhost` (or from `OLLAMA_HOST` env)
- **Port**: `11434` (or from `OLLAMA_PORT` env)

#### How It Works

1. Ollama receives your natural language request
2. The agent prompt guides the LLM to generate a valid issuedb-cli command
3. The command is automatically validated and executed
4. Results are displayed in your terminal

The integration uses only Python standard library (urllib), keeping the package dependency-free.

## Database

IssueDB uses a local SQLite database stored at `~/.issuedb/issuedb.sqlite`. The database includes:

- **issues** table - Stores all issue data
- **audit_logs** table - Immutable audit trail of all changes
- Comprehensive indexes for optimal query performance

The database is automatically created on first use.

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=issuedb
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/issuedb
cd issuedb

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
pip install pytest pytest-cov ruff
```

### Code Formatting and Linting

```bash
# Format code
ruff format .

# Check linting
ruff check .
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_repository.py

# Run with verbose output
pytest -v
```

## License

Apache License 2.0 - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Roadmap

- [ ] Export/import functionality
- [ ] Issue templates
- [ ] Tags/labels support
- [ ] Due dates
- [ ] Issue relationships (blocks, depends on)
- [ ] Statistics and reporting
- [ ] Web UI (optional)
- [ ] Backup and restore utilities
