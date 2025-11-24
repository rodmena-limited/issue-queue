# Changelog

All notable changes to IssueDB will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
