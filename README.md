# IssueDB

A command-line issue tracking system for software development projects. IssueDB provides a simple yet concrete way to manage issues, bugs, and tasks directly from your terminal with a **per-directory database model** - each directory gets its own issue database.

--------------------
# Quick Start:

```bash
pip install issuedb
```
then in your [CLAUDE/QWEN/GEMINI].md
```markdown
STRICT RULES:
- You need to use issuedb as issue tracker.
- Every request, feature, bugfix must have a ticket.
- run `issuedb-cli --prompt` to learn how to use it.
```
That's it!
--------------------


## Features

### Core Features
- **Per-Directory Databases**: Each directory has its own `issuedb.sqlite` - your issues live where your code lives
- **Simple Issue Management**: Create, update, delete, and list issues
- **Bulk Operations**: Update multiple issues at once with filters, patterns, or JSON input
- **Priority Levels**: Categorize issues as low, medium, high, or critical
- **Status Tracking**: Track issues through open, in-progress, and closed states
- **FIFO Queue Management**: Get the next issue to work on based on priority and creation date
- **Full-text Search**: Search issues by keyword in title and description
- **Comments**: Add notes and progress updates to issues

### Advanced Features
- **Issue Dependencies**: Block issues on other issues, track dependency graphs
- **Code References**: Link issues to specific files and line numbers in your codebase
- **Time Tracking**: Start/stop timers, set estimates, generate time reports
- **Workspace Awareness**: Track active issues, git branch integration
- **Duplicate Detection**: Find similar issues before creating duplicates
- **Issue Templates**: Create issues from predefined templates (bug, feature, task)
- **Issue Context**: Get comprehensive context for LLM agents

### Web Interface
- **Web UI**: Clean, premium web interface for issue management
- **Dashboard**: Summary statistics, priority breakdown, active issues
- **Issue Browser**: Filter and search issues with status/priority badges
- **API Endpoints**: Full REST API for programmatic access

![Issue Detail Full](docs/screenshots/issue-detail-full.png)
*Complete issue detail with context, git integration, comments, and audit history*

![Dashboard](docs/screenshots/dashboard.png)
*Dashboard with statistics, priority breakdown, and active issue tracking*

![Issues List](docs/screenshots/issues-list.png)
*Issues list with filtering and search*

![Create Issue](docs/screenshots/create-issue.png)
*Create new issue form*

![Issue Detail](docs/screenshots/issue-detail.png)
*Issue detail with async-loaded comments, similar issues, dependencies, and audit history*

![Audit Log](docs/screenshots/audit-log.png)
*Complete audit log of all changes*

### Reporting & Integration
- **Summary & Reports**: Aggregate statistics and detailed breakdowns by status/priority
- **Audit Logging**: Complete immutable history of all changes
- **JSON Output**: Machine-readable output for scripting and automation
- **LLM Agent Integration**: Built-in prompt for programmatic usage
- **Natural Language Interface**: Ollama integration for conversational issue management
- **Local Storage**: SQLite database with no external dependencies
- **Minimal Dependencies**: Core functionality uses only Python standard library (Flask optional for web UI)

## Per-Directory Project Model

IssueDB v2.0 uses a **per-directory model** where each directory has its own `issuedb.sqlite` database:

```
my-workspace/
├── frontend/
│   ├── src/
│   ├── issuedb.sqlite      # Frontend issues
│   └── README.md
├── backend/
│   ├── api/
│   ├── issuedb.sqlite      # Backend issues
│   └── README.md
└── docs/
    ├── guides/
    └── issuedb.sqlite          # Documentation issues
```

### Benefits

- **Better isolation**: Each project/directory has its own independent database
- **Simpler mental model**: Your issues are where your code is
- **Easier backup**: Just backup the directory to preserve all issues
- **Natural organization**: Filesystem directories already organize projects
- **Git-friendly**: Database file can be .gitignored or committed per project needs

### Working with Multiple Projects

```bash
# Work on frontend issues
cd ~/workspace/frontend
issuedb-cli create -t "Fix navbar bug"
issuedb-cli list

# Switch to backend issues
cd ~/workspace/backend
issuedb-cli create -t "Add authentication"
issuedb-cli list

# Each directory maintains its own issues
```

