# Changelog

All notable changes to IssueDB will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

(Note: this file was not maintained between 2.3.1 and 2.12.0; see git history
for the intermediate releases.)

## [2.22.0]

### Fixed
- **A malformed change from the server crashed the planner.** `payload.get(...)`
  on a payload that was a string raised `AttributeError` and took the whole plan
  down — one bad row broke sync for every other row on the page. Server data is
  input, not something to trust.
- **A malformed change was silently applied.** An issue with no payload or an
  empty title planned as `CREATE` and produced a titleless row. It is now
  `MALFORMED`: reported, never applied, and it does not advance the cursor.

### Added
- `MALFORMED` is distinct from `UNSUPPORTED`, decided after the entity fork so
  an unsupported type is never reported as a data defect in a feature that does
  not exist yet. Both directions asserted — a client calling everything
  "unsupported" would pass the unsupported test alone.

## [2.21.0]

### Added
- **The apply path reads `entities` from the handshake**, separating two causes
  that were previously one observation: *the server has not shipped this entity
  type* (`UNSUPPORTED`) versus *issuedb does not apply it yet* (`SKIP`). Before
  the field existed both arrived as an identical per-entry rejection, and a
  client that cannot tell them apart either retries forever against a server
  that will never accept tags, or discards a genuinely malformed entry as
  unsupported. `None` — an older server omitting the field — is **not** read as
  "supports nothing", which would mark every change unsupported and silently
  stop applying anything.
- **The drift check now compares the handshake RESPONSE too.** It previously
  compared only what the client *sends* against what the contract *requires*, so
  a response-side addition was invisible: `entities` shipped and went unread
  while the check said "no drift" — correctly, and uselessly, because it was
  answering a different question.

### Fixed
- `openapi.yaml` re-vendored at Tracker `2012446`.

## [2.20.0]

