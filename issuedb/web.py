"""Flask Web UI and API for IssueDB."""

from typing import Any, Union

from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from werkzeug.wrappers import Response

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository
from issuedb.similarity import find_similar_issues

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
            --bg-accent: #1f2937;
            --border-color: #30363d;
            --border-light: #21262d;
            --border-focus: #58a6ff;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-orange: #db6d28;
            --accent-red: #f85149;
            --accent-purple: #a371f7;
            --accent-cyan: #39d5ff;
            --status-open: #3fb950;
            --status-progress: #d29922;
            --status-closed: #8b949e;
            --priority-low: #8b949e;
            --priority-medium: #58a6ff;
            --priority-high: #d29922;
            --priority-critical: #f85149;
            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
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
            transition: color 0.15s ease;
        }

        a:hover {
            color: var(--accent-cyan);
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
            backdrop-filter: blur(10px);
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

        .logo:hover {
            color: var(--text-primary);
        }

        .logo-icon {
            color: var(--accent-green);
            font-weight: 700;
        }

        .nav {
            display: flex;
            gap: 8px;
        }

        .nav a {
            color: var(--text-secondary);
            font-size: 13px;
            padding: 8px 16px;
            border-radius: 6px;
            transition: all 0.15s ease;
        }

        .nav a:hover {
            color: var(--text-primary);
            background-color: var(--bg-tertiary);
        }

        .nav a.active {
            color: var(--text-primary);
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
        }

        /* Main content */
        .main {
            padding: 32px 0;
            min-height: calc(100vh - 140px);
        }

        .page-header {
            margin-bottom: 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }

        .page-title {
            font-size: 26px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }

        .page-subtitle {
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 18px;
            font-family: inherit;
            font-size: 13px;
            font-weight: 500;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.15s ease;
            white-space: nowrap;
        }

        .btn:hover {
            background-color: var(--bg-hover);
            border-color: var(--text-muted);
        }

        .btn-primary {
            background-color: var(--accent-green);
            border-color: var(--accent-green);
            color: #000;
            font-weight: 600;
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
            padding: 6px 12px;
            font-size: 12px;
        }

        .btn-ghost {
            background-color: transparent;
            border-color: transparent;
        }

        .btn-ghost:hover {
            background-color: var(--bg-tertiary);
            border-color: var(--border-color);
        }

        /* Cards */
        .card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 20px;
            box-shadow: var(--shadow-sm);
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-light);
            background-color: var(--bg-tertiary);
        }

        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-body {
            padding: 20px;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 28px;
        }

        @media (max-width: 1000px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 600px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }

        .stat-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            transition: all 0.2s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }

        .stat-card:hover {
            border-color: var(--accent-blue);
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }

        .stat-card-link {
            position: absolute;
            inset: 0;
            z-index: 1;
        }

        .stat-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 36px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -1px;
        }

        .stat-breakdown {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--border-light);
        }

        .stat-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            font-size: 13px;
        }

        .stat-item a {
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .stat-item a:hover {
            color: var(--text-primary);
        }

        .stat-item-value {
            font-weight: 600;
            color: var(--text-primary);
        }

        .stat-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        /* Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
            border-radius: 16px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .badge-open {
            background-color: rgba(63, 185, 80, 0.15);
            color: var(--status-open);
            border: 1px solid rgba(63, 185, 80, 0.4);
        }

        .badge-in-progress {
            background-color: rgba(210, 153, 34, 0.15);
            color: var(--status-progress);
            border: 1px solid rgba(210, 153, 34, 0.4);
        }

        .badge-closed {
            background-color: rgba(139, 148, 158, 0.15);
            color: var(--status-closed);
            border: 1px solid rgba(139, 148, 158, 0.4);
        }

        .badge-low {
            background-color: rgba(139, 148, 158, 0.15);
            color: var(--priority-low);
            border: 1px solid rgba(139, 148, 158, 0.4);
        }

        .badge-medium {
            background-color: rgba(88, 166, 255, 0.15);
            color: var(--priority-medium);
            border: 1px solid rgba(88, 166, 255, 0.4);
        }

        .badge-high {
            background-color: rgba(210, 153, 34, 0.15);
            color: var(--priority-high);
            border: 1px solid rgba(210, 153, 34, 0.4);
        }

        .badge-critical {
            background-color: rgba(248, 81, 73, 0.15);
            color: var(--priority-critical);
            border: 1px solid rgba(248, 81, 73, 0.4);
        }

        /* Issue Table */
        .issue-table {
            width: 100%;
            border-collapse: collapse;
        }

        .issue-table th,
        .issue-table td {
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-light);
        }

        .issue-table th {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background-color: var(--bg-tertiary);
        }

        .issue-table tbody tr {
            transition: background-color 0.1s ease;
        }

        .issue-table tbody tr:hover {
            background-color: var(--bg-tertiary);
        }

        .issue-id {
            color: var(--text-muted);
            font-weight: 600;
            font-size: 13px;
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
            color: var(--text-muted);
            margin-top: 4px;
        }

        /* Filters */
        .filters {
            display: flex;
            gap: 12px;
            padding: 16px 20px;
            flex-wrap: wrap;
            align-items: center;
            background-color: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-light);
        }

        .filter-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .filter-label {
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 500;
        }

        select, input[type="text"], input[type="search"], textarea {
            font-family: inherit;
            font-size: 13px;
            padding: 8px 12px;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        select:focus, input:focus, textarea:focus {
            outline: none;
            border-color: var(--border-focus);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
        }

        .search-input {
            min-width: 280px;
        }

        /* Forms */
        .form-group {
            margin-bottom: 24px;
        }

        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        .form-control {
            width: 100%;
            padding: 12px 14px;
            font-family: inherit;
            font-size: 14px;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        .form-control:focus {
            outline: none;
            border-color: var(--border-focus);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
        }

        .form-control::placeholder {
            color: var(--text-muted);
        }

        textarea.form-control {
            min-height: 150px;
            resize: vertical;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        /* Issue Detail */
        .issue-detail-header {
            margin-bottom: 28px;
        }

        .issue-detail-title {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 16px;
            line-height: 1.3;
        }

        .issue-detail-meta {
            display: flex;
            gap: 12px;
            align-items: center;
            color: var(--text-secondary);
            font-size: 13px;
            flex-wrap: wrap;
        }

        .issue-detail-body {
            display: grid;
            grid-template-columns: 1fr 340px;
            gap: 24px;
        }

        @media (max-width: 1000px) {
            .issue-detail-body {
                grid-template-columns: 1fr;
            }
        }

        .issue-description {
            white-space: pre-wrap;
            line-height: 1.8;
            color: var(--text-secondary);
        }

        /* Sidebar */
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .sidebar-section {
            padding: 16px;
        }

        .sidebar-section:not(:last-child) {
            border-bottom: 1px solid var(--border-light);
        }

        .sidebar-label {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            margin-bottom: 12px;
        }

        /* Comments */
        .comments-section {
            margin-top: 24px;
        }

        .comment {
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }

        .comment-header {
            padding: 10px 16px;
            background-color: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-light);
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .comment-body {
            padding: 16px;
            white-space: pre-wrap;
            line-height: 1.7;
        }

        .comment-form {
            margin-top: 16px;
        }

        /* Audit Log */
        .audit-log {
            max-height: 300px;
            overflow-y: auto;
        }

        .audit-entry {
            padding: 10px 0;
            border-bottom: 1px solid var(--border-light);
            font-size: 12px;
        }

        .audit-entry:last-child {
            border-bottom: none;
        }

        .audit-action {
            font-weight: 600;
            color: var(--accent-blue);
            margin-right: 8px;
        }

        .audit-field {
            color: var(--accent-purple);
        }

        .audit-value {
            color: var(--text-muted);
            font-style: italic;
        }

        .audit-time {
            color: var(--text-muted);
            font-size: 11px;
            margin-top: 4px;
        }

        /* Similar Issues */
        .similar-issue {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-light);
        }

        .similar-issue:last-child {
            border-bottom: none;
        }

        .similar-score {
            font-size: 11px;
            font-weight: 600;
            color: var(--accent-yellow);
            background-color: rgba(210, 153, 34, 0.15);
            padding: 2px 8px;
            border-radius: 10px;
        }

        /* Time Tracking */
        .time-entry {
            padding: 10px 0;
            border-bottom: 1px solid var(--border-light);
            font-size: 12px;
        }

        .time-entry:last-child {
            border-bottom: none;
        }

        .time-duration {
            font-weight: 600;
            color: var(--accent-green);
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 48px 20px;
            color: var(--text-secondary);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.3;
            color: var(--text-muted);
        }

        .empty-state-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        /* Alert messages */
        .alert {
            padding: 14px 18px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .alert-success {
            background-color: rgba(63, 185, 80, 0.1);
            border: 1px solid rgba(63, 185, 80, 0.3);
            color: var(--accent-green);
        }

        .alert-error {
            background-color: rgba(248, 81, 73, 0.1);
            border: 1px solid rgba(248, 81, 73, 0.3);
            color: var(--accent-red);
        }

        /* Progress bar */
        .progress-bar {
            height: 6px;
            background-color: var(--bg-tertiary);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 12px;
        }

        .progress-fill {
            height: 100%;
            border-radius: 3px;
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
            margin-top: 16px;
        }

        /* Quick actions */
        .quick-actions {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }

        .quick-action {
            padding: 6px 12px;
            font-size: 11px;
            font-weight: 500;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            cursor: pointer;
            color: var(--text-secondary);
            transition: all 0.15s ease;
            font-family: inherit;
        }

        .quick-action:hover {
            background-color: var(--bg-hover);
            color: var(--text-primary);
            border-color: var(--text-muted);
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
            font-size: 12px;
        }

        .blocker-icon {
            font-size: 14px;
        }

        /* Code refs */
        .code-ref {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background-color: var(--bg-tertiary);
            border-radius: 6px;
            font-size: 12px;
            margin-top: 8px;
            border: 1px solid var(--border-light);
        }

        .code-ref-path {
            color: var(--accent-cyan);
            font-weight: 500;
        }

        .code-ref-lines {
            color: var(--text-muted);
        }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
        }

        .tab {
            padding: 12px 20px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
            border-bottom: 2px solid transparent;
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .tab:hover {
            color: var(--text-primary);
        }

        .tab.active {
            color: var(--text-primary);
            border-bottom-color: var(--accent-blue);
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

        /* Dashboard cards grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }

        @media (max-width: 1000px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-tertiary);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        /* Collapsible sections */
        .collapsible-header {
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .collapsible-content {
            max-height: 400px;
            overflow-y: auto;
        }

        /* Issue number link */
        .issue-num {
            color: var(--text-muted);
            font-weight: 500;
        }

        .issue-num:hover {
            color: var(--accent-blue);
        }

        /* Loading placeholder */
        .loading-placeholder {
            color: var(--text-muted);
            font-style: italic;
            padding: 12px 0;
        }

        @keyframes pulse {
            0%, 100% { opacity: 0.6; }
            50% { opacity: 1; }
        }

        .loading-placeholder {
            animation: pulse 1.5s ease-in-out infinite;
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
                    <a href="/audit" class="{{ 'active' if active_page == 'audit' else '' }}">Audit Log</a>
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
            IssueDB v2.5.3 &middot; Command-line issue tracking for developers
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
    <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">Issue tracking overview</p>
    </div>
    <a href="/issues/new" class="btn btn-primary">+ New Issue</a>
</div>

<div class="stats-grid">
    <div class="stat-card">
        <a href="/issues" class="stat-card-link"></a>
        <div class="stat-label">Total Issues</div>
        <div class="stat-value">{{ summary.total_issues }}</div>
    </div>

    <div class="stat-card">
        <a href="/issues?status=open" class="stat-card-link"></a>
        <div class="stat-label">Open</div>
        <div class="stat-value" style="color: var(--status-open)">{{ summary.by_status.open }}</div>
        <div class="progress-bar">
            <div class="progress-fill progress-green" style="width: {{ summary.status_percentages.open | default(0) }}%"></div>
        </div>
    </div>

    <div class="stat-card">
        <a href="/issues?status=in-progress" class="stat-card-link"></a>
        <div class="stat-label">In Progress</div>
        <div class="stat-value" style="color: var(--status-progress)">{{ summary.by_status.in_progress }}</div>
        <div class="progress-bar">
            <div class="progress-fill progress-yellow" style="width: {{ summary.status_percentages['in-progress'] | default(0) }}%"></div>
        </div>
    </div>

    <div class="stat-card">
        <a href="/issues?status=closed" class="stat-card-link"></a>
        <div class="stat-label">Closed</div>
        <div class="stat-value" style="color: var(--status-closed)">{{ summary.by_status.closed }}</div>
        <div class="progress-bar">
            <div class="progress-fill progress-gray" style="width: {{ summary.status_percentages.closed | default(0) }}%"></div>
        </div>
    </div>
</div>

<div class="dashboard-grid">
    <div class="card">
        <div class="card-header">
            <h3 class="card-title">Priority Breakdown</h3>
        </div>
        <div class="card-body">
            <div class="stat-item">
                <a href="/issues?priority=critical">
                    <span class="stat-dot" style="background-color: var(--priority-critical)"></span>
                    Critical
                </a>
                <span class="stat-item-value">{{ summary.by_priority.critical }}</span>
            </div>
            <div class="stat-item">
                <a href="/issues?priority=high">
                    <span class="stat-dot" style="background-color: var(--priority-high)"></span>
                    High
                </a>
                <span class="stat-item-value">{{ summary.by_priority.high }}</span>
            </div>
            <div class="stat-item">
                <a href="/issues?priority=medium">
                    <span class="stat-dot" style="background-color: var(--priority-medium)"></span>
                    Medium
                </a>
                <span class="stat-item-value">{{ summary.by_priority.medium }}</span>
            </div>
            <div class="stat-item">
                <a href="/issues?priority=low">
                    <span class="stat-dot" style="background-color: var(--priority-low)"></span>
                    Low
                </a>
                <span class="stat-item-value">{{ summary.by_priority.low }}</span>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <h3 class="card-title">Next Issue</h3>
        </div>
        <div class="card-body">
            {% if next_issue %}
            <div class="issue-title" style="margin-bottom: 8px;">
                <a href="/issues/{{ next_issue.id }}">#{{ next_issue.id }} {{ next_issue.title }}</a>
            </div>
            <div style="display: flex; gap: 6px; margin-bottom: 12px;">
                <span class="badge badge-{{ next_issue.priority.value }}">{{ next_issue.priority.value }}</span>
                <span class="badge badge-{{ next_issue.status.value | replace('-', '-') }}">{{ next_issue.status.value }}</span>
            </div>
            <form action="/api/issues/{{ next_issue.id }}/start" method="post">
                <button type="submit" class="btn btn-primary btn-sm">Start Working</button>
            </form>
            {% else %}
            <div class="empty-state" style="padding: 20px 0;">
                <p style="color: var(--text-muted);">No open issues</p>
            </div>
            {% endif %}
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <h3 class="card-title">Active Issue</h3>
        </div>
        <div class="card-body">
            {% if active_issue %}
            <div class="issue-title" style="margin-bottom: 8px;">
                <a href="/issues/{{ active_issue.id }}">#{{ active_issue.id }} {{ active_issue.title }}</a>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">
                Started: {{ active_started | default('N/A') }}
            </div>
            <div class="action-row" style="margin-top: 0;">
                <form action="/api/issues/stop" method="post" style="display: inline;">
                    <button type="submit" class="btn btn-sm">Stop</button>
                </form>
                <form action="/api/issues/stop?close=1" method="post" style="display: inline;">
                    <button type="submit" class="btn btn-sm btn-primary">Stop & Close</button>
                </form>
            </div>
            {% else %}
            <div class="empty-state" style="padding: 20px 0;">
                <p style="color: var(--text-muted);">No active issue</p>
            </div>
            {% endif %}
        </div>
    </div>
</div>

<div class="card">
    <div class="card-header">
        <h3 class="card-title">Recent Issues</h3>
        <a href="/issues" class="btn btn-sm btn-ghost">View All</a>
    </div>
    {% if recent_issues %}
    <table class="issue-table">
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Title</th>
                <th style="width: 110px;">Status</th>
                <th style="width: 100px;">Priority</th>
                <th style="width: 150px;">Created</th>
            </tr>
        </thead>
        <tbody>
            {% for issue in recent_issues %}
            <tr>
                <td><a href="/issues/{{ issue.id }}" class="issue-num">#{{ issue.id }}</a></td>
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
    <div>
        <h1 class="page-title">Issues</h1>
        <p class="page-subtitle">{{ issues | length }} issue{% if issues | length != 1 %}s{% endif %}{% if status_filter or priority_filter or search_query %} found{% endif %}</p>
    </div>
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
        <div class="filter-group" style="flex: 1;">
            <input type="search" name="q" placeholder="Search issues..."
                   value="{{ search_query | default('') }}" class="search-input">
            <button type="submit" class="btn btn-sm">Search</button>
        </div>
        {% if status_filter or priority_filter or search_query %}
        <a href="/issues" class="btn btn-sm btn-ghost">Clear Filters</a>
        {% endif %}
    </form>

    {% if issues %}
    <table class="issue-table">
        <thead>
            <tr>
                <th style="width: 70px;">ID</th>
                <th>Title</th>
                <th style="width: 110px;">Status</th>
                <th style="width: 100px;">Priority</th>
                <th style="width: 150px;">Created</th>
                <th style="width: 120px;">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for issue in issues %}
            <tr>
                <td><a href="/issues/{{ issue.id }}" class="issue-num">#{{ issue.id }}</a></td>
                <td class="issue-title">
                    <a href="/issues/{{ issue.id }}">{{ issue.title }}</a>
                    {% if issue.description %}
                    <div class="issue-meta">{{ issue.description[:100] }}{% if issue.description|length > 100 %}...{% endif %}</div>
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
        <span style="color: var(--text-muted); font-weight: 400;">#{{ issue.id }}</span>
        {{ issue.title }}
    </h1>
    <div class="issue-detail-meta">
        <span class="badge badge-{{ issue.status.value | replace('-', '-') }}">{{ issue.status.value }}</span>
        <span class="badge badge-{{ issue.priority.value }}">{{ issue.priority.value }}</span>
        <span>Created {{ issue.created_at.strftime('%Y-%m-%d %H:%M') }}</span>
        <span>&middot;</span>
        <span>Updated {{ issue.updated_at.strftime('%Y-%m-%d %H:%M') }}</span>
    </div>
</div>

<div class="issue-detail-body">
    <div>
        <!-- Description Card -->
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Description</h3>
                <a href="/issues/{{ issue.id }}/edit" class="btn btn-sm btn-ghost">Edit</a>
            </div>
            <div class="card-body">
                {% if issue.description %}
                <div class="issue-description">{{ issue.description }}</div>
                {% else %}
                <p style="color: var(--text-muted); font-style: italic;">No description provided.</p>
                {% endif %}
            </div>
        </div>

        <!-- Similar Issues Card (async loaded) -->
        <div class="card" id="similar-card" style="display: none;">
            <div class="card-header">
                <h3 class="card-title">Similar Issues</h3>
            </div>
            <div class="card-body" id="similar-content">
                <div class="loading-placeholder">Loading similar issues...</div>
            </div>
        </div>

        <!-- Comments Card (async loaded) -->
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Comments <span id="comments-count"></span></h3>
            </div>
            <div class="card-body">
                <div id="comments-content">
                    <div class="loading-placeholder">Loading comments...</div>
                </div>
                <div class="comment-form">
                    <form action="/api/issues/{{ issue.id }}/comments" method="post">
                        <div class="form-group" style="margin-bottom: 12px;">
                            <textarea name="text" class="form-control" placeholder="Add a comment..." required style="min-height: 100px;"></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary btn-sm">Add Comment</button>
                    </form>
                </div>
            </div>
        </div>

        <!-- Audit Log Card (async loaded) -->
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Audit History</h3>
                <a href="/audit?issue_id={{ issue.id }}" class="btn btn-sm btn-ghost">View All</a>
            </div>
            <div class="card-body">
                <div id="audit-content">
                    <div class="loading-placeholder">Loading audit history...</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="card">
            <div class="sidebar-section">
                <div class="sidebar-label">Quick Actions</div>
                <div class="quick-actions">
                    {% if issue.status.value == 'open' %}
                    <form action="/api/issues/{{ issue.id }}/start" method="post" style="display: inline;">
                        <button type="submit" class="quick-action" style="background-color: var(--accent-green); color: #000; border-color: var(--accent-green);">Start</button>
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
                    <a href="/issues/{{ issue.id }}/edit" class="quick-action">Edit</a>
                </div>
            </div>

            <div class="sidebar-section">
                <div class="sidebar-label">Status</div>
                <form action="/api/issues/{{ issue.id }}" method="post">
                    <input type="hidden" name="_method" value="PATCH">
                    <select name="status" class="form-control" onchange="this.form.submit()" style="font-size: 13px;">
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
                    <select name="priority" class="form-control" onchange="this.form.submit()" style="font-size: 13px;">
                        <option value="low" {{ 'selected' if issue.priority.value == 'low' }}>Low</option>
                        <option value="medium" {{ 'selected' if issue.priority.value == 'medium' }}>Medium</option>
                        <option value="high" {{ 'selected' if issue.priority.value == 'high' }}>High</option>
                        <option value="critical" {{ 'selected' if issue.priority.value == 'critical' }}>Critical</option>
                    </select>
                </form>
            </div>

            <!-- Dependencies (async loaded) -->
            <div id="dependencies-section"></div>

            <!-- Code References (async loaded) -->
            <div id="coderefs-section"></div>

            <!-- Time Tracking (async loaded) -->
            <div id="time-section"></div>

            <div class="sidebar-section">
                <div class="sidebar-label" style="color: var(--accent-red);">Danger Zone</div>
                <form action="/api/issues/{{ issue.id }}" method="post"
                      onsubmit="return confirm('Are you sure you want to delete this issue? This cannot be undone.')">
                    <input type="hidden" name="_method" value="DELETE">
                    <button type="submit" class="btn btn-danger btn-sm" style="width: 100%;">Delete Issue</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}""")
    .replace("{% block scripts %}{% endblock %}", """{% block scripts %}
<script>
(function() {
    var issueId = {{ issue.id }};
    var baseUrl = '/api/issues/' + issueId;

    function truncate(str, len) {
        if (!str) return '';
        return str.length > len ? str.substring(0, len) + '...' : str;
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Load comments
    fetch(baseUrl + '/comments')
        .then(function(r) { return r.json(); })
        .then(function(comments) {
            var countEl = document.getElementById('comments-count');
            var contentEl = document.getElementById('comments-content');
            countEl.textContent = '(' + comments.length + ')';
            if (comments.length === 0) {
                contentEl.innerHTML = '<p style="color: var(--text-muted); font-style: italic;">No comments yet.</p>';
            } else {
                var html = '';
                for (var i = 0; i < comments.length; i++) {
                    var c = comments[i];
                    html += '<div class="comment">' +
                        '<div class="comment-header">' +
                        '<span>' + c.created_at.replace('T', ' ').substring(0, 16) + '</span>' +
                        '<form action="/api/comments/' + c.id + '" method="post" style="display: inline;">' +
                        '<input type="hidden" name="_method" value="DELETE">' +
                        '<button type="submit" class="quick-action" style="color: var(--accent-red); font-size: 11px;">Delete</button>' +
                        '</form></div>' +
                        '<div class="comment-body">' + escapeHtml(c.text) + '</div></div>';
                }
                contentEl.innerHTML = html;
            }
        })
        .catch(function() {
            document.getElementById('comments-content').innerHTML = '<p style="color: var(--accent-red);">Failed to load comments</p>';
        });

    // Load similar issues
    fetch(baseUrl + '/similar?limit=5')
        .then(function(r) { return r.json(); })
        .then(function(similar) {
            var card = document.getElementById('similar-card');
            var content = document.getElementById('similar-content');
            if (similar.length > 0) {
                card.style.display = 'block';
                var html = '';
                for (var i = 0; i < similar.length; i++) {
                    var s = similar[i];
                    var statusClass = 'badge-' + s.issue.status.replace('-', '-');
                    html += '<div class="similar-issue">' +
                        '<div><a href="/issues/' + s.issue.id + '">#' + s.issue.id + ' ' + escapeHtml(s.issue.title) + '</a>' +
                        '<div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">' +
                        '<span class="badge ' + statusClass + '" style="font-size: 10px;">' + s.issue.status + '</span></div></div>' +
                        '<span class="similar-score">' + Math.round(s.score * 100) + '%</span></div>';
                }
                content.innerHTML = html;
            }
        })
        .catch(function() {});

    // Load audit logs
    fetch(baseUrl + '/audit')
        .then(function(r) { return r.json(); })
        .then(function(logs) {
            var content = document.getElementById('audit-content');
            if (logs.length === 0) {
                content.innerHTML = '<p style="color: var(--text-muted); font-style: italic;">No audit history.</p>';
            } else {
                var html = '<div class="audit-log">';
                var limit = Math.min(logs.length, 10);
                for (var i = 0; i < limit; i++) {
                    var log = logs[i];
                    html += '<div class="audit-entry"><span class="audit-action">' + log.action + '</span>';
                    if (log.field_name) {
                        html += '<span class="audit-field">' + log.field_name + '</span>: ';
                        if (log.old_value) html += '<span class="audit-value">' + truncate(log.old_value, 30) + '</span> &rarr; ';
                        html += '<span class="audit-value">' + (log.new_value ? truncate(log.new_value, 30) : 'null') + '</span>';
                    }
                    html += '<div class="audit-time">' + log.timestamp.replace('T', ' ') + '</div></div>';
                }
                html += '</div>';
                content.innerHTML = html;
            }
        })
        .catch(function() {
            document.getElementById('audit-content').innerHTML = '<p style="color: var(--accent-red);">Failed to load audit history</p>';
        });

    // Load dependencies
    fetch(baseUrl + '/dependencies')
        .then(function(r) { return r.json(); })
        .then(function(deps) {
            var section = document.getElementById('dependencies-section');
            var html = '';
            if (deps.blockers && deps.blockers.length > 0) {
                html += '<div class="sidebar-section"><div class="sidebar-label" style="color: var(--accent-red);">Blocked By</div><div class="blockers-list">';
                for (var i = 0; i < deps.blockers.length; i++) {
                    var b = deps.blockers[i];
                    html += '<div class="blocker-item"><span class="blocker-icon" style="color: var(--accent-red);">&#x26D4;</span>' +
                        '<a href="/issues/' + b.id + '">#' + b.id + ' ' + truncate(b.title, 25) + '</a>';
                    if (b.status === 'closed') html += '<span class="badge badge-closed" style="margin-left: auto; font-size: 9px;">done</span>';
                    html += '</div>';
                }
                html += '</div></div>';
            }
            if (deps.blocking && deps.blocking.length > 0) {
                html += '<div class="sidebar-section"><div class="sidebar-label" style="color: var(--accent-yellow);">Blocking</div><div class="blockers-list">';
                for (var i = 0; i < deps.blocking.length; i++) {
                    var b = deps.blocking[i];
                    html += '<div class="blocker-item"><span style="color: var(--accent-yellow);">&#x2192;</span>' +
                        '<a href="/issues/' + b.id + '">#' + b.id + ' ' + truncate(b.title, 25) + '</a></div>';
                }
                html += '</div></div>';
            }
            section.innerHTML = html;
        })
        .catch(function() {});

    // Load code references
    fetch(baseUrl + '/refs')
        .then(function(r) { return r.json(); })
        .then(function(refs) {
            var section = document.getElementById('coderefs-section');
            if (refs.length > 0) {
                var html = '<div class="sidebar-section"><div class="sidebar-label">Code References</div>';
                for (var i = 0; i < refs.length; i++) {
                    var ref = refs[i];
                    html += '<div class="code-ref"><span class="code-ref-path">' + escapeHtml(ref.file_path) + '</span>';
                    if (ref.start_line) {
                        html += '<span class="code-ref-lines">:' + ref.start_line;
                        if (ref.end_line) html += '-' + ref.end_line;
                        html += '</span>';
                    }
                    html += '</div>';
                }
                html += '</div>';
                section.innerHTML = html;
            }
        })
        .catch(function() {});

    // Load time tracking
    fetch(baseUrl + '/time')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var section = document.getElementById('time-section');
            if (data.entries && data.entries.length > 0) {
                var html = '<div class="sidebar-section"><div class="sidebar-label">Time Tracking</div>' +
                    '<div style="font-size: 24px; font-weight: 600; color: var(--accent-green); margin-bottom: 12px;">' + data.total_formatted + '</div>' +
                    '<div class="collapsible-content" style="max-height: 150px;">';
                var limit = Math.min(data.entries.length, 5);
                for (var i = 0; i < limit; i++) {
                    var e = data.entries[i];
                    html += '<div class="time-entry"><span class="time-duration">' + e.duration_formatted + '</span>';
                    if (e.note) html += '<span style="color: var(--text-muted);"> - ' + truncate(e.note, 20) + '</span>';
                    html += '<div style="font-size: 10px; color: var(--text-muted);">' + e.started_at + '</div></div>';
                }
                html += '</div></div>';
                section.innerHTML = html;
            }
        })
        .catch(function() {});
})();
</script>
{% endblock %}""")
)

ISSUE_FORM_TEMPLATE = (
    BASE_TEMPLATE.replace("{% block title %}IssueDB{% endblock %}", "{% block title %}{{ 'Edit' if issue else 'New' }} Issue - IssueDB{% endblock %}")
    .replace("{% block content %}{% endblock %}", """{% block content %}
<div class="page-header">
    <div>
        <h1 class="page-title">{{ 'Edit Issue #' ~ issue.id if issue else 'New Issue' }}</h1>
        <p class="page-subtitle">{{ 'Update issue details' if issue else 'Create a new issue to track' }}</p>
    </div>
</div>

{% if error %}
<div class="alert alert-error">{{ error }}</div>
{% endif %}

<div class="card">
    <div class="card-body">
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

            <div style="display: flex; gap: 12px; margin-top: 8px;">
                <button type="submit" class="btn btn-primary">{{ 'Update Issue' if issue else 'Create Issue' }}</button>
                <a href="{{ '/issues/' ~ issue.id if issue else '/issues' }}" class="btn">Cancel</a>
            </div>
        </form>
    </div>
</div>
{% endblock %}""")
)

AUDIT_LOG_TEMPLATE = (
    BASE_TEMPLATE.replace("{% block title %}IssueDB{% endblock %}", "{% block title %}Audit Log - IssueDB{% endblock %}")
    .replace("{% block content %}{% endblock %}", """{% block content %}
<div class="page-header">
    <div>
        <h1 class="page-title">Audit Log</h1>
        <p class="page-subtitle">Complete history of all changes{% if issue_filter %} for issue #{{ issue_filter }}{% endif %}</p>
    </div>
    {% if issue_filter %}
    <a href="/audit" class="btn btn-sm">View All</a>
    {% endif %}
</div>

<div class="card">
    {% if logs %}
    <table class="issue-table">
        <thead>
            <tr>
                <th style="width: 80px;">Issue</th>
                <th style="width: 120px;">Action</th>
                <th style="width: 120px;">Field</th>
                <th>Old Value</th>
                <th>New Value</th>
                <th style="width: 160px;">Timestamp</th>
            </tr>
        </thead>
        <tbody>
            {% for log in logs %}
            <tr>
                <td><a href="/issues/{{ log.issue_id }}" class="issue-num">#{{ log.issue_id }}</a></td>
                <td><span class="audit-action" style="margin: 0;">{{ log.action }}</span></td>
                <td>{% if log.field_name %}<span class="audit-field">{{ log.field_name }}</span>{% else %}-{% endif %}</td>
                <td class="issue-meta">{{ log.old_value[:50] if log.old_value else '-' }}{% if log.old_value and log.old_value|length > 50 %}...{% endif %}</td>
                <td class="issue-meta">{{ log.new_value[:50] if log.new_value else '-' }}{% if log.new_value and log.new_value|length > 50 %}...{% endif %}</td>
                <td class="issue-meta">{{ log.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <div class="empty-state-icon">&gt;_</div>
        <div class="empty-state-title">No audit logs</div>
        <p>Changes will be recorded here</p>
    </div>
    {% endif %}
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
    """Issue detail page - loads basic info, async fetches the rest."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return redirect(url_for("issues_list", message="Issue not found"))

    # Only load basic issue info - everything else loads async via JS
    return render_template_string(
        ISSUE_DETAIL_TEMPLATE,
        active_page="issues",
        issue=issue,
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


@app.route("/audit")
def audit_log_page() -> str:
    """Audit log page."""
    repo = get_repo()
    issue_filter = request.args.get("issue_id", type=int)
    logs = repo.get_audit_logs(issue_id=issue_filter)

    return render_template_string(
        AUDIT_LOG_TEMPLATE,
        active_page="audit",
        logs=logs[:100],  # Limit to 100 entries
        issue_filter=issue_filter,
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


@app.route("/api/issues/<int:issue_id>/similar", methods=["GET"])
def api_similar_issues(issue_id: int) -> Any:
    """API: Find similar issues."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    threshold = request.args.get("threshold", 0.4, type=float)
    limit = request.args.get("limit", 10, type=int)

    all_issues = repo.list_issues()
    other_issues = [i for i in all_issues if i.id != issue_id]
    issue_text = f"{issue.title} {issue.description or ''}"

    similar_results = find_similar_issues(issue_text, other_issues, threshold=threshold)

    return jsonify([
        {"issue": i.to_dict(), "score": round(score, 3)}
        for i, score in similar_results[:limit]
    ])


@app.route("/api/issues/<int:issue_id>/audit", methods=["GET"])
def api_issue_audit(issue_id: int) -> Any:
    """API: Get audit logs for an issue."""
    repo = get_repo()
    logs = repo.get_audit_logs(issue_id)

    return jsonify([
        {
            "id": log.id,
            "issue_id": log.issue_id,
            "action": log.action,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ])


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


@app.route("/api/audit", methods=["GET"])
def api_audit_logs() -> Any:
    """API: Get all audit logs."""
    repo = get_repo()
    issue_id = request.args.get("issue_id", type=int)
    logs = repo.get_audit_logs(issue_id=issue_id)

    return jsonify([
        {
            "id": log.id,
            "issue_id": log.issue_id,
            "action": log.action,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ])


@app.route("/api/issues/<int:issue_id>/comments", methods=["GET"])
def api_get_comments(issue_id: int) -> Any:
    """API: Get comments for an issue."""
    repo = get_repo()
    comments = repo.get_comments(issue_id)
    return jsonify([c.to_dict() for c in comments])


@app.route("/api/issues/<int:issue_id>/time", methods=["GET"])
def api_get_time_entries(issue_id: int) -> Any:
    """API: Get time entries for an issue."""
    repo = get_repo()
    entries = repo.get_time_entries(issue_id)
    result = []
    total_seconds = 0
    for entry in entries:
        e = dict(entry)
        if e.get("duration_seconds"):
            total_seconds += e["duration_seconds"]
            hours = e["duration_seconds"] // 3600
            minutes = (e["duration_seconds"] % 3600) // 60
            e["duration_formatted"] = f"{hours}h {minutes}m" if hours else f"{minutes}m"
        else:
            e["duration_formatted"] = "running..."
        result.append(e)
    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60
    return jsonify({
        "entries": result,
        "total_formatted": f"{total_hours}h {total_minutes}m" if total_hours else f"{total_minutes}m",
        "total_seconds": total_seconds,
    })


@app.route("/api/issues/<int:issue_id>/dependencies", methods=["GET"])
def api_get_dependencies(issue_id: int) -> Any:
    """API: Get dependencies (blockers/blocking) for an issue."""
    repo = get_repo()
    blockers = repo.get_blockers(issue_id)
    blocking = repo.get_blocking(issue_id)
    return jsonify({
        "blockers": [i.to_dict() for i in blockers],
        "blocking": [i.to_dict() for i in blocking],
    })


@app.route("/api/issues/<int:issue_id>/refs", methods=["GET"])
def api_get_code_refs(issue_id: int) -> Any:
    """API: Get code references for an issue."""
    repo = get_repo()
    refs = repo.get_code_references(issue_id)
    return jsonify([
        {
            "id": r.id,
            "file_path": r.file_path,
            "start_line": r.start_line,
            "end_line": r.end_line,
        }
        for r in refs
    ])


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