## Installation

### From PyPI (when published)

```bash
pip install issuedb
```

### With Web UI Support

To use the web interface, install with the `web` extra:

```bash
pip install issuedb[web]
```

This installs Flask as an optional dependency for the web UI.

### From Source

```bash
git clone https://github.com/rodmena-limited/issue-queue
cd issuedb
pip install -e .

# Or with web UI support:
pip install -e ".[web]"
```

## Quick Start

### Create your first issue

```bash
cd ~/my-project
issuedb-cli create --title "Fix login bug" --description "Users cannot log in with special characters" --priority high
```

### List all open issues

```bash
issuedb-cli list --status open
```

### Get the next issue to work on

```bash
issuedb-cli get-next
```

## Usage

### Creating Issues

Create a new issue:

```bash
issuedb-cli create -t "Add user authentication"
```

With additional details:

```bash
issuedb-cli create \
  --title "Implement OAuth2" \
  --description "Add Google and GitHub OAuth providers" \
  --priority high \
  --status open
```

### Listing Issues

List all issues in current directory:

```bash
issuedb-cli list
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

### Bulk Updates

Close all open issues:

```bash
issuedb-cli bulk-update --filter-status open -s closed
```

Set all critical issues to high priority:

```bash
issuedb-cli bulk-update --filter-priority critical --priority high
```

### Bulk Operations (JSON)

Create multiple issues at once:

```bash
# From stdin
echo '[
  {"title": "Issue 1", "priority": "high", "description": "First issue"},
  {"title": "Issue 2", "priority": "medium"},
  {"title": "Issue 3"}
]' | issuedb-cli --json bulk-create

# From file
issuedb-cli --json bulk-create -f issues.json

# Inline data
issuedb-cli --json bulk-create -d '[{"title": "Quick issue", "priority": "low"}]'
```

Update multiple specific issues:

```bash
# Update different fields on different issues
echo '[
  {"id": 1, "status": "closed", "description": "Completed"},
  {"id": 2, "priority": "high", "title": "Updated title"},
  {"id": 3, "status": "in-progress"}
]' | issuedb-cli --json bulk-update-json
```

Close multiple issues by ID:

```bash
# Close issues 1, 2, 3, and 5
echo '[1, 2, 3, 5]' | issuedb-cli --json bulk-close

# Or from file
issuedb-cli --json bulk-close -f issue_ids.json
```

### Deleting Issues

Delete an issue (with audit trail preserved):

```bash
issuedb-cli delete 42
```

### Comments

Add comments to issues to track notes, resolutions, or updates:

```bash
# Add a comment to an issue
issuedb-cli comment 42 -t "Fixed by updating the configuration file"

# List all comments on an issue
issuedb-cli list-comments 42
issuedb-cli --json list-comments 42

# Delete a comment
issuedb-cli delete-comment 5
```

Common use case - close an issue with a comment:

```bash
issuedb-cli update 42 -s closed && issuedb-cli comment 42 -t "Resolved: Updated dependencies to v2.0"
```

### Getting Next Issue

Get the highest priority oldest issue:

```bash
issuedb-cli get-next
```

With status filter:

```bash
issuedb-cli get-next --status open
```

### Getting Last Fetched Issues

Track which issues were recently retrieved with `get-next`:

```bash
# Get the last issue you fetched
issuedb-cli get-last

# Get the last 5 fetched issues
issuedb-cli get-last -n 5

# JSON output for automation
issuedb-cli --json get-last -n 3
```

This feature helps you:
- Track what issues you've recently worked on
- Review fetch history even for deleted issues
- Maintain continuity when switching between tasks

### Searching Issues

Search by keyword:

```bash
issuedb-cli search --keyword "login"
```

With limit:

```bash
issuedb-cli search -k "bug" -l 5
```

### Clearing All Issues

Clear all issues in current directory (requires confirmation):

```bash
issuedb-cli clear --confirm
```

### Issue Dependencies

Track blocking relationships between issues:

```bash
# Mark issue 5 as blocked by issue 3
issuedb-cli block 5 --by 3

