# Changelog

All notable changes to IssueDB will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2025-11-24

### Added
- **Comment System**: Add, view, and delete comments on issues
  - `comment` command: Add a comment to an issue
  - `list-comments` command: View all comments on an issue
  - `delete-comment` command: Remove a comment
  - Comments support JSON output for automation
  - Useful for tracking resolution notes, updates, or explanations when closing issues
  - Example: `issuedb-cli comment 5 -t "Fixed by updating config"`
  - Comments cascade delete with issues

### Changed
- Database schema updated with `comments` table
- Added Comment model to data models
- Enhanced LLM agent prompt with comment examples
- Updated README with comment usage documentation

### Technical Details
- Comments table with foreign key to issues (CASCADE on delete)
- Indexed by issue_id and created_at for performance
- Repository methods: `add_comment()`, `get_comments()`, `delete_comment()`
- Full type hints and mypy compliance
- 19 new tests for comment functionality (now 115 total tests)

### Fixed
- Eliminated all Python 3.12+ datetime deprecation warnings (207 warnings → 0)
  - Now explicitly convert datetime objects to ISO format strings for SQLite

## [2.1.0] - 2025-11-24

### Added
- **Bulk Create Command** (`bulk-create`): Create multiple issues at once from JSON input
  - Supports JSON input via stdin, `-f` file, or `-d` inline data
  - Full transaction support - all issues created atomically or none
  - Audit logging with `BULK_CREATE` action for each issue
  - Example: `echo '[{"title": "Issue 1", "priority": "high"}, {"title": "Issue 2"}]' | issuedb-cli --json bulk-create`

- **Bulk Update JSON Command** (`bulk-update-json`): Update multiple specific issues from JSON
  - Update any fields on specific issues by ID
  - Each update object requires `id` field plus fields to update
  - Full audit logging for each field change
  - Example: `echo '[{"id": 1, "status": "closed"}, {"id": 2, "priority": "high"}]' | issuedb-cli --json bulk-update-json`

- **Bulk Close Command** (`bulk-close`): Close multiple issues by their IDs
  - Simple array of issue IDs to close
  - Full audit logging for status changes
  - Example: `echo '[1, 2, 3, 4, 5]' | issuedb-cli --json bulk-close`

### Changed
- Updated LLM agent prompt (PROMPT.txt) with documentation for all bulk operations
- Enhanced test suite with 15 new tests for bulk operations (now 96 total tests)
- Added comprehensive type hints for all bulk operation methods

### Technical Details
- All bulk operations are transactional - either all succeed or all fail with rollback
- Repository layer methods: `bulk_create_issues()`, `bulk_update_issues_from_json()`, `bulk_close_issues()`
- Full mypy type checking compliance
- 100% test coverage for bulk operations

## [2.0.0] - 2025-11-24

### BREAKING CHANGES
- **Removed project concept**: IssueDB now uses a per-directory database model
  - Each directory has its own `./issuedb.sqlite` database file
  - No more `-p/--project` flags on any commands
  - Projects are now organized by directory structure instead of database fields
  - Migration: Use separate directories for different projects
- **Removed project field from Issue model**: Issues no longer have a project field
- **Removed project field from AuditLog model**: Audit logs no longer track project
- **Removed project filtering**: All project-based filtering has been removed from commands
  - `list`, `search`, `get-next`, `bulk-update`, `summary`, `report`, `audit`, `clear`
- **Changed clear command**: `clear` now clears all issues in the current directory's database (was `clear -p PROJECT`)
- **Changed database location**: Default database is now `./issuedb.sqlite` in current directory (was `~/.issuedb/issuedb.sqlite`)
- **Updated CLI output**: Issue display no longer shows project field

### Why This Change?
The per-directory model provides:
- **Better isolation**: Each project/directory has its own independent database
- **Simpler mental model**: Your issues are where your code is
- **Easier backup**: Just backup the directory to preserve all issues
- **Natural organization**: Filesystem directories already organize projects
- **Git-friendly**: Database file can be .gitignored or committed per project needs

