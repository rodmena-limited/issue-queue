"""Flask Web UI and API for IssueDB."""

from typing import Any, Union

from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from werkzeug.wrappers import Response

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository

app = Flask(__name__)


def get_repo() -> IssueRepository:
    """Get repository instance."""
    db_path = request.args.get("db")
    return IssueRepository(db_path)


# =============================================================================
# HTML Templates
# =============================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}IssueDB{% endblock %}</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --bg-hover: #30363d;
            --border-color: #30363d;
            --border-light: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-orange: #db6d28;
            --accent-red: #f85149;
            --accent-purple: #a371f7;
            --status-open: #3fb950;
            --status-progress: #d29922;
            --status-closed: #8b949e;
            --priority-low: #8b949e;
            --priority-medium: #58a6ff;
            --priority-high: #d29922;
            --priority-critical: #f85149;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code',
                         'Droid Sans Mono', 'Source Code Pro', monospace;
            font-size: 14px;
            line-height: 1.6;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        a {
            color: var(--accent-blue);
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        /* Layout */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 24px;
        }

        /* Header */
        .header {
            background-color: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 0;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .logo-icon {
            color: var(--accent-blue);
        }

        .nav {
            display: flex;
            gap: 24px;
        }

        .nav a {
            color: var(--text-secondary);
            font-size: 14px;
            padding: 8px 0;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .nav a:hover,
        .nav a.active {
            color: var(--text-primary);
            text-decoration: none;
            border-bottom-color: var(--accent-blue);
        }

        /* Main content */
        .main {
            padding: 32px 0;
        }

        .page-header {
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .page-title {
            font-size: 24px;
            font-weight: 600;
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            font-family: inherit;
            font-size: 14px;
            font-weight: 500;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn:hover {
            background-color: var(--bg-hover);
            text-decoration: none;
        }

        .btn-primary {
            background-color: var(--accent-green);
            border-color: var(--accent-green);
            color: #000;
        }

        .btn-primary:hover {
            background-color: #2ea043;
            border-color: #2ea043;
        }

        .btn-danger {
            background-color: transparent;
            border-color: var(--accent-red);
            color: var(--accent-red);
        }

        .btn-danger:hover {
            background-color: var(--accent-red);
            color: #fff;
        }

        .btn-sm {
            padding: 4px 12px;
            font-size: 12px;
        }

        /* Cards */
        .card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-light);
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }

        .stat-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
        }

        .stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .stat-breakdown {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border-light);
        }

        .stat-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            font-size: 13px;
        }

        .stat-item-label {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .stat-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 2px 8px;
            font-size: 12px;
            font-weight: 500;
            border-radius: 12px;
            text-transform: capitalize;
        }

        .badge-open {
            background-color: rgba(63, 185, 80, 0.15);
            color: var(--status-open);
            border: 1px solid rgba(63, 185, 80, 0.3);
        }

        .badge-in-progress {
            background-color: rgba(210, 153, 34, 0.15);
            color: var(--status-progress);
            border: 1px solid rgba(210, 153, 34, 0.3);
        }

        .badge-closed {
            background-color: rgba(139, 148, 158, 0.15);
            color: var(--status-closed);
            border: 1px solid rgba(139, 148, 158, 0.3);
        }

        .badge-low {
            background-color: rgba(139, 148, 158, 0.15);
            color: var(--priority-low);
            border: 1px solid rgba(139, 148, 158, 0.3);
        }

        .badge-medium {
            background-color: rgba(88, 166, 255, 0.15);
            color: var(--priority-medium);
            border: 1px solid rgba(88, 166, 255, 0.3);
        }

        .badge-high {
            background-color: rgba(210, 153, 34, 0.15);
            color: var(--priority-high);
            border: 1px solid rgba(210, 153, 34, 0.3);
        }

        .badge-critical {
            background-color: rgba(248, 81, 73, 0.15);
            color: var(--priority-critical);
            border: 1px solid rgba(248, 81, 73, 0.3);
        }

        /* Issue Table */
        .issue-table {
            width: 100%;
            border-collapse: collapse;
        }

        .issue-table th,
        .issue-table td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-light);
        }

        .issue-table th {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background-color: var(--bg-tertiary);
        }

        .issue-table tr:hover {
            background-color: var(--bg-tertiary);
        }

        .issue-id {
            color: var(--text-muted);
            font-weight: 500;
        }

        .issue-title {
            font-weight: 500;
        }

        .issue-title a {
            color: var(--text-primary);
        }

        .issue-title a:hover {
            color: var(--accent-blue);
        }

        .issue-meta {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* Filters */
        .filters {
            display: flex;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            align-items: center;
        }

        .filter-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .filter-label {
            font-size: 12px;
            color: var(--text-secondary);
        }

        select, input[type="text"], input[type="search"], textarea {
            font-family: inherit;
            font-size: 14px;
            padding: 8px 12px;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
        }

        select:focus, input:focus, textarea:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
        }

        .search-input {
            min-width: 250px;
        }

        /* Forms */
        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        .form-control {
            width: 100%;
            padding: 10px 14px;
            font-family: inherit;
            font-size: 14px;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
        }

        .form-control:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
        }

        textarea.form-control {
            min-height: 120px;
            resize: vertical;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }

        /* Issue Detail */
        .issue-detail-header {
            margin-bottom: 24px;
        }

        .issue-detail-title {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 12px;
        }

        .issue-detail-meta {
            display: flex;
            gap: 16px;
            align-items: center;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .issue-detail-body {
            display: grid;
            grid-template-columns: 1fr 300px;
            gap: 24px;
        }

        @media (max-width: 900px) {
            .issue-detail-body {
                grid-template-columns: 1fr;
            }
        }

        .issue-description {
            white-space: pre-wrap;
            line-height: 1.8;
        }

        .sidebar-section {
            padding: 16px;
            border-bottom: 1px solid var(--border-light);
        }

        .sidebar-section:last-child {
            border-bottom: none;
        }

        .sidebar-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        /* Comments */
        .comments-section {
            margin-top: 32px;
        }

        .comment {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 16px;
        }

        .comment-header {
            padding: 12px 16px;
            background-color: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-light);
            border-radius: 8px 8px 0 0;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .comment-body {
            padding: 16px;
            white-space: pre-wrap;
        }

        .comment-form {
            margin-top: 16px;
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        .empty-state-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        /* Alert messages */
        .alert {
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 14px;
        }

        .alert-success {
            background-color: rgba(63, 185, 80, 0.15);
            border: 1px solid rgba(63, 185, 80, 0.3);
            color: var(--accent-green);
        }

        .alert-error {
            background-color: rgba(248, 81, 73, 0.15);
            border: 1px solid rgba(248, 81, 73, 0.3);
            color: var(--accent-red);
        }

        /* Progress bar */
        .progress-bar {
            height: 8px;
            background-color: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        .progress-green { background-color: var(--accent-green); }
        .progress-yellow { background-color: var(--accent-yellow); }
        .progress-red { background-color: var(--accent-red); }
        .progress-gray { background-color: var(--text-muted); }

        /* Action buttons row */
        .action-row {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }

        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }

        .modal-overlay.active {
            display: flex;
        }

        .modal {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .modal-title {
            font-size: 18px;
            font-weight: 600;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 24px;
            cursor: pointer;
            padding: 4px;
        }

        .modal-close:hover {
            color: var(--text-primary);
        }

        /* Footer */
        .footer {
            padding: 24px 0;
            border-top: 1px solid var(--border-color);
            margin-top: 48px;
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
        }

        /* Blockers */
        .blockers-list {
            margin-top: 8px;
        }

        .blocker-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 0;
            font-size: 13px;
        }

        .blocker-icon {
            color: var(--accent-red);
        }

        /* Code refs */
        .code-ref {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background-color: var(--bg-tertiary);
            border-radius: 4px;
            font-size: 13px;
            margin-top: 8px;
        }

        .code-ref-path {
            color: var(--accent-blue);
        }

        .code-ref-lines {
            color: var(--text-muted);
        }

        /* Quick actions */
        .quick-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .quick-action {
            padding: 6px 12px;
            font-size: 12px;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            cursor: pointer;
            color: var(--text-secondary);
            transition: all 0.2s;
        }

        .quick-action:hover {
            background-color: var(--bg-hover);
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <div class="header-content">
                <a href="/" class="logo">
                    <span class="logo-icon">&gt;_</span>
                    <span>IssueDB</span>
                </a>
                <nav class="nav">
                    <a href="/" class="{{ 'active' if active_page == 'dashboard' else '' }}">Dashboard</a>
                    <a href="/issues" class="{{ 'active' if active_page == 'issues' else '' }}">Issues</a>
                    <a href="/issues/new" class="{{ 'active' if active_page == 'new' else '' }}">New Issue</a>
                </nav>
            </div>
        </div>
    </header>

    <main class="main">
        <div class="container">
            {% block content %}{% endblock %}
        </div>
    </main>

    <footer class="footer">
        <div class="container">
            IssueDB v2.5.0 &middot; Command-line issue tracking for developers
        </div>
    </footer>

    {% block scripts %}{% endblock %}
</body>
</html>
"""

DASHBOARD_TEMPLATE = (
    BASE_TEMPLATE.replace("{% block title %}IssueDB{% endblock %}", "{% block title %}Dashboard - IssueDB{% endblock %}")
    .replace("{% block content %}{% endblock %}", """{% block content %}
<div class="page-header">
    <h1 class="page-title">Dashboard</h1>
    <a href="/issues/new" class="btn btn-primary">+ New Issue</a>
</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-label">Total Issues</div>
        <div class="stat-value">{{ summary.total_issues }}</div>
    </div>

    <div class="stat-card">
        <div class="stat-label">Open Issues</div>
        <div class="stat-value" style="color: var(--status-open)">{{ summary.by_status.open }}</div>
        <div class="progress-bar">
            <div class="progress-fill progress-green" style="width: {{ summary.status_percentages.open | default(0) }}%"></div>
        </div>
    </div>

    <div class="stat-card">
        <div class="stat-label">In Progress</div>
        <div class="stat-value" style="color: var(--status-progress)">{{ summary.by_status.in_progress }}</div>
        <div class="progress-bar">
            <div class="progress-fill progress-yellow" style="width: {{ summary.status_percentages['in-progress'] | default(0) }}%"></div>
        </div>
    </div>

    <div class="stat-card">
        <div class="stat-label">Closed</div>
        <div class="stat-value" style="color: var(--status-closed)">{{ summary.by_status.closed }}</div>
        <div class="progress-bar">
            <div class="progress-fill progress-gray" style="width: {{ summary.status_percentages.closed | default(0) }}%"></div>
        </div>
    </div>
</div>

<div class="stats-grid">
    <div class="card">
        <div class="card-header">
            <h3 class="card-title">Priority Breakdown</h3>
        </div>
        <div class="stat-breakdown">
            <div class="stat-item">
                <span class="stat-item-label">
                    <span class="stat-dot" style="background-color: var(--priority-critical)"></span>
                    Critical
                </span>
                <span>{{ summary.by_priority.critical }}</span>
            </div>
            <div class="stat-item">
                <span class="stat-item-label">
                    <span class="stat-dot" style="background-color: var(--priority-high)"></span>
                    High
                </span>
                <span>{{ summary.by_priority.high }}</span>
            </div>
            <div class="stat-item">
                <span class="stat-item-label">
                    <span class="stat-dot" style="background-color: var(--priority-medium)"></span>
                    Medium
                </span>
                <span>{{ summary.by_priority.medium }}</span>
            </div>
            <div class="stat-item">
                <span class="stat-item-label">
                    <span class="stat-dot" style="background-color: var(--priority-low)"></span>
                    Low
                </span>
                <span>{{ summary.by_priority.low }}</span>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <h3 class="card-title">Next Issue</h3>
        </div>
        {% if next_issue %}
        <div>
            <div class="issue-title">
                <a href="/issues/{{ next_issue.id }}">#{{ next_issue.id }} {{ next_issue.title }}</a>
            </div>
            <div class="issue-meta">
                <span class="badge badge-{{ next_issue.priority.value }}">{{ next_issue.priority.value }}</span>
                <span class="badge badge-{{ next_issue.status.value | replace('-', '-') }}">{{ next_issue.status.value }}</span>
            </div>
            <div class="action-row">
                <form action="/api/issues/{{ next_issue.id }}/start" method="post" style="display: inline;">
                    <button type="submit" class="btn btn-sm btn-primary">Start Working</button>
                </form>
            </div>
        </div>
        {% else %}
        <div class="empty-state" style="padding: 20px;">
            <p>No open issues to work on</p>
        </div>
        {% endif %}
    </div>

    <div class="card">
        <div class="card-header">
            <h3 class="card-title">Active Issue</h3>
        </div>
        {% if active_issue %}
        <div>
            <div class="issue-title">
                <a href="/issues/{{ active_issue.id }}">#{{ active_issue.id }} {{ active_issue.title }}</a>
            </div>
            <div class="issue-meta" style="margin-top: 8px;">
                Started: {{ active_started | default('N/A') }}
            </div>
            <div class="action-row">
                <form action="/api/issues/stop" method="post" style="display: inline;">
                    <button type="submit" class="btn btn-sm">Stop</button>
                </form>
                <form action="/api/issues/stop?close=1" method="post" style="display: inline;">
                    <button type="submit" class="btn btn-sm btn-primary">Stop & Close</button>
                </form>
            </div>
        </div>
        {% else %}
        <div class="empty-state" style="padding: 20px;">
            <p>No active issue</p>
        </div>
        {% endif %}
    </div>
</div>

<div class="card">
    <div class="card-header">
        <h3 class="card-title">Recent Issues</h3>
        <a href="/issues" class="btn btn-sm">View All</a>
    </div>
    {% if recent_issues %}
    <table class="issue-table">
        <thead>
            <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Created</th>
            </tr>
        </thead>
        <tbody>
            {% for issue in recent_issues %}
            <tr>
                <td class="issue-id">#{{ issue.id }}</td>
                <td class="issue-title">
                    <a href="/issues/{{ issue.id }}">{{ issue.title }}</a>
                </td>
                <td><span class="badge badge-{{ issue.status.value | replace('-', '-') }}">{{ issue.status.value }}</span></td>
                <td><span class="badge badge-{{ issue.priority.value }}">{{ issue.priority.value }}</span></td>
                <td class="issue-meta">{{ issue.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <div class="empty-state-icon">&gt;_</div>
        <div class="empty-state-title">No issues yet</div>
        <p>Create your first issue to get started</p>
    </div>
    {% endif %}
</div>
{% endblock %}""")
)

ISSUES_LIST_TEMPLATE = (
    BASE_TEMPLATE.replace("{% block title %}IssueDB{% endblock %}", "{% block title %}Issues - IssueDB{% endblock %}")
    .replace("{% block content %}{% endblock %}", """{% block content %}
<div class="page-header">
    <h1 class="page-title">Issues</h1>
    <a href="/issues/new" class="btn btn-primary">+ New Issue</a>
</div>

{% if message %}
<div class="alert alert-success">{{ message }}</div>
{% endif %}

<div class="card">
    <form method="get" class="filters">
        <div class="filter-group">
            <label class="filter-label">Status:</label>
            <select name="status" onchange="this.form.submit()">
                <option value="">All</option>
                <option value="open" {{ 'selected' if status_filter == 'open' }}>Open</option>
                <option value="in-progress" {{ 'selected' if status_filter == 'in-progress' }}>In Progress</option>
                <option value="closed" {{ 'selected' if status_filter == 'closed' }}>Closed</option>
            </select>
        </div>
        <div class="filter-group">
            <label class="filter-label">Priority:</label>
            <select name="priority" onchange="this.form.submit()">
                <option value="">All</option>
                <option value="critical" {{ 'selected' if priority_filter == 'critical' }}>Critical</option>
                <option value="high" {{ 'selected' if priority_filter == 'high' }}>High</option>
                <option value="medium" {{ 'selected' if priority_filter == 'medium' }}>Medium</option>
                <option value="low" {{ 'selected' if priority_filter == 'low' }}>Low</option>
            </select>
        </div>
        <div class="filter-group">
            <input type="search" name="q" placeholder="Search issues..."
                   value="{{ search_query | default('') }}" class="search-input">
            <button type="submit" class="btn">Search</button>
        </div>
    </form>

    {% if issues %}
    <table class="issue-table">
        <thead>
            <tr>
                <th style="width: 60px;">ID</th>
                <th>Title</th>
                <th style="width: 100px;">Status</th>
                <th style="width: 90px;">Priority</th>
                <th style="width: 140px;">Created</th>
                <th style="width: 100px;">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for issue in issues %}
            <tr>
                <td class="issue-id">#{{ issue.id }}</td>
                <td class="issue-title">
                    <a href="/issues/{{ issue.id }}">{{ issue.title }}</a>
                    {% if issue.description %}
                    <div class="issue-meta">{{ issue.description[:80] }}{% if issue.description|length > 80 %}...{% endif %}</div>
                    {% endif %}
                </td>
                <td><span class="badge badge-{{ issue.status.value | replace('-', '-') }}">{{ issue.status.value }}</span></td>
                <td><span class="badge badge-{{ issue.priority.value }}">{{ issue.priority.value }}</span></td>
                <td class="issue-meta">{{ issue.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
                <td>
                    <div class="quick-actions">
                        <a href="/issues/{{ issue.id }}/edit" class="quick-action">Edit</a>
                        {% if issue.status.value != 'closed' %}
                        <form action="/api/issues/{{ issue.id }}" method="post" style="display: inline;">
                            <input type="hidden" name="_method" value="PATCH">
                            <input type="hidden" name="status" value="closed">
                            <button type="submit" class="quick-action">Close</button>
                        </form>
                        {% endif %}
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <div class="empty-state-icon">&gt;_</div>
        <div class="empty-state-title">No issues found</div>
        <p>{% if search_query or status_filter or priority_filter %}Try different filters{% else %}Create your first issue to get started{% endif %}</p>
    </div>
    {% endif %}
</div>
{% endblock %}""")
)

ISSUE_DETAIL_TEMPLATE = (
    BASE_TEMPLATE.replace("{% block title %}IssueDB{% endblock %}", "{% block title %}#{{ issue.id }} {{ issue.title }} - IssueDB{% endblock %}")
    .replace("{% block content %}{% endblock %}", """{% block content %}
{% if message %}
<div class="alert alert-success">{{ message }}</div>
{% endif %}
{% if error %}
<div class="alert alert-error">{{ error }}</div>
{% endif %}

<div class="issue-detail-header">
    <h1 class="issue-detail-title">
        <span class="issue-id" style="font-weight: 400;">#{{ issue.id }}</span>
        {{ issue.title }}
    </h1>
    <div class="issue-detail-meta">
        <span class="badge badge-{{ issue.status.value | replace('-', '-') }}">{{ issue.status.value }}</span>
        <span class="badge badge-{{ issue.priority.value }}">{{ issue.priority.value }}</span>
        <span>Created {{ issue.created_at.strftime('%Y-%m-%d %H:%M') }}</span>
        <span>Updated {{ issue.updated_at.strftime('%Y-%m-%d %H:%M') }}</span>
    </div>
</div>

<div class="issue-detail-body">
    <div>
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Description</h3>
                <a href="/issues/{{ issue.id }}/edit" class="btn btn-sm">Edit</a>
            </div>
            {% if issue.description %}
            <div class="issue-description">{{ issue.description }}</div>
            {% else %}
            <p style="color: var(--text-muted);">No description provided.</p>
            {% endif %}
        </div>

        <div class="comments-section">
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Comments ({{ comments | length }})</h3>
                </div>

                {% for comment in comments %}
                <div class="comment">
                    <div class="comment-header">
                        {{ comment.created_at.strftime('%Y-%m-%d %H:%M') }}
                        <form action="/api/comments/{{ comment.id }}" method="post" style="display: inline; float: right;">
                            <input type="hidden" name="_method" value="DELETE">
                            <button type="submit" class="quick-action" style="color: var(--accent-red);">Delete</button>
                        </form>
                    </div>
                    <div class="comment-body">{{ comment.text }}</div>
                </div>
                {% else %}
                <p style="color: var(--text-muted); padding: 16px 0;">No comments yet.</p>
                {% endfor %}

                <div class="comment-form">
                    <form action="/api/issues/{{ issue.id }}/comments" method="post">
                        <div class="form-group">
                            <textarea name="text" class="form-control" placeholder="Add a comment..." required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary">Add Comment</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div>
        <div class="card">
            <div class="sidebar-section">
                <div class="sidebar-label">Quick Actions</div>
                <div class="quick-actions">
                    {% if issue.status.value == 'open' %}
                    <form action="/api/issues/{{ issue.id }}/start" method="post" style="display: inline;">
                        <button type="submit" class="quick-action">Start</button>
                    </form>
                    <form action="/api/issues/{{ issue.id }}" method="post" style="display: inline;">
                        <input type="hidden" name="_method" value="PATCH">
                        <input type="hidden" name="status" value="in-progress">
                        <button type="submit" class="quick-action">In Progress</button>
                    </form>
                    {% endif %}
                    {% if issue.status.value != 'closed' %}
                    <form action="/api/issues/{{ issue.id }}" method="post" style="display: inline;">
                        <input type="hidden" name="_method" value="PATCH">
                        <input type="hidden" name="status" value="closed">
                        <button type="submit" class="quick-action">Close</button>
                    </form>
                    {% else %}
                    <form action="/api/issues/{{ issue.id }}" method="post" style="display: inline;">
                        <input type="hidden" name="_method" value="PATCH">
                        <input type="hidden" name="status" value="open">
                        <button type="submit" class="quick-action">Reopen</button>
                    </form>
                    {% endif %}
                </div>
            </div>

            <div class="sidebar-section">
                <div class="sidebar-label">Status</div>
                <form action="/api/issues/{{ issue.id }}" method="post">
                    <input type="hidden" name="_method" value="PATCH">
                    <select name="status" class="form-control" onchange="this.form.submit()">
                        <option value="open" {{ 'selected' if issue.status.value == 'open' }}>Open</option>
                        <option value="in-progress" {{ 'selected' if issue.status.value == 'in-progress' }}>In Progress</option>
                        <option value="closed" {{ 'selected' if issue.status.value == 'closed' }}>Closed</option>
                    </select>
                </form>
            </div>

            <div class="sidebar-section">
                <div class="sidebar-label">Priority</div>
                <form action="/api/issues/{{ issue.id }}" method="post">
                    <input type="hidden" name="_method" value="PATCH">
                    <select name="priority" class="form-control" onchange="this.form.submit()">
                        <option value="low" {{ 'selected' if issue.priority.value == 'low' }}>Low</option>
                        <option value="medium" {{ 'selected' if issue.priority.value == 'medium' }}>Medium</option>
                        <option value="high" {{ 'selected' if issue.priority.value == 'high' }}>High</option>
                        <option value="critical" {{ 'selected' if issue.priority.value == 'critical' }}>Critical</option>
                    </select>
                </form>
            </div>

            {% if blockers %}
            <div class="sidebar-section">
                <div class="sidebar-label">Blocked By</div>
                <div class="blockers-list">
                    {% for blocker in blockers %}
                    <div class="blocker-item">
                        <span class="blocker-icon">&#x26D4;</span>
                        <a href="/issues/{{ blocker.id }}">#{{ blocker.id }} {{ blocker.title }}</a>
                        {% if blocker.status.value == 'closed' %}
                        <span class="badge badge-closed" style="margin-left: auto;">closed</span>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            {% if blocking %}
            <div class="sidebar-section">
                <div class="sidebar-label">Blocking</div>
                <div class="blockers-list">
                    {% for blocked in blocking %}
                    <div class="blocker-item">
                        <span style="color: var(--accent-yellow);">&#x2192;</span>
                        <a href="/issues/{{ blocked.id }}">#{{ blocked.id }} {{ blocked.title }}</a>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            {% if code_refs %}
            <div class="sidebar-section">
                <div class="sidebar-label">Code References</div>
                {% for ref in code_refs %}
                <div class="code-ref">
                    <span class="code-ref-path">{{ ref.file_path }}</span>
                    {% if ref.start_line %}
                    <span class="code-ref-lines">
                        :{{ ref.start_line }}{% if ref.end_line %}-{{ ref.end_line }}{% endif %}
                    </span>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <div class="sidebar-section">
                <div class="sidebar-label">Danger Zone</div>
                <form action="/api/issues/{{ issue.id }}" method="post"
                      onsubmit="return confirm('Are you sure you want to delete this issue?')">
                    <input type="hidden" name="_method" value="DELETE">
                    <button type="submit" class="btn btn-danger btn-sm" style="width: 100%;">Delete Issue</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}""")
)

ISSUE_FORM_TEMPLATE = (
    BASE_TEMPLATE.replace("{% block title %}IssueDB{% endblock %}", "{% block title %}{{ 'Edit' if issue else 'New' }} Issue - IssueDB{% endblock %}")
    .replace("{% block content %}{% endblock %}", """{% block content %}
<div class="page-header">
    <h1 class="page-title">{{ 'Edit Issue #' ~ issue.id if issue else 'New Issue' }}</h1>
</div>

{% if error %}
<div class="alert alert-error">{{ error }}</div>
{% endif %}

<div class="card">
    <form action="{{ '/api/issues/' ~ issue.id if issue else '/api/issues' }}" method="post">
        {% if issue %}
        <input type="hidden" name="_method" value="PUT">
        {% endif %}

        <div class="form-group">
            <label class="form-label" for="title">Title *</label>
            <input type="text" id="title" name="title" class="form-control"
                   value="{{ issue.title if issue else '' }}" required
                   placeholder="Brief description of the issue">
        </div>

        <div class="form-group">
            <label class="form-label" for="description">Description</label>
            <textarea id="description" name="description" class="form-control"
                      placeholder="Detailed explanation of the issue...">{{ issue.description if issue else '' }}</textarea>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label class="form-label" for="priority">Priority</label>
                <select id="priority" name="priority" class="form-control">
                    <option value="low" {{ 'selected' if issue and issue.priority.value == 'low' }}>Low</option>
                    <option value="medium" {{ 'selected' if (not issue) or (issue and issue.priority.value == 'medium') }}>Medium</option>
                    <option value="high" {{ 'selected' if issue and issue.priority.value == 'high' }}>High</option>
                    <option value="critical" {{ 'selected' if issue and issue.priority.value == 'critical' }}>Critical</option>
                </select>
            </div>

            <div class="form-group">
                <label class="form-label" for="status">Status</label>
                <select id="status" name="status" class="form-control">
                    <option value="open" {{ 'selected' if (not issue) or (issue and issue.status.value == 'open') }}>Open</option>
                    <option value="in-progress" {{ 'selected' if issue and issue.status.value == 'in-progress' }}>In Progress</option>
                    <option value="closed" {{ 'selected' if issue and issue.status.value == 'closed' }}>Closed</option>
                </select>
            </div>
        </div>

        <div style="display: flex; gap: 12px;">
            <button type="submit" class="btn btn-primary">{{ 'Update Issue' if issue else 'Create Issue' }}</button>
            <a href="{{ '/issues/' ~ issue.id if issue else '/issues' }}" class="btn">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}""")
)


# =============================================================================
# Web Routes (Pages)
# =============================================================================


@app.route("/")
def dashboard() -> str:
    """Dashboard page with summary statistics."""
    repo = get_repo()
    summary = repo.get_summary()
    next_issue = repo.get_next_issue(log_fetch=False)
    recent_issues = repo.list_issues(limit=5)

    active = repo.get_active_issue()
    active_issue = None
    active_started = None
    if active:
        active_issue, started_at = active
        active_started = started_at.strftime("%Y-%m-%d %H:%M")

    return render_template_string(
        DASHBOARD_TEMPLATE,
        active_page="dashboard",
        summary=summary,
        next_issue=next_issue,
        active_issue=active_issue,
        active_started=active_started,
        recent_issues=recent_issues,
    )


@app.route("/issues")
def issues_list() -> str:
    """List all issues with filters."""
    repo = get_repo()

    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    search_query = request.args.get("q")
    message = request.args.get("message")

    if search_query:
        issues = repo.search_issues(search_query)
        # Apply additional filters to search results
        if status_filter:
            issues = [i for i in issues if i.status.value == status_filter]
        if priority_filter:
            issues = [i for i in issues if i.priority.value == priority_filter]
    else:
        issues = repo.list_issues(status=status_filter, priority=priority_filter)

    return render_template_string(
        ISSUES_LIST_TEMPLATE,
        active_page="issues",
        issues=issues,
        status_filter=status_filter,
        priority_filter=priority_filter,
        search_query=search_query,
        message=message,
    )


@app.route("/issues/new")
def issue_new() -> str:
    """New issue form."""
    return render_template_string(
        ISSUE_FORM_TEMPLATE,
        active_page="new",
        issue=None,
        error=request.args.get("error"),
    )


@app.route("/issues/<int:issue_id>")
def issue_detail(issue_id: int) -> Union[str, Response]:
    """Issue detail page."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return redirect(url_for("issues_list", message="Issue not found"))

    comments = repo.get_comments(issue_id)
    blockers = repo.get_blockers(issue_id)
    blocking = repo.get_blocking(issue_id)
    code_refs = repo.get_code_references(issue_id)

    return render_template_string(
        ISSUE_DETAIL_TEMPLATE,
        active_page="issues",
        issue=issue,
        comments=comments,
        blockers=blockers,
        blocking=blocking,
        code_refs=code_refs,
        message=request.args.get("message"),
        error=request.args.get("error"),
    )


@app.route("/issues/<int:issue_id>/edit")
def issue_edit(issue_id: int) -> Union[str, Response]:
    """Edit issue form."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return redirect(url_for("issues_list", message="Issue not found"))

    return render_template_string(
        ISSUE_FORM_TEMPLATE,
        active_page="issues",
        issue=issue,
        error=request.args.get("error"),
    )


# =============================================================================
# API Routes
# =============================================================================


@app.route("/api/issues", methods=["GET"])
def api_list_issues() -> Any:
    """API: List issues."""
    repo = get_repo()

    status = request.args.get("status")
    priority = request.args.get("priority")
    limit = request.args.get("limit", type=int)

    issues = repo.list_issues(status=status, priority=priority, limit=limit)
    return jsonify([i.to_dict() for i in issues])


@app.route("/api/issues", methods=["POST"])
def api_create_issue() -> Any:
    """API: Create a new issue."""
    repo = get_repo()

    # Handle form data or JSON
    data = request.get_json() if request.is_json else request.form.to_dict()

    title = data.get("title", "").strip()
    if not title:
        if request.is_json:
            return jsonify({"error": "Title is required"}), 400
        return redirect(url_for("issue_new", error="Title is required"))

    issue = Issue(
        title=title,
        description=data.get("description"),
        priority=Priority.from_string(data.get("priority", "medium")),
        status=Status.from_string(data.get("status", "open")),
    )

    created = repo.create_issue(issue)

    if request.is_json:
        return jsonify(created.to_dict()), 201
    return redirect(url_for("issue_detail", issue_id=created.id, message="Issue created"))


@app.route("/api/issues/<int:issue_id>", methods=["GET"])
def api_get_issue(issue_id: int) -> Any:
    """API: Get issue by ID."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    return jsonify(issue.to_dict())


@app.route("/api/issues/<int:issue_id>", methods=["POST", "PUT", "PATCH"])
def api_update_issue(issue_id: int) -> Any:
    """API: Update an issue."""
    repo = get_repo()

    # Handle method override for HTML forms
    method = request.form.get("_method", request.method).upper()

    if method == "DELETE":
        return api_delete_issue(issue_id)

    # Handle form data or JSON
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        data.pop("_method", None)

    updates = {}
    if "title" in data and data["title"]:
        updates["title"] = data["title"]
    if "description" in data:
        updates["description"] = data["description"]
    if "priority" in data and data["priority"]:
        updates["priority"] = data["priority"]
    if "status" in data and data["status"]:
        updates["status"] = data["status"]

    if not updates:
        if request.is_json:
            return jsonify({"error": "No updates provided"}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error="No updates provided"))

    updated = repo.update_issue(issue_id, **updates)

    if not updated:
        if request.is_json:
            return jsonify({"error": "Issue not found"}), 404
        return redirect(url_for("issues_list", message="Issue not found"))

    if request.is_json:
        return jsonify(updated.to_dict())
    return redirect(url_for("issue_detail", issue_id=issue_id, message="Issue updated"))


@app.route("/api/issues/<int:issue_id>", methods=["DELETE"])
def api_delete_issue(issue_id: int) -> Any:
    """API: Delete an issue."""
    repo = get_repo()

    deleted = repo.delete_issue(issue_id)

    if not deleted:
        if request.is_json or request.method == "DELETE":
            return jsonify({"error": "Issue not found"}), 404
        return redirect(url_for("issues_list", message="Issue not found"))

    if request.is_json or request.method == "DELETE":
        return jsonify({"message": "Issue deleted"})
    return redirect(url_for("issues_list", message="Issue deleted"))


@app.route("/api/issues/<int:issue_id>/comments", methods=["POST"])
def api_add_comment(issue_id: int) -> Any:
    """API: Add comment to an issue."""
    repo = get_repo()

    data = request.get_json() if request.is_json else request.form.to_dict()

    text = data.get("text", "").strip()
    if not text:
        if request.is_json:
            return jsonify({"error": "Comment text is required"}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error="Comment text is required"))

    try:
        comment = repo.add_comment(issue_id, text)
        if request.is_json:
            return jsonify(comment.to_dict()), 201
        return redirect(url_for("issue_detail", issue_id=issue_id, message="Comment added"))
    except ValueError as e:
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error=str(e)))


