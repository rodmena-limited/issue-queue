# IssueDB Web UI

IssueDB v2.5.0 introduces an optional web interface for visual issue management.

## Installation

The web UI requires Flask, which is an optional dependency. Install it with:

```bash
# From PyPI
pip install issuedb[web]

# From source
pip install -e ".[web]"
```

## Starting the Server

```bash
# Start on default port (7760)
issuedb-cli web

# Custom port
issuedb-cli web --port 8080

# Custom host
issuedb-cli web --host localhost

# Enable debug mode
issuedb-cli web --debug
```

## Pages

### Dashboard (`/`)

The dashboard provides an overview of your issues:

- **Statistics Cards**: Total issues, open, in-progress, and closed counts with progress bars
- **Priority Breakdown**: Visual breakdown of issues by priority level
- **Next Issue**: The highest priority open issue ready to work on
- **Active Issue**: Currently active issue (if any) with stop/close buttons
- **Recent Issues**: Table of the 5 most recently created issues

### Issues List (`/issues`)

Browse and filter all issues:

- **Status Filter**: Filter by open, in-progress, or closed status
- **Priority Filter**: Filter by critical, high, medium, or low priority
- **Search**: Full-text search across issue titles and descriptions
- **Actions**: Quick edit and close buttons for each issue

### Memory (`/memory`)

Manage persistent memory items:

- **List**: View all memory items grouped by category
- **Add**: Add new memory items
- **Delete**: Remove memory items

### Lessons (`/lessons`)

View and manage lessons learned:

- **List**: View lessons learned from resolved issues
- **Add**: Record new lessons

### Issue Detail (`/issues/<id>`)

Full issue view with:

- **Description**: Complete issue description
- **Comments**: View and add comments to the issue
- **Quick Actions**: Start, close, or reopen the issue
- **Status/Priority Dropdowns**: Change status and priority inline
- **Linked Issues**: View and manage related issues
- **Blockers**: Issues blocking this issue (if any)
- **Blocking**: Issues this issue is blocking (if any)
- **Code References**: Files and line numbers linked to this issue
- **Danger Zone**: Delete the issue

### Create/Edit Forms (`/issues/new`, `/issues/<id>/edit`)

- **Title**: Required issue title
- **Description**: Optional detailed description
- **Priority**: Select from low, medium, high, critical
- **Status**: Select from open, in-progress, closed

## API Endpoints

All endpoints support JSON for programmatic access.

### Issues

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/issues` | List all issues (supports status, priority, limit params) |
| POST | `/api/issues` | Create a new issue |
| GET | `/api/issues/<id>` | Get issue by ID |
| PUT/PATCH | `/api/issues/<id>` | Update an issue |
| DELETE | `/api/issues/<id>` | Delete an issue |

### Comments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/issues/<id>/comments` | Add a comment |
| DELETE | `/api/comments/<id>` | Delete a comment |

### Workflow

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/issues/<id>/start` | Start working on an issue |
| POST | `/api/issues/stop` | Stop working (add ?close=1 to also close) |

### Utilities

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary` | Get summary statistics |
| GET | `/api/next` | Get next issue to work on |

## Examples

### Create Issue via API

```bash
curl -X POST http://localhost:7760/api/issues \
  -H "Content-Type: application/json" \
  -d '{"title": "Fix login bug", "priority": "high", "description": "Users cannot log in"}'
```

### Update Issue Status

```bash
curl -X PATCH http://localhost:7760/api/issues/5 \
  -H "Content-Type: application/json" \
  -d '{"status": "closed"}'
```

### Add Comment

```bash
curl -X POST http://localhost:7760/api/issues/5/comments \
  -H "Content-Type: application/json" \
  -d '{"text": "Fixed by updating configuration"}'
```

### Get Summary

```bash
curl http://localhost:7760/api/summary
```

Response:
```json
{
  "total_issues": 14,
  "by_status": {
    "open": 8,
    "in_progress": 2,
    "closed": 4
  },
  "by_priority": {
    "critical": 5,
    "high": 9,
    "medium": 0,
    "low": 0
  }
}
```

## Design

The web UI features a clean, premium dark theme with:

- **Monospace fonts**: Consistent developer-friendly typography
- **Dark color scheme**: Easy on the eyes for extended use
- **Status badges**: Color-coded status and priority indicators
- **Responsive layout**: Works on desktop and mobile devices
- **No external dependencies**: All CSS is inline, no JavaScript frameworks

## Requirements

The web UI requires Flask:

```bash
pip install flask
```

Flask is only needed for the web UI feature; the core CLI functionality works without any external dependencies.