# Remove a specific blocker
issuedb-cli unblock 5 --by 3

# Remove all blockers from an issue
issuedb-cli unblock 5

# View dependency graph for an issue
issuedb-cli deps 5

# List all blocked issues
issuedb-cli blocked
issuedb-cli --json blocked -s open
```

### Code References

Link issues to specific code locations:

```bash
# Attach a file reference
issuedb-cli attach 5 --file "src/auth.py"

# Attach with line number
issuedb-cli attach 5 --file "src/auth.py:42"

# Attach with line range and note
issuedb-cli attach 5 --file "src/auth.py:42-50" --note "Bug location"

# List references for an issue
issuedb-cli refs 5

# Find issues referencing a file
issuedb-cli affected --file "src/auth.py"

# Remove a code reference
issuedb-cli detach 5 --file "src/auth.py"
```

### Time Tracking

Track time spent on issues:

```bash
# Start a timer
issuedb-cli timer-start 5

# Check timer status
issuedb-cli timer-status

# Stop the timer
issuedb-cli timer-stop

# Set an estimate
issuedb-cli set-estimate 5 --hours 4

# View time log for an issue
issuedb-cli time-log 5

# Generate time reports
issuedb-cli time-report
issuedb-cli time-report --period week
issuedb-cli --json time-report --period month
```

### Workspace Awareness

Track your current working context:

```bash
# View workspace status (git branch, active issue, etc.)
issuedb-cli workspace

# Start working on an issue (sets active + starts timer)
issuedb-cli start 5

# Stop working (stops timer)
issuedb-cli stop

# Stop and close the issue
issuedb-cli stop --close

# View currently active issue
issuedb-cli active
```

### Duplicate Detection

Find similar issues to avoid duplicates:

```bash
# Find issues similar to a query
issuedb-cli find-similar "login bug"
issuedb-cli --json find-similar "authentication" --threshold 0.7

# Find potential duplicate groups in database
issuedb-cli find-duplicates
issuedb-cli --json find-duplicates --threshold 0.8

# Create with duplicate check
issuedb-cli create -t "Fix login" --check-duplicates
issuedb-cli create -t "Fix login" --check-duplicates --force  # Create anyway
```

### Issue Templates

Create issues from predefined templates:

```bash
# List available templates
issuedb-cli templates

# Create from template
issuedb-cli create --template bug -t "Login crash" -d "App crashes on login"
issuedb-cli create --template feature -t "Dark mode"
issuedb-cli create --template task -t "Update dependencies"
```

### Issue Context (for LLM Agents)

Get comprehensive context for an issue:

```bash
# Full context with comments, history, related issues, suggestions
issuedb-cli context 5
issuedb-cli --json context 5

# Compact context (just issue + comments)
issuedb-cli context 5 --compact
```

### Bulk Pattern Operations

Operate on issues matching patterns:

```bash
# Close issues matching a pattern (glob)
issuedb-cli bulk-close-pattern --title "*test*"

# Update issues matching a pattern
issuedb-cli bulk-update-pattern --title "*bug*" --priority high

# Delete with regex pattern (requires --confirm)
issuedb-cli bulk-delete-pattern --title "temp.*" --regex --confirm

# Preview changes with --dry-run
issuedb-cli bulk-close-pattern --title "*WIP*" --dry-run
```

### Viewing Audit Logs

View all changes for an issue:

```bash
issuedb-cli audit --issue 42
```

View all audit logs:

```bash
issuedb-cli audit
```

### Database Information

Get database statistics:

```bash
issuedb-cli info
```

### Summary Statistics

Get aggregate statistics:

```bash
issuedb-cli summary
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

Get report grouped by priority:

```bash
issuedb-cli report --group-by priority
```

Reports include:
- Full issue details grouped by status or priority
- Count for each group
- Total issues

## JSON Output

All commands support JSON output for scripting and automation:

```bash
issuedb-cli list --json | jq '.[].title'
```

```bash
issuedb-cli get-next --json | jq '.id'
```

## Command Reference