### Added
- **`issuedb-cli sync` — pull from Tracker, DRY RUN by default** (#9).
  - Everything else in this package writes into a server with backups and an
    audit trail. This writes into someone's **local** issue database, where a
    defect destroys work that exists nowhere else — so the design is four
    refusals rather than four features.
  - **Dry run is the default.** `sync` reports what it *would* change and
    changes nothing; `--apply` is explicit. The dry run and the real run share
    one `plan()` call, so the plan shown is the plan executed.
  - **Absence never deletes.** A uid missing from a pulled page means "not on
    this page", not "deleted". Only an explicit tombstone removes a row.
  - **The cursor advances only to what was durably committed** — not to the end
    of the page, not to the last change examined. A cursor past a failed apply
    skips those rows forever with nothing erroring.
  - **A failure stops the run**; applied changes stay, the rest are not
    attempted, and re-running retries from the last durable position.
  - An **ambiguous** uid is never applied and never advances the cursor.
  - Verified against the **real server**: 52 changes applied, a pre-existing
    local issue untouched, and convergence proven three ways — a second run
    applying nothing, and a full re-pull from cursor zero re-applying 52
    changes with zero duplicates.

## [2.19.0]

### Added
- **The server-minted `project_uid` is recorded immutably in `.issue.db`**
  (`issuedb/sync/_project.py`, migration 4). (#8)
  - It is **field 1 of every derived uid**, so deriving without it produces uids
    the server never agrees with and the rows silently fail to converge.
    `require_project_uid()` therefore **raises** rather than substituting an
    empty string — `get_project_uid(conn) or ""` is the natural thing to write
    and it is catastrophic.
  - Write-once. A server reporting a *different* project for a database that
    already holds one is refused: the path was reused or the key swapped, and
    adopting the new id would merge two projects' rows under one identity.
  - `CHECK (id = 1)` makes "one project per database" a schema constraint, so it
    holds against a direct `sqlite3` write.
  - Unlike the cursor, this belongs *in* the committed file: same for every
    clone, non-secret, and it lets a fresh clone know its project with zero
    setup.

### Documentation
- `audit/MUTATION_TESTING.md` — a mutation that appears to **survive** may be a
  stale `.pyc`. CPython's timestamp-based invalidation has one-second
  granularity, and a write→run→restore loop hits that window constantly. A
  **red** result is self-proving; a **survivor** is not. Both
  `PYTHONDONTWRITEBYTECODE=1` and an on-disk postcondition are needed, and
  neither implies the other.

## [2.18.0]

### Changed
- **`git-scan` refuses to act on an ambiguous `#N`** and reports every
  candidate. (#6)
  - This is where the ambiguity rule stops being a display concern and starts
    preventing a destructive write: `git-scan --auto-close` CLOSES issues from a
    number parsed out of a commit message, and two clones allocate that number
    independently. Acting on an ambiguous reference closes **somebody else's
    issue**, and nothing errors when it does.
  - For an automated action, "select none" means **do nothing and report**. The
    scan skips the reference, creates no link, closes nothing, and continues
    with the other commits.
  - Ambiguity is checked **before** the issue lookup — the local candidate is
    always findable, so a lookup-first scanner would act on it and never reach
    the check.
  - `ambiguous_refs` is a first-class count on the result and appears on its own
    summary line. Buried in `details`, "Closed 0 issue(s)" reads as "nothing to
    do" rather than "I refused to guess".
  - Every candidate is named with its uid, so the refusal is actionable instead
    of a dead end.

## [2.17.0]

### Added
- **Ambiguous issue references: present every candidate, select none**
  (`issuedb/sync/_references.py`, schema migration 3). (#6)
  - Two clones of a repo that commits `.issue.db` allocate from the same
    AUTOINCREMENT counter independently, so both mint a different issue
    numbered 3 — reproduced, not theorised. Renumbering is not available as a
    repair: `parse_issue_refs` resolves `#3` out of commit messages already
    immutable in git history, so renumbering silently repoints old commits at
    someone else's work.
  - `resolve_reference()` returns every candidate and **never picks one**.
    `resolved()` returns `None` when several match rather than a first-of, so
    "just take the first" is not something a caller can write by accident.
    Not newest-wins, not most-recently-updated-wins — a plausible tie-break is
    the most dangerous kind, because it looks like a feature.
  - New `issue_number_alias` table, **keyed by uid** with `(replica_id,
    local_number)` as attributes. Keyed by number it would have the very
    collision it exists to resolve. No foreign keys, so an alias outlives the
    row and a five-year-old `#3` still resolves to something.
  - Ambiguous and unknown references are reported **separately** — unknown
    means stale, ambiguous means real and needing a human.
  - Stdlib only.

## [2.16.0]

### Added
- **Sync client: handshake, push, pull, and cursor state** (`issuedb/sync/_client.py`,
  `issuedb/sync/_state.py`). `urllib` only. (#5)
  - The handshake is a **preflight that fails closed**: if the server's protocol
    range does not include ours, nothing is written locally. The client checks
    the advertised range *itself*, not only the server's 409, so a server that
    advertises without enforcing cannot wave an incompatible client through.
  - Errors branch on the problem+json `code`, **not on the HTTP status** — two
    different 409s mean opposite things (`protocol_unsupported` = stop,
    `cursor_too_old` = re-seed). `Retry-After` is taken from the server rather
    than a locally invented backoff.
  - **Cursor and replica id live in `$XDG_CONFIG_HOME/issuedb/`, never in
    `.issue.db`**: a cursor in a git-tracked file rolled *forward* by a checkout
    silently skips server changes that were never applied, and a replica id in a
    tracked file would be claimed by every clone at once. State is keyed by
    database path and validated against the project uid, so a reused path cannot
    inherit a foreign cursor.
  - A replayed push (`existing`) is success, not a conflict — the normal case in
    a repo that commits `.issue.db`.
  - Tested against Tracker's real FakeTracker **over HTTP with no mock
    transport**; FakeTracker and all twelve vectors are vendored into
    `tests/data/` so the tests run rather than skip.

### Note
- **Tracker has not implemented `/v1/sync/*`.** Probed live: `/_build`,
  `/_design`, `/healthz` and `/` all return 200 while all three sync endpoints
  return 404. This client has never successfully talked to Tracker and cannot
  yet. A green test run means "the fixture agrees", not "sync works".

## [2.15.0]

### Added
- **`issuedb-cli signin` / `signout` / `whoami`** — Tracker credentials, stored
  outside the database. (#4)
  - Credentials live in `$XDG_CONFIG_HOME/issuedb/credentials.json`, **never in
    `.issue.db`** (which is committed to git in many repos) and never in the
    working directory. Keyed by server URL, so two servers do not evict each
    other.
  - These commands **short-circuit before the database is opened**, so signing
    in never leaves a stray `.issue.db` in whatever directory you were standing
    in.
  - File mode 0600, directory 0700, written via `mkstemp` + atomic rename so the
    secret is never on disk at a wider mode even briefly. Loose permissions are
    tightened on the next write.
  - **`signout` removes the file**, rather than blanking the entry, and reports
    honestly when there was nothing to remove.
  - The secret portion of a token is never printed — not by `signin`, not by
    `whoami`, and not in error messages. The `key_id` is not secret and is shown,
    so "which key was that?" stays answerable.
  - Not included, deliberately: token refresh, device flow, multi-account
    switching. `signin` does not yet verify the key against Tracker, because
    `/v1/sync/handshake` is not implemented — a stored credential means "a
    well-formed key was saved", never "the key works".
  - Stdlib only.

## [2.14.0]

### Added
- **Sync identity: canonical uids, the `sync_row` ledger, and the `sync_outbox`
  change feed** (`issuedb/sync/`, schema migration 2). The client half of the
  issuedb <-> Tracker sync protocol. No network code yet.
  - The canonical uid form is frozen and **cross-checked against Tracker's
    independently authored expectations — 10 of 10 derivations agree**. Two
    implementations, two repos, identical bytes; the vectors are vendored into
    `tests/data/` so the check runs in CI rather than skipping.
  - `sync_row` has **no foreign keys**, so a ledger entry outlives the row it
    describes and a tombstone is never cascaded away.
  - `sync_row.uid` is **not UNIQUE**: bidirectional `relates_to` pairs are legal
    today and derive one uid under the symmetric rule, so a pre-existing database
    already contains them. Collisions are reported by `find_uid_collisions()`,
    never merged. `resolve_uid()` returns a list — an ambiguous reference
    presents every candidate and selects none.
  - `sync_outbox` is fed by **SQLite triggers**, so writes from the CLI, the
    Flask UI, a raw `sqlite3` session, or an older installed issuedb are all
    captured. Cascade-deleted children fire their triggers — verified, not
    assumed; without it, child tombstones would never propagate.
  - Stdlib only. (#3)

## [2.13.0]

### Added
- **Forward-only schema migration ladder** (`issuedb/database/_migrations.py`).
  Every `.issue.db` now records its schema version in `PRAGMA user_version`.
  Pending migrations apply on open in ascending order, each in its own
  transaction together with the version bump, so a crash leaves the database at
  a version that is true rather than half-applied. Databases predating this are
  stamped to the baseline without re-running baseline DDL, so existing data is
  untouched. A database written by a *newer* issuedb is now REFUSED
  (`NewerDatabaseError`) instead of being opened read-write with older
  assumptions — this matters wherever a `.issue.db` is shared through git and
  one machine has an older install. Forward only: there are no down-migrations,
  because a rollback path that is never exercised is one that does not work.
  New: `Database.schema_version`, `Database.supported_schema_version`.
  Documented in `docs/schema_versioning.rst`. Stdlib only. (#2)

### Fixed
- **The declared version disagreed with itself.** `pyproject.toml` said 2.12.0
  while `issuedb/__init__.py` said 2.11.0, so a bug report quoting either named
  a release that did not contain the code being reported. All declarations are
  now aligned and `tests/test_version_consistency.py` fails if they drift again.

## [Unreleased]

### Added
- GitHub Actions CI/CD pipeline (`.github/workflows/`). `ci.yml` runs the full
  test suite on Python 3.9–3.14 (with the `[web]` extra so Flask tests run),
  plus `ruff check`, `mypy`, and a `build` + `twine check` job, on every push
  and pull request. `release.yml` publishes to PyPI via OIDC Trusted Publishing
  when a GitHub Release tagged `v<version>` is published, after re-running the
  tests and verifying the built version matches the tag. This is
  infrastructure only — no packaged code changed, so the package version is
  unchanged.

## [2.12.0] - 2026-07-23

Full audit release: correctness, concurrency, security, and agent-contract
hardening across every layer.

### Fixed
- Status/priority filters now match documented aliases (`in_progress`,
  `in progress`, padded/case-variant values) in list, count, get-next,
  blocked, and advanced search — previously they validated but matched
  nothing.
- `bulk-create` no longer silently drops `due_date`, `estimated_hours`, and
  `tags`.
- CLI error contract: invalid `create --due-date`, memory/lesson/link
  failures, `estimate` on a missing issue, and `timer-stop` with no running
  timer now exit 1 with the error on stderr (previously stdout + exit 0).
  Bare `memory`/`lesson`/`tag`/`link` exit 2. Broken pipes (`| head`) exit
  quietly with code 141.
- Keyword search escapes `%` and `_` (LIKE wildcards) so they match literally.
- Blockers in `wont-do` status count as resolved: dependent issues are no
  longer hidden from `get-next`/`blocked` forever.
- Stored XSS in the web issue-detail page (audit history values, dependency
  titles, time-entry notes, commit hashes) — all dynamic HTML is now escaped.
- Web: the `?db=` query parameter no longer selects the database (it allowed
  any request to create/read arbitrary SQLite files); the served database is
  fixed at startup and `issuedb-cli web` now honors `--db`.
- Web: blank-title form posts no longer 500; JSON API accepts `tags` as an
  array; updating a missing issue returns 404; inbound links can be deleted;
  search composes with status/priority/tag filters; memory keys containing
  `/` can be deleted; `GET /api/next` no longer writes an audit row.
- Git: `get_commit_message` returned the wrong commit's message (pathspec
  misuse); commit scanning now reads full message bodies and survives `|` in
  author names; detached HEAD no longer reports branch "HEAD"; issue-ref
  search no longer matches `#10` when looking for `#1`.
- Ollama: `OLLAMA_HOST` accepts `host:port` and URL forms; generated commands
  run this installation's CLI (not whatever `issuedb-cli` is on PATH); prose
  is no longer extracted and executed as a command; interactive runs ask for
  confirmation; added `--ollama-dry-run`.
- Similarity: all-punctuation texts no longer score 1.0 against each other;
  `dedupe` is ~3x faster on large databases.
- Concurrency: WAL-mode switch and schema migration no longer crash when
  several processes open a fresh database simultaneously; duplicate running
  timers per issue are prevented by a unique index; workspace `stop` cannot
  wipe another process's newly started issue; `clear` snapshots and deletes
  atomically.
- Tests no longer touch (or delete!) the real `.issue.db` in the invoking
  directory — every test runs in an isolated temp directory.

### Added
- Git integration commands: `git-link`, `git-unlink`, `git-links`,
  `git-linked`, `git-scan [--auto-close]`, `git-status` (the code existed but
  was never wired to the CLI).
- Issue templates: `templates` and `create --template NAME` (bug/feature/task
  built-ins).
- `create --check-duplicates` / `--force` flags (documented but previously
  not wired).
- `timer-stop` with no arguments now stops all running timers (matching its
  help text); new `stop_all_timers` repository API.
- List/search/get-next now include issue tags in output.

### Changed
- Minimum supported Python is 3.9 (the code used runtime PEP 585 generics
  that never imported on 3.8).
- Deleted templates are no longer re-seeded on every start (seeding happens
  only when a database is first created).
- Removed dead repo-root scripts `git_cli_integration.py` and
  `screenshot_tool.py`.

## [2.3.1] - 2025-11-25

### Fixed
- **--ollama flag now accepts unquoted multi-word requests**: No need to quote the natural language request
  - Before: `issuedb-cli --ollama "create a high priority bug"`
  - After: `issuedb-cli --ollama create a high priority bug`
  - Note: `--ollama-model`, `--ollama-host`, `--ollama-port` must come BEFORE `--ollama`
  - Example: `issuedb-cli --ollama-model llama3 --ollama create a critical issue for login bug`

### Technical Details
- Changed `--ollama` to use `nargs=argparse.REMAINDER` to capture all remaining arguments
- 4 new tests for argparse behavior (now 136 total tests)

## [2.3.0] - 2025-11-25

### Added
- **Fetch History Tracking**: Track which issues were fetched via `get-next`
  - `get-next` now logs a `FETCH` action in the audit trail
  - New `get-last` command to view last fetched issue(s)
  - `-n/--number` flag to get last N fetched issues (default: 1)
  - Shows current state of existing issues or reconstructs from audit log for deleted issues
  - Example: `issuedb-cli get-last -n 5` to see last 5 fetched issues
  - Useful for tracking what issues you've recently worked on

### Technical Details
- New `FETCH` action type in audit logs
- `log_fetch` parameter in `get_next_issue()` to control logging (default: True)
- New `get_last_fetched(limit)` method in IssueRepository
- 16 new tests for get-last functionality (now 132 total tests)
- Updated LLM agent prompt with get-last examples
- Full documentation update for Read the Docs

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
