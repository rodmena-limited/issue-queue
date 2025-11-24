# IssueDB

A command-line issue tracking system for software development projects. IssueDB provides a simple yet concrete way to manage issues, bugs, and tasks directly from your terminal.

## Features

- **Simple Issue Management**: Create, update, delete, and list issues
- **Project-based Organization**: Group issues by project
- **Priority Levels**: Categorize issues as low, medium, high, or critical
- **Status Tracking**: Track issues through open, in-progress, and closed states
- **FIFO Queue Management**: Get the next issue to work on based on priority and creation date
- **Full-text Search**: Search issues by keyword in title and description
- **Audit Logging**: Complete immutable history of all changes
- **JSON Output**: Machine-readable output for scripting and automation
- **Local Storage**: SQLite database stored locally with no external dependencies

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
- `delete` - Delete an issue
- `get-next` - Get the next issue to work on
- `search` - Search issues by keyword
- `clear` - Clear all issues for a project
- `audit` - View audit logs
- `info` - Get database information

### Global Options

- `--db PATH` - Use a custom database file (default: ~/.issuedb/issuedb.sqlite)
- `--json` - Output results in JSON format

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

MIT License - See LICENSE file for details

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