### Commands

**Issue Management:**
- `create` - Create a new issue (supports templates and duplicate check)
- `list` - List issues with optional filters
- `get` - Get details of a specific issue
- `update` - Update issue fields
- `delete` - Delete an issue
- `get-next` - Get the next issue to work on (logs to fetch history)
- `get-last` - Get the last fetched issue(s) from history
- `search` - Search issues by keyword

**Comments:**
- `comment` - Add a comment to an issue
- `list-comments` - List comments for an issue
- `delete-comment` - Delete a comment

**Dependencies:**
- `block` - Mark an issue as blocked by another
- `unblock` - Remove blocker(s) from an issue
- `deps` - Show dependency graph for an issue
- `blocked` - List all blocked issues

**Code References:**
- `attach` - Attach a code reference to an issue
- `detach` - Remove a code reference
- `refs` - List code references for an issue
- `affected` - List issues referencing a file

**Time Tracking:**
- `timer-start` - Start tracking time on an issue
- `timer-stop` - Stop the active timer
- `timer-status` - Show active timers
- `set-estimate` - Set time estimate for an issue
- `time-log` - View time entries for an issue
- `time-report` - Generate time reports

**Workspace:**
- `workspace` - Show workspace status
- `start` - Start working on an issue
- `stop` - Stop working on active issue
- `active` - Show currently active issue
- `context` - Get full context for an issue (for LLM agents)

**Duplicate Detection:**
- `find-similar` - Find issues similar to given text
- `find-duplicates` - Find potential duplicate groups

**Templates:**
- `templates` - List available issue templates

**Bulk Operations:**
- `bulk-update` - Bulk update by filter
- `bulk-create` - Create multiple issues from JSON
- `bulk-update-json` - Update specific issues from JSON
- `bulk-close` - Close multiple issues by ID
- `bulk-close-pattern` - Close issues matching pattern
- `bulk-update-pattern` - Update issues matching pattern
- `bulk-delete-pattern` - Delete issues matching pattern

**Reporting:**
- `summary` - Get summary statistics
- `report` - Get detailed report
- `info` - Get database information
- `audit` - View audit logs

**Administrative:**
- `clear` - Clear all issues
- `web` - Start the web UI server

### Global Options

- `--db PATH` - Use a custom database file (default: ./issuedb.sqlite)
- `--json` - Output results in JSON format
- `--prompt` - Display LLM agent guide for automated usage
- `--ollama REQUEST...` - Generate and execute command from natural language via Ollama (no quotes needed, must be last flag)
- `--ollama-model MODEL` - Ollama model to use (default: llama3) - must come before --ollama
- `--ollama-host HOST` - Ollama server host (default: localhost) - must come before --ollama
- `--ollama-port PORT` - Ollama server port (default: 11434) - must come before --ollama

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
# Navigate to your project
cd ~/my-project

# Create some issues
issuedb-cli create -t "Setup CI/CD pipeline" --priority high
issuedb-cli create -t "Add unit tests" --priority medium
issuedb-cli create -t "Update documentation" --priority low

# Get the next issue to work on
issuedb-cli get-next

# Start working on it
issuedb-cli update 1 --status in-progress

# Complete the issue
issuedb-cli update 1 --status closed

# Check remaining open issues
issuedb-cli list --status open
```

### Multi-Project Workflow

```bash
# Work on frontend
cd ~/projects/frontend
issuedb-cli create -t "Fix navbar styling"
issuedb-cli list

# Work on backend
cd ~/projects/backend
issuedb-cli create -t "Add authentication endpoint"
issuedb-cli list

# Each project maintains its own issues
```

### Integration with Scripts

```bash
#!/bin/bash
# Get next issue ID and mark it as in-progress
cd ~/my-project
ISSUE_ID=$(issuedb-cli get-next --json | jq -r '.id')
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
import os