### Migration Guide
**Before (v1.x):**
```bash
cd ~/my-code
issuedb-cli create -t "Fix bug" -p ProjectA
issuedb-cli list -p ProjectA
```

**After (v2.0):**
```bash
cd ~/my-code/ProjectA
issuedb-cli create -t "Fix bug"
issuedb-cli list
```

To migrate from v1.x:
1. Export issues per project (use v1.x): `issuedb-cli list -p ProjectA --json > projecta-issues.json`
2. Create project directory: `mkdir ProjectA && cd ProjectA`
3. Re-create issues in new location using v2.0

## [1.1.0] - 2025-11-24

### Added
- **Bulk Update Command**: New `bulk-update` command to update multiple issues at once
  - Filter by project, current status, or current priority
  - Set new status and/or priority for matching issues
  - Full audit trail for all bulk changes
  - Example: `issuedb-cli bulk-update -s closed` to close all issues
- **Summary Command**: New `summary` command for aggregate statistics
  - Shows total issue count
  - Breakdown by status (open, in-progress, closed) with counts and percentages
  - Breakdown by priority (low, medium, high, critical) with counts and percentages
  - Optional project filtering with `-p/--project` flag
  - JSON output support for automation
- **Report Command**: New `report` command for detailed issue reports
  - Group issues by status or priority (`--group-by` flag)
  - Includes full issue details in each group
  - Shows count for each group
  - Optional project filtering with `-p/--project` flag
  - JSON output support for automation

### Changed
- **License**: Changed from MIT to Apache-2.0
- Updated LLM agent prompt (PROMPT.txt) with bulk-update, summary, and report examples
- Enhanced README with new command documentation and examples
- Updated command reference with all new commands

### Fixed
- Ollama natural language interface now correctly handles bulk operations like "close all issues"

## [1.0.0] - 2025-11-24

### Added
- Complete CLI issue tracking system with SQLite backend
- CRUD operations for issues (create, read, update, delete)
- Project-based issue organization
- Priority levels: low, medium, high, critical
- Status tracking: open, in-progress, closed
- FIFO queue management with `get-next` command
- Full-text search across issue titles and descriptions
- Immutable audit logging for all operations
- JSON output mode for all commands (`--json` flag)
- Database information command (`info`)
- Project clearing with audit trail (`clear`)
- Comprehensive indexing for optimal query performance
- Type hints throughout the codebase
- Full test suite with 62 tests
- LLM agent integration with `--prompt` flag
- Natural language interface via Ollama integration
  - `--ollama` flag for conversational commands
  - Support for custom models, hosts, and ports
  - Environment variable configuration
  - Pure standard library HTTP client (no external dependencies)
- Complete documentation in README.md
- MIT License

### Technical Details
- Python 3.8+ support
- SQLite database at `~/.issuedb/issuedb.sqlite`
- Zero external dependencies (uses only Python standard library)
- Full transaction support with rollback capability
- Row-level locking for concurrent access
- Comprehensive error handling

### Commands
- `create` - Create a new issue
- `list` - List issues with filters
- `get` - Get issue details
- `update` - Update issue fields
- `delete` - Delete an issue (with audit trail)
- `get-next` - Get next issue by priority and FIFO
- `search` - Search issues by keyword
- `clear` - Clear all project issues (with confirmation)
- `audit` - View audit logs
- `info` - Database statistics

### CLI Options
- `--db PATH` - Custom database path
- `--json` - JSON output format
- `--prompt` - Display LLM agent guide
- `--ollama REQUEST` - Natural language command generation
- `--ollama-model MODEL` - Specify Ollama model
- `--ollama-host HOST` - Ollama server host
- `--ollama-port PORT` - Ollama server port

[1.0.0]: https://github.com/rodmena-limited/issue-queue/releases/tag/v1.0.0