@app.route("/api/comments/<int:comment_id>", methods=["POST", "DELETE"])
def api_delete_comment(comment_id: int) -> Any:
    """API: Delete a comment."""
    repo = get_repo()

    # Handle method override for HTML forms
    method = request.form.get("_method", request.method).upper()

    if method != "DELETE":
        return jsonify({"error": "Method not allowed"}), 405

    deleted = repo.delete_comment(comment_id)

    # Get referer for redirect
    referer = request.headers.get("Referer", "/issues")

    if deleted:
        if request.is_json:
            return jsonify({"message": "Comment deleted"})
        return redirect(referer)
    else:
        if request.is_json:
            return jsonify({"error": "Comment not found"}), 404
        return redirect(referer)


@app.route("/api/issues/<int:issue_id>/start", methods=["POST"])
def api_start_issue(issue_id: int) -> Any:
    """API: Start working on an issue."""
    repo = get_repo()

    try:
        issue, started_at = repo.start_issue(issue_id)
        if request.is_json:
            return jsonify({
                "issue": issue.to_dict(),
                "started_at": started_at.isoformat(),
            })
        return redirect(url_for("issue_detail", issue_id=issue_id, message="Started working on issue"))
    except ValueError as e:
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error=str(e)))


@app.route("/api/issues/stop", methods=["POST"])
def api_stop_issue() -> Any:
    """API: Stop working on active issue."""
    repo = get_repo()

    close = request.args.get("close") == "1"

    result = repo.stop_issue(close=close)

    if result:
        issue, started_at, stopped_at = result
        if request.is_json:
            return jsonify({
                "issue": issue.to_dict(),
                "started_at": started_at.isoformat(),
                "stopped_at": stopped_at.isoformat(),
            })
        return redirect(url_for("dashboard"))
    else:
        if request.is_json:
            return jsonify({"error": "No active issue"}), 400
        return redirect(url_for("dashboard"))


@app.route("/api/summary", methods=["GET"])
def api_summary() -> Any:
    """API: Get summary statistics."""
    repo = get_repo()
    return jsonify(repo.get_summary())


@app.route("/api/next", methods=["GET"])
def api_next_issue() -> Any:
    """API: Get next issue to work on."""
    repo = get_repo()
    issue = repo.get_next_issue()

    if issue:
        return jsonify(issue.to_dict())
    return jsonify(None)


def run_server(
    host: str = "0.0.0.0",
    port: int = 7760,
    debug: bool = False,
) -> None:
    """Run the Flask development server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Enable debug mode.
    """
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