def get_next_issue(project_dir):
    os.chdir(project_dir)
    result = subprocess.run(
        ["issuedb-cli", "get-next", "--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout) if result.returncode == 0 else None

def create_issue(project_dir, title, description=None, priority="medium"):
    os.chdir(project_dir)
    cmd = ["issuedb-cli", "create",
           "--title", title,
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
import os

# Get the agent prompt to include in your LLM context
prompt = subprocess.run(["issuedb-cli", "--prompt"], capture_output=True, text=True).stdout

# Your LLM can now generate direct issuedb-cli commands
# Example: User says "Create a high priority bug for login issues"
# LLM outputs: issuedb-cli create -t "Fix login bug" --priority high

# Execute the command in the correct directory
os.chdir("~/my-project")
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
# Use natural language to create issues (no quotes needed!)
issuedb-cli --ollama we have many junk files and we need to fix it fast

# Get the next task to work on
issuedb-cli --ollama what should I work on next

# Search for issues
issuedb-cli --ollama find all critical bugs

# Update issues
issuedb-cli --ollama mark issue 42 as completed

# With custom model (model flag must come BEFORE --ollama)
issuedb-cli --ollama-model mistral --ollama create a high priority bug for login
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
cd ~/my-project
issuedb-cli --ollama create a critical bug for login failures
```

#### Configuration

Configure Ollama connection via command-line flags or environment variables:

```bash
# Command-line flags (--ollama must be LAST)
issuedb-cli --ollama-model mistral --ollama-host localhost --ollama-port 11434 --ollama your request here

# Environment variables
export OLLAMA_HOST=localhost
export OLLAMA_PORT=11434
export OLLAMA_MODEL=llama3

issuedb-cli --ollama create a bug for the payment system
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

## Web UI

IssueDB includes an optional web interface for visual issue management.

### Starting the Web Server

```bash
# Start on default port (7760)
issuedb-cli web

# Custom port and host
issuedb-cli web --port 8080 --host localhost

# Enable debug mode for development
issuedb-cli web --debug
```

### Web Features

- **Dashboard**: Overview with statistics, next issue, active issue, recent issues
- **Issues List**: Browse all issues with status/priority filters and search
- **Issue Detail**: Full issue view with comments, quick actions, dependency info
- **Create/Edit Forms**: Create and modify issues through the web interface

### API Endpoints

The web server exposes REST API endpoints:

```bash
# List all issues
curl http://localhost:7760/api/issues

# Get specific issue
curl http://localhost:7760/api/issues/5

# Create issue
curl -X POST http://localhost:7760/api/issues \
  -H "Content-Type: application/json" \
  -d '{"title": "New issue", "priority": "high"}'

# Update issue
curl -X PATCH http://localhost:7760/api/issues/5 \
  -H "Content-Type: application/json" \
  -d '{"status": "closed"}'

# Delete issue
curl -X DELETE http://localhost:7760/api/issues/5

# Get summary statistics
curl http://localhost:7760/api/summary

# Get next issue
curl http://localhost:7760/api/next

# Add comment
curl -X POST http://localhost:7760/api/issues/5/comments \
  -H "Content-Type: application/json" \
  -d '{"text": "Comment text"}'
```

### Requirements

The web UI requires Flask (installed separately):

```bash
pip install flask
```

## Database

IssueDB uses a local SQLite database stored at `./issuedb.sqlite` in the current directory. The database includes:

- **issues** table - Stores all issue data
- **audit_logs** table - Immutable audit trail of all changes
- Comprehensive indexes for optimal query performance

The database is automatically created on first use in each directory.

### Custom Database Location

You can specify a custom database path:

```bash
issuedb-cli --db ~/custom/location/issues.db create -t "Test"
```

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
git clone https://github.com/rodmena-limited/issue-queue
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

### Completed
- [x] Issue templates (bug, feature, task)
- [x] Issue relationships (blocks, depends on)
- [x] Code references (link issues to files/lines)
- [x] Time tracking (timers, estimates, reports)
- [x] Workspace awareness (active issue, git integration)
- [x] Duplicate detection (similarity search)
- [x] LLM agent context command
- [x] Bulk pattern operations

### Planned
- [ ] Export/import functionality
- [ ] Tags/labels support
- [ ] Due dates
- [x] Web UI (optional)
- [ ] Backup and restore utilities
- [ ] Git hooks integration
