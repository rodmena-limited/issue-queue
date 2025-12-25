"""Flask Web UI and API for .issue.db."""

import contextlib
import os
from pathlib import Path
from typing import Any, Optional, Union

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for
from werkzeug.wrappers import Response

from issuedb.models import Issue, Priority, Status
from issuedb.repository import IssueRepository
from issuedb.similarity import find_similar_issues

app = Flask(__name__)

# Cache repository instances by db_path
_repo_cache: dict[str, IssueRepository] = {}


@app.context_processor
def inject_project_info() -> dict[str, str]:
    """Inject project information into templates."""
    db_path = request.args.get("db")
    if db_path:
        try:
            path = Path(db_path).resolve()
            project_name = path.parent.name if path.is_file() else path.name
        except Exception:
            project_name = "unknown"
    else:
        project_name = Path.cwd().name
    return {"project_name": project_name}


def get_repo() -> IssueRepository:
    """Get cached repository instance for the current db_path."""
    db_path = request.args.get("db") or ""

    # Use request-scoped cache first (Flask g object)
    cache_key = f"repo_{db_path}"
    cached_repo: Optional[IssueRepository] = getattr(g, cache_key, None)
    if cached_repo is not None:
        return cached_repo

    # Fall back to global cache
    if db_path not in _repo_cache:
        _repo_cache[db_path] = IssueRepository(db_path if db_path else None)

    repo = _repo_cache[db_path]
    setattr(g, cache_key, repo)
    return repo


# =============================================================================
# HTML Templates
# =============================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="author" content="RODMENA LIMITED, https://rodmena.co.uk">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <title>{% block title %}.issue.db{% endblock %}</title>
    <style>
        @font-face {
            font-family: 'JetBrains Mono';
            src: url('/static/fonts/JetBrainsMono-Regular.woff2') format('woff2');
            font-weight: 400;
            font-style: normal;
        }
        @font-face {
            font-family: 'JetBrains Mono';
            src: url('/static/fonts/JetBrainsMono-Bold.woff2') format('woff2');
            font-weight: 700;
            font-style: normal;
        }
        @font-face {
            font-family: 'JetBrains Mono';
            src: url('/static/fonts/JetBrainsMono-Italic.woff2') format('woff2');
            font-weight: 400;
            font-style: italic;
        }
        @font-face {
            font-family: 'JetBrains Mono';
            src: url('/static/fonts/JetBrainsMono-BoldItalic.woff2') format('woff2');
            font-weight: 700;
            font-style: italic;
        }

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
            --status-wontdo: #a371f7;
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
            font-family: 'JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code',
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
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 28px;
        }

        @media (max-width: 1200px) {
            .stats-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        @media (max-width: 800px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 500px) {
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

        .badge-wont-do {
            background-color: rgba(163, 113, 247, 0.15);
            color: var(--status-wontdo);
            border: 1px solid rgba(163, 113, 247, 0.4);
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

        /* Context section */
        .context-section {
            padding: 16px 0;
            border-bottom: 1px solid var(--border-light);
        }

        .context-section:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }

        .context-section:first-child {
            padding-top: 0;
        }

        .context-label {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            margin-bottom: 12px;
        }

        .context-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            font-size: 13px;
        }

        .context-icon {
            font-size: 14px;
            width: 18px;
            text-align: center;
            flex-shrink: 0;
        }

        .context-commit {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 6px 0;
            font-size: 12px;
        }

        .commit-hash {
            background-color: var(--bg-tertiary);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            color: var(--accent-cyan);
            flex-shrink: 0;
        }

        .commit-msg {
            color: var(--text-secondary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <div class="header-content">
                <a href="/" class="logo">
                    <span class="logo-icon">&gt;_</span>
                    <span>.issue.db</span>
                    <span style="color: var(--text-muted); font-size: 0.8em; font-weight: normal; margin-left: 2px;">/{{ project_name }}</span>
                </a>
                <nav class="nav">
                    <a href="/" class="{{ 'active' if active_page == 'dashboard' else '' }}">Dashboard</a>
                    <a href="/issues" class="{{ 'active' if active_page == 'issues' else '' }}">Issues</a>
                    <a href="/memory" class="{{ 'active' if active_page == 'memory' else '' }}">Memory</a>
                    <a href="/lessons" class="{{ 'active' if active_page == 'lessons' else '' }}">Lessons</a>
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
            <a href="https://github.com/rodmena-limited/issue-queue" target="_new">.issue.db</a> &middot; Command-line issue tracking for developers;
        </div>
    </footer>

    {% block scripts %}{% endblock %}
</body>
</html>
"""

DASHBOARD_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}", "{% block title %}[{{ project_name }}] - .issue.db{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
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

    <div class="stat-card">
        <a href="/issues?status=wont-do" class="stat-card-link"></a>
        <div class="stat-label">Won't Do</div>
        <div class="stat-value" style="color: var(--status-wontdo)">{{ summary.by_status.wont_do | default(0) }}</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {{ summary.status_percentages['wont-do'] | default(0) }}%; background-color: var(--status-wontdo)"></div>
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
{% endblock %}""",
)

MEMORY_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}", "{% block title %}Memory [{{ project_name }}] - .issue.db{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
<div class="page-header">
    <div>
        <h1 class="page-title">Memory</h1>
        <p class="page-subtitle">Persistent context for AI agents</p>
    </div>
</div>

<div class="issue-detail-body">
    <div>
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Stored Items</h3>
            </div>
            {% if memories %}
            <table class="issue-table">
                <thead>
                    <tr>
                        <th style="width: 150px;">Category</th>
                        <th style="width: 200px;">Key</th>
                        <th>Value</th>
                        <th style="width: 100px;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in memories %}
                    <tr>
                        <td><span class="badge badge-low">{{ item.category }}</span></td>
                        <td style="font-family: monospace;">{{ item.key }}</td>
                        <td style="white-space: pre-wrap;">{{ item.value }}</td>
                        <td>
                            <form action="/memory/delete/{{ item.key }}" method="post" onsubmit="return confirm('Delete this item?')">
                                <button type="submit" class="btn btn-danger btn-sm" style="padding: 2px 8px; font-size: 11px;">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty-state">
                <div class="empty-state-icon">&gt;_</div>
                <div class="empty-state-title">No memory items</div>
                <p>Add persistent information for agents here</p>
            </div>
            {% endif %}
        </div>
    </div>

    <div class="sidebar">
        <div class="card">
            <div class="sidebar-section">
                <div class="sidebar-label">Add Memory</div>
                <form action="/memory/add" method="post">
                    <div class="form-group">
                        <label class="form-label">Key *</label>
                        <input type="text" name="key" class="form-control" required placeholder="e.g., project_style">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Category</label>
                        <input type="text" name="category" class="form-control" value="general" placeholder="general">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Value *</label>
                        <textarea name="value" class="form-control" required placeholder="Value content..." style="min-height: 100px;"></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary btn-sm" style="width: 100%;">Add Item</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",
)

LESSONS_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}",
    "{% block title %}Lessons Learned [{{ project_name }}] - .issue.db{% endblock %}",
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
<div class="page-header">
    <div>
        <h1 class="page-title">Lessons Learned</h1>
        <p class="page-subtitle">Knowledge base from resolved issues</p>
    </div>
</div>

<div class="issue-detail-body">
    <div>
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Lessons</h3>
            </div>
            {% if lessons %}
            <table class="issue-table">
                <thead>
                    <tr>
                        <th style="width: 120px;">Category</th>
                        <th>Lesson</th>
                        <th style="width: 80px;">Issue</th>
                        <th style="width: 150px;">Date</th>
                        <th style="width: 100px;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in lessons %}
                    <tr>
                        <td><span class="badge badge-medium">{{ item.category }}</span></td>
                        <td style="white-space: pre-wrap;">{{ item.lesson }}</td>
                        <td>
                            {% if item.issue_id %}
                            <a href="/issues/{{ item.issue_id }}">#{{ item.issue_id }}</a>
                            {% else %}
                            -
                            {% endif %}
                        </td>
                        <td class="issue-meta">{{ item.created_at.strftime('%Y-%m-%d') }}</td>
                        <td>
                            <form action="/lessons/delete/{{ item.id }}" method="post" onsubmit="return confirm('Delete this lesson?')">
                                <button type="submit" class="btn btn-danger btn-sm" style="padding: 2px 8px; font-size: 11px;">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty-state">
                <div class="empty-state-icon">&gt;_</div>
                <div class="empty-state-title">No lessons yet</div>
                <p>Record lessons learned from resolved issues</p>
            </div>
            {% endif %}
        </div>
    </div>

    <div class="sidebar">
        <div class="card">
            <div class="sidebar-section">
                <div class="sidebar-label">Add Lesson</div>
                <form action="/lessons/add" method="post">
                    <div class="form-group">
                        <label class="form-label">Lesson *</label>
                        <textarea name="lesson" class="form-control" required placeholder="What did we learn?" style="min-height: 100px;"></textarea>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Category</label>
                        <input type="text" name="category" class="form-control" value="general">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Related Issue ID</label>
                        <input type="number" name="issue_id" class="form-control" placeholder="Optional">
                    </div>
                    <button type="submit" class="btn btn-primary btn-sm" style="width: 100%;">Add Lesson</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",
)

ISSUES_LIST_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}", "{% block title %}Issues [{{ project_name }}] - .issue.db{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
<div class="page-header">
    <div>
        <h1 class="page-title">Issues</h1>
        <p class="page-subtitle">{{ total_issues if total_issues is defined else issues|length }} issue{% if (total_issues if total_issues is defined else issues|length) != 1 %}s{% endif %}{% if status_filter or priority_filter or search_query or tag_filter %} found{% endif %}</p>
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
                <option value="wont-do" {{ 'selected' if status_filter == 'wont-do' }}>Won't Do</option>
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
                   value="{{ search_query or '' }}" class="search-input">
            <button type="submit" class="btn btn-sm">Search</button>
        </div>
        {% if status_filter or priority_filter or search_query or tag_filter %}
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
                <th style="width: 120px;">Due Date</th>
                <th style="width: 120px;">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for issue in issues %}
            <tr>
                <td><a href="/issues/{{ issue.id }}" class="issue-num">#{{ issue.id }}</a></td>
                <td class="issue-title">
                    <a href="/issues/{{ issue.id }}">{{ issue.title }}</a>
                    {% if issue.tags %}
                    <div style="display: inline-flex; gap: 4px; margin-left: 8px;">
                        {% for tag in issue.tags %}
                        <a href="/issues?tag={{ tag.name }}" class="badge" style="font-size: 10px; padding: 2px 6px; {% if tag.color %}background-color: {{ tag.color }}20; color: {{ tag.color }}; border: 1px solid {{ tag.color }}40;{% else %}background-color: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-color);{% endif %}">{{ tag.name }}</a>
                        {% endfor %}
                    </div>
                    {% endif %}
                    {% if issue.description %}
                    <div class="issue-meta">{{ issue.description[:100] }}{% if issue.description|length > 100 %}...{% endif %}</div>
                    {% endif %}
                </td>
                <td><span class="badge badge-{{ issue.status.value | replace('-', '-') }}">{{ issue.status.value }}</span></td>
                <td><span class="badge badge-{{ issue.priority.value }}">{{ issue.priority.value }}</span></td>
                <td class="issue-meta">{{ issue.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
                <td class="issue-meta">{{ issue.due_date.strftime('%Y-%m-%d') if issue.due_date else '-' }}</td>
                <td>
                    <div class="quick-actions">
                        <a href="/issues/{{ issue.id }}/edit" class="quick-action">Edit</a>
                        {% if issue.status.value not in ['closed', 'wont-do'] %}
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

    <!-- Pagination -->
    {% if total_pages is defined and total_pages > 1 %}
    <div style="margin-top: 20px; margin-bottom: 20px; display: flex; justify-content: center; align-items: center; gap: 12px;">
        {% if page > 1 %}
        <a href="{{ url_for('issues_list', page=page-1, status=status_filter, priority=priority_filter, q=search_query, tag=tag_filter) }}" class="btn btn-sm">Previous</a>
        {% else %}
        <span class="btn btn-sm" style="opacity: 0.5; cursor: default;">Previous</span>
        {% endif %}

        <span style="font-size: 13px; color: var(--text-secondary);">Page {{ page }} of {{ total_pages }}</span>

        {% if page < total_pages %}
        <a href="{{ url_for('issues_list', page=page+1, status=status_filter, priority=priority_filter, q=search_query, tag=tag_filter) }}" class="btn btn-sm">Next</a>
        {% else %}
        <span class="btn btn-sm" style="opacity: 0.5; cursor: default;">Next</span>
        {% endif %}
    </div>
    {% endif %}

    {% else %}
    <div class="empty-state">
        <div class="empty-state-icon">&gt;_</div>
        <div class="empty-state-title">No issues found</div>
        <p>{% if search_query or status_filter or priority_filter %}Try different filters{% else %}Create your first issue to get started{% endif %}</p>
    </div>
    {% endif %}
</div>
{% endblock %}""",
)

ISSUE_DETAIL_TEMPLATE = (
    BASE_TEMPLATE.replace(
        "{% block title %}.issue.db{% endblock %}",
        "{% block title %}#{{ issue.id }} {{ issue.title }} - .issue.db{% endblock %}",
    )
    .replace(
        "{% block content %}{% endblock %}",
        """{% block content %}
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
        {% for tag in issue.tags %}
        <a href="/issues?tag={{ tag.name }}" class="badge" style="{% if tag.color %}background-color: {{ tag.color }}20; color: {{ tag.color }}; border: 1px solid {{ tag.color }}40;{% else %}background-color: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-color);{% endif %}">{{ tag.name }}</a>
        {% endfor %}
        <span>Created {{ issue.created_at.strftime('%Y-%m-%d %H:%M') }}</span>
        <span>&middot;</span>
        <span>Updated {{ issue.updated_at.strftime('%Y-%m-%d %H:%M') }}</span>
        {% if issue.due_date %}
        <span>&middot;</span>
        <span>Due {{ issue.due_date.strftime('%Y-%m-%d') }}</span>
        {% endif %}
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

        <!-- Context Card (async loaded) -->
        <div class="card" id="context-card">
            <div class="card-header">
                <h3 class="card-title">Context</h3>
            </div>
            <div class="card-body" id="context-content">
                <div class="loading-placeholder">Loading context...</div>
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
                    {% if issue.status.value not in ['closed', 'wont-do'] %}
                    <form action="/api/issues/{{ issue.id }}" method="post" style="display: inline;">
                        <input type="hidden" name="_method" value="PATCH">
                        <input type="hidden" name="status" value="closed">
                        <button type="submit" class="quick-action">Close</button>
                    </form>
                    {% endif %}
                    {% if issue.status.value in ['closed', 'wont-do'] %}
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
                        <option value="wont-do" {{ 'selected' if issue.status.value == 'wont-do' }}>Won't Do</option>
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

            <!-- Linked Issues (async loaded) -->
            <div id="links-section"></div>

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
{% endblock %}""",
    )
    .replace(
        "{% block scripts %}{% endblock %}",
        """{% block scripts %}
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

    // Load linked issues
    fetch(baseUrl + '/links')
        .then(function(r) { return r.json(); })
        .then(function(links) {
            var section = document.getElementById('links-section');
            var html = '';

            // Combine source and target links
            var allLinks = [];
            if (links.source) {
                for (var i = 0; i < links.source.length; i++) {
                    var l = links.source[i];
                    allLinks.push({
                        id: l.target_id,
                        title: l.target_title,
                        status: l.target_status,
                        type: l.type,
                        direction: 'out'
                    });
                }
            }
            if (links.target) {
                for (var i = 0; i < links.target.length; i++) {
                    var l = links.target[i];
                    allLinks.push({
                        id: l.source_id,
                        title: l.source_title,
                        status: l.source_status,
                        type: l.type,
                        direction: 'in'
                    });
                }
            }

            if (allLinks.length > 0) {
                html += '<div class="sidebar-section"><div class="sidebar-label">Linked Issues</div>';
                for (var i = 0; i < allLinks.length; i++) {
                    var link = allLinks[i];
                    var icon = link.direction === 'out' ? '&#x2192;' : '&#x2190;';
                    html += '<div class="blocker-item" style="flex-wrap: wrap;">';
                    html += '<span style="color: var(--accent-cyan); margin-right: 6px;">' + icon + '</span>';
                    html += '<span class="badge badge-low" style="margin-right: 6px; font-size: 9px;">' + escapeHtml(link.type) + '</span>';
                    html += '<a href="/issues/' + link.id + '" style="flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">#' + link.id + ' ' + truncate(link.title, 20) + '</a>';

                    // Delete button
                    html += '<button onclick="deleteLink(' + issueId + ', ' + link.id + ', \\'' + escapeHtml(link.type) + '\\')" style="background: none; border: none; color: var(--text-muted); cursor: pointer; margin-left: 4px; font-size: 14px;">&times;</button>';

                    html += '</div>';
                }
                html += '</div>';
            }

            // Add Link Form
            html += '<div class="sidebar-section">';
            html += '<div class="sidebar-label">Add Link</div>';
            html += '<div style="display: flex; gap: 6px; flex-direction: column;">';
            html += '<input type="number" id="link-target-id" class="form-control" placeholder="Issue ID" style="padding: 6px 10px; font-size: 12px;">';
            html += '<input type="text" id="link-type" class="form-control" placeholder="Type (e.g. related)" style="padding: 6px 10px; font-size: 12px;">';
            html += '<button onclick="addLink(' + issueId + ')" class="btn btn-sm" style="width: 100%;">Link Issue</button>';
            html += '</div></div>';

            section.innerHTML = html;
        })
        .catch(function() {
             // Even on error, show the form so user can try to link
            var section = document.getElementById('links-section');
            var html = '<div class="sidebar-section">';
            html += '<div class="sidebar-label">Add Link</div>';
            html += '<div style="display: flex; gap: 6px; flex-direction: column;">';
            html += '<input type="number" id="link-target-id" class="form-control" placeholder="Issue ID" style="padding: 6px 10px; font-size: 12px;">';
            html += '<input type="text" id="link-type" class="form-control" placeholder="Type (e.g. related)" style="padding: 6px 10px; font-size: 12px;">';
            html += '<button onclick="addLink(' + issueId + ')" class="btn btn-sm" style="width: 100%;">Link Issue</button>';
            html += '</div></div>';
            section.innerHTML = html;
        });

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

    // Load context
    fetch(baseUrl + '/context')
        .then(function(r) { return r.json(); })
        .then(function(ctx) {
            var content = document.getElementById('context-content');
            var html = '';

            // Git info section
            if (ctx.git) {
                html += '<div class="context-section">';
                html += '<div class="context-label">Git Integration</div>';
                html += '<div class="context-item">';
                html += '<span class="context-icon" style="color: var(--accent-purple);">&#x2387;</span>';
                html += '<span>Branch: <strong>' + escapeHtml(ctx.git.branch || 'N/A') + '</strong></span>';
                if (ctx.git.branch_matches_issue) {
                    html += '<span class="badge badge-open" style="margin-left: 8px; font-size: 9px;">matches</span>';
                }
                html += '</div>';
                if (ctx.git.commits_mentioning_issue && ctx.git.commits_mentioning_issue.length > 0) {
                    html += '<div style="margin-top: 10px; font-size: 11px; color: var(--text-muted);">Commits mentioning #' + issueId + ':</div>';
                    for (var i = 0; i < ctx.git.commits_mentioning_issue.length; i++) {
                        var c = ctx.git.commits_mentioning_issue[i];
                        html += '<div class="context-commit">';
                        html += '<code class="commit-hash">' + c.hash + '</code>';
                        html += '<span class="commit-msg">' + escapeHtml(c.message) + '</span>';
                        html += '</div>';
                    }
                }
                html += '</div>';
            }

            // Suggested actions section
            if (ctx.suggested_actions && ctx.suggested_actions.length > 0) {
                html += '<div class="context-section">';
                html += '<div class="context-label">Suggested Actions</div>';
                for (var i = 0; i < ctx.suggested_actions.length; i++) {
                    var action = ctx.suggested_actions[i];
                    var iconColor = action.priority === 'high' ? 'var(--accent-red)' : 'var(--accent-blue)';
                    var icon = action.type === 'blocked' ? '&#x26D4;' : action.type === 'start' ? '&#x25B6;' : action.type === 'close' ? '&#x2713;' : '&#x2022;';
                    html += '<div class="context-item">';
                    html += '<span class="context-icon" style="color: ' + iconColor + ';">' + icon + '</span>';
                    html += '<span>' + escapeHtml(action.text) + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }

            // Related issues section
            if (ctx.related_issues && ctx.related_issues.length > 0) {
                html += '<div class="context-section">';
                html += '<div class="context-label">Related Issues</div>';
                for (var i = 0; i < ctx.related_issues.length; i++) {
                    var rel = ctx.related_issues[i];
                    html += '<div class="context-item">';
                    html += '<a href="/issues/' + rel.id + '">#' + rel.id + ' ' + escapeHtml(rel.title) + '</a>';
                    html += '<span class="badge badge-' + rel.status + '" style="margin-left: 8px; font-size: 9px;">' + rel.status + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }

            if (html === '') {
                html = '<p style="color: var(--text-muted); font-style: italic;">No additional context available.</p>';
            }

            content.innerHTML = html;
        })
        .catch(function() {
            document.getElementById('context-content').innerHTML = '<p style="color: var(--accent-red);">Failed to load context</p>';
        });
})();

window.addLink = function(sourceId) {
    var targetId = document.getElementById('link-target-id').value;
    var type = document.getElementById('link-type').value;

    if (!targetId || !type) {
        alert('Please provide Issue ID and Relation Type');
        return;
    }

    fetch('/api/links', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            source: sourceId,
            target: parseInt(targetId),
            type: type
        })
    })
    .then(function(response) {
        if (response.ok) {
            window.location.reload();
        } else {
            response.json().then(function(data) {
                alert('Error: ' + (data.error || 'Failed to add link'));
            });
        }
    });
};

window.deleteLink = function(sourceId, targetId, type) {
    if (!confirm('Are you sure you want to unlink these issues?')) return;

    fetch('/api/links', {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            source: sourceId,
            target: targetId,
            type: type
        })
    })
    .then(function(response) {
        if (response.ok) {
            window.location.reload();
        } else {
            alert('Failed to delete link');
        }
    });
};
</script>
{% endblock %}""",
    )
)

ISSUE_FORM_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}",
    "{% block title %}{{ 'Edit' if issue else 'New' }} Issue - .issue.db{% endblock %}",
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
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
                        <option value="wont-do" {{ 'selected' if issue and issue.status.value == 'wont-do' }}>Won't Do</option>
                    </select>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label">Due Date (YYYY-MM-DD)</label>
                <input type="date" name="due_date" class="form-control" value="{{ issue.due_date.strftime('%Y-%m-%d') if issue and issue.due_date else '' }}">
            </div>
            <div class="form-group">
                <label class="form-label">Tags (comma separated)</label>
                <input type="text" name="tags" class="form-control" value="{{ issue.tags|map(attribute='name')|join(', ') if issue and issue.tags else '' }}" placeholder="bug, frontend, v1.0">
            </div>

            <div class="form-group">
                <label class="form-label" for="related_issues">Related Issues (IDs)</label>
                <input type="text" id="related_issues" name="related_issues" class="form-control"
                       placeholder="e.g. 12, 15 (comma separated)">
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                    Enter IDs of issues related to this one. They will be linked as 'related'.
                </div>
            </div>

            <div style="display: flex; gap: 12px; margin-top: 8px;">
                <button type="submit" class="btn btn-primary">{{ 'Update Issue' if issue else 'Create Issue' }}</button>
                <a href="{{ '/issues/' ~ issue.id if issue else '/issues' }}" class="btn">Cancel</a>
            </div>
        </form>
    </div>
</div>
{% endblock %}""",
)

AUDIT_LOG_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}", "{% block title %}Audit Log - .issue.db{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
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
{% endblock %}""",
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
    """Issues list page."""
    repo = get_repo()
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    search_query = request.args.get("q")
    tag_filter = request.args.get("tag")
    due_date_filter = request.args.get("due_date")

    # Pagination
    page = request.args.get("page", 1, type=int)
    limit = 20
    offset = (page - 1) * limit

    if search_query:
        issues = repo.search_issues(search_query, limit=limit, offset=offset)
    else:
        issues = repo.list_issues(
            status=status_filter,
            priority=priority_filter,
            due_date=due_date_filter,
            tag=tag_filter,
            limit=limit,
            offset=offset,
        )

    # Populate tags
    for issue in issues:
        if issue.id:
            issue.tags = repo.get_issue_tags(issue.id)

    total_issues = repo.count_issues(
        status=status_filter,
        priority=priority_filter,
        due_date=due_date_filter,
        tag=tag_filter,
        keyword=search_query,
    )

    import math
    total_pages = math.ceil(total_issues / limit) if total_issues else 0

    return render_template_string(
        ISSUES_LIST_TEMPLATE,
        active_page="issues",
        issues=issues,
        status_filter=status_filter,
        priority_filter=priority_filter,
        search_query=search_query,
        tag_filter=tag_filter,
        page=page,
        total_pages=total_pages,
        total_issues=total_issues,
    )


@app.route("/issues/new", methods=["GET", "POST"])
def create_issue() -> Union[str, Response]:
    """Create a new issue."""
    repo = get_repo()

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        priority = request.form.get("priority", "medium")
        status = request.form.get("status", "open")
        due_date = request.form.get("due_date")
        tags_str = request.form.get("tags")

        if not title:
            return render_template_string(
                ISSUE_FORM_TEMPLATE,
                title="New Issue",
                issue=None,
                error="Title is required",
            )

        due_date_obj = None
        if due_date:
            try:
                from datetime import datetime
                due_date_obj = datetime.fromisoformat(due_date)
            except ValueError:
                pass

        issue = Issue(
            title=title,
            description=description,
            priority=Priority.from_string(priority),
            status=Status.from_string(status),
            due_date=due_date_obj,
        )

        created = repo.create_issue(issue)
        assert created.id is not None  # ID is always assigned after creation

        if tags_str:
            for tag in tags_str.split(","):
                if tag_name := tag.strip():
                    repo.add_issue_tag(created.id, tag_name)

        return redirect(url_for("issue_detail", issue_id=created.id))

    return render_template_string(ISSUE_FORM_TEMPLATE, title="New Issue", issue=None)


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


@app.route("/issues/<int:issue_id>/edit", methods=["GET", "POST"])
def edit_issue(issue_id: int) -> Union[str, Response]:
    """Edit an issue."""
    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return redirect(url_for("issues_list", message="Issue not found"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        priority = request.form.get("priority")
        status = request.form.get("status")
        due_date = request.form.get("due_date")
        tags_str = request.form.get("tags")

        if not title:
            return render_template_string(
                ISSUE_FORM_TEMPLATE,
                title="Edit Issue",
                issue=issue,
                error="Title is required",
            )

        repo.update_issue(
            issue_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
        )

        # Handle tags
        current_tags = {t.name for t in repo.get_issue_tags(issue_id)}
        new_tags = set()
        if tags_str:
            new_tags = {t.strip() for t in tags_str.split(",") if t.strip()}

        for tag in new_tags - current_tags:
            repo.add_issue_tag(issue_id, tag)

        for tag in current_tags - new_tags:
            repo.remove_issue_tag(issue_id, tag)

        return redirect(url_for("issue_detail", issue_id=issue_id))

    return render_template_string(ISSUE_FORM_TEMPLATE, title="Edit Issue", issue=issue)


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


@app.route("/memory")
def memory_page() -> str:
    """Memory management page."""
    repo = get_repo()
    memories = repo.list_memory()
    return render_template_string(
        MEMORY_TEMPLATE,
        active_page="memory",
        memories=memories,
    )


@app.route("/favicon.svg")
def favicon() -> Response:
    """Serve favicon."""
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.svg")


@app.route("/static/fonts/<path:filename>")
def serve_fonts(filename: str) -> Response:
    """Serve font files."""

    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, "static/fonts"), filename)


@app.route("/lessons")
def lessons_page() -> str:
    """Lessons learned page."""
    repo = get_repo()
    lessons = repo.list_lessons()
    return render_template_string(
        LESSONS_TEMPLATE,
        active_page="lessons",
        lessons=lessons,
    )


@app.route("/memory/add", methods=["POST"])
def memory_add() -> Any:
    """Form handler for adding memory."""
    repo = get_repo()

    try:
        key = request.form.get("key")
        value = request.form.get("value")
        category = request.form.get("category", "general")

        if not key or not value:
            return "Key and value required", 400

        repo.add_memory(key=key, value=value, category=category)
        return redirect(url_for("memory_page"))
    except Exception as e:
        return f"Error: {str(e)}", 400


@app.route("/memory/delete/<key>", methods=["POST"])
def memory_delete(key: str) -> Any:
    """Form handler for deleting memory."""
    repo = get_repo()
    repo.delete_memory(key)
    return redirect(url_for("memory_page"))


@app.route("/lessons/add", methods=["POST"])
def add_lesson() -> Response:
    """Add a lesson learned."""
    repo = get_repo()
    lesson = request.form.get("lesson")
    category = request.form.get("category", "general")
    issue_id_str = request.form.get("issue_id")

    if not lesson:
        return redirect(url_for("lessons_page"))

    issue_id = None
    if issue_id_str:
        with contextlib.suppress(ValueError):
            issue_id = int(issue_id_str)

    repo.add_lesson(lesson=lesson, category=category, issue_id=issue_id)
    return redirect(url_for("lessons_page"))


@app.route("/lessons/delete/<int:lesson_id>", methods=["POST"])
def delete_lesson(lesson_id: int) -> Response:
    """Delete a lesson learned."""
    repo = get_repo()
    repo.delete_lesson(lesson_id)
    return redirect(url_for("lessons_page"))



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

    description = data.get("description")
    priority = data.get("priority", "medium")
    status = data.get("status", "open")
    due_date = data.get("due_date")

    due_date_obj = None
    if due_date:
        try:
            from datetime import datetime
            due_date_obj = datetime.fromisoformat(due_date)
        except ValueError:
            pass

    issue = Issue(
        title=title,
        description=description,
        priority=Priority.from_string(priority),
        status=Status.from_string(status),
        due_date=due_date_obj,
    )

    created = repo.create_issue(issue)
    assert created.id is not None  # ID is always assigned after creation
    issue_id = created.id

    if "tags" in data:
        tags_str = data["tags"]
        for tag in tags_str.split(","):
            if tag_name := tag.strip():
                repo.add_issue_tag(issue_id, tag_name)

    if request.is_json:
        # Refetch to include tags
        refetched = repo.get_issue(issue_id)
        assert refetched is not None  # Issue was just created
        return jsonify(refetched.to_dict()), 201

    return redirect(url_for("issue_detail", issue_id=created.id))


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
    if "due_date" in data:
        updates["due_date"] = data["due_date"]

    if not updates and "tags" not in data:
        if request.is_json:
            return jsonify({"error": "No updates provided"}), 400
        return redirect(url_for("issue_detail", issue_id=issue_id, error="No updates provided"))

    if updates:
        repo.update_issue(issue_id, **updates)

    # Handle tags
    if "tags" in data:
        tags_str = data["tags"]
        current_tags = {t.name for t in repo.get_issue_tags(issue_id)}
        new_tags = {t.strip() for t in tags_str.split(",") if t.strip()}

        for tag in new_tags - current_tags:
            repo.add_issue_tag(issue_id, tag)

        for tag in current_tags - new_tags:
            repo.remove_issue_tag(issue_id, tag)

    if request.is_json:
        updated = repo.get_issue(issue_id)
        return jsonify(updated.to_dict()) if updated else (jsonify({"error": "Issue not found"}), 404)

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
        return redirect(
            url_for("issue_detail", issue_id=issue_id, error="Comment text is required")
        )

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
            return jsonify(
                {
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                }
            )
        return redirect(
            url_for("issue_detail", issue_id=issue_id, message="Started working on issue")
        )
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
            return jsonify(
                {
                    "issue": issue.to_dict(),
                    "started_at": started_at.isoformat(),
                    "stopped_at": stopped_at.isoformat(),
                }
            )
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

    return jsonify(
        [{"issue": i.to_dict(), "score": round(score, 3)} for i, score in similar_results[:limit]]
    )


@app.route("/api/issues/<int:issue_id>/audit", methods=["GET"])
def api_issue_audit(issue_id: int) -> Any:
    """API: Get audit logs for an issue."""
    repo = get_repo()
    logs = repo.get_audit_logs(issue_id)

    return jsonify(
        [
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
        ]
    )


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

    return jsonify(
        [
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
        ]
    )


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
    return jsonify(
        {
            "entries": result,
            "total_formatted": f"{total_hours}h {total_minutes}m"
            if total_hours
            else f"{total_minutes}m",
            "total_seconds": total_seconds,
        }
    )


@app.route("/api/issues/<int:issue_id>/dependencies", methods=["GET"])
def api_get_dependencies(issue_id: int) -> Any:
    """API: Get dependencies (blockers/blocking) for an issue."""
    repo = get_repo()
    blockers = repo.get_blockers(issue_id)
    blocking = repo.get_blocking(issue_id)
    return jsonify(
        {
            "blockers": [i.to_dict() for i in blockers],
            "blocking": [i.to_dict() for i in blocking],
        }
    )


@app.route("/api/issues/<int:issue_id>/links", methods=["GET"])
def api_get_issue_links(issue_id: int) -> Any:
    """API: Get links for an issue."""
    repo = get_repo()
    links = repo.get_issue_relations(issue_id)
    return jsonify(links)


@app.route("/api/issues/<int:issue_id>/refs", methods=["GET"])
def api_get_code_refs(issue_id: int) -> Any:
    """API: Get code references for an issue."""
    repo = get_repo()
    refs = repo.get_code_references(issue_id)
    return jsonify(
        [
            {
                "id": r.id,
                "file_path": r.file_path,
                "start_line": r.start_line,
                "end_line": r.end_line,
            }
            for r in refs
        ]
    )


@app.route("/api/issues/<int:issue_id>/context", methods=["GET"])
def api_get_context(issue_id: int) -> Any:
    """API: Get comprehensive context for an issue."""
    import subprocess

    repo = get_repo()
    issue = repo.get_issue(issue_id)

    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    context: dict[str, Any] = {
        "git": None,
        "suggested_actions": [],
        "related_issues": [],
    }

    # Get git info
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

            # Get recent commits mentioning this issue
            commits = []
            try:
                log_result = subprocess.run(
                    ["git", "log", "--oneline", "-10", f"--grep=#{issue_id}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if log_result.returncode == 0 and log_result.stdout.strip():
                    for line in log_result.stdout.strip().split("\n")[:5]:
                        if line:
                            parts = line.split(" ", 1)
                            commits.append(
                                {
                                    "hash": parts[0],
                                    "message": parts[1] if len(parts) > 1 else "",
                                }
                            )
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

            # Check if branch matches issue
            branch_matches = current_branch and str(issue_id) in current_branch

            context["git"] = {
                "branch": current_branch,
                "branch_matches_issue": branch_matches,
                "commits_mentioning_issue": commits,
            }
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    # Generate suggested actions
    actions = []
    if issue.status.value == "open":
        actions.append(
            {
                "type": "start",
                "text": "Start working on this issue",
                "priority": "high" if issue.priority.value in ["critical", "high"] else "normal",
            }
        )
    elif issue.status.value == "in-progress":
        actions.append(
            {
                "type": "progress",
                "text": "Add a progress update comment",
                "priority": "normal",
            }
        )
        actions.append(
            {
                "type": "close",
                "text": "Close issue when complete",
                "priority": "normal",
            }
        )
    elif issue.status.value == "closed":
        actions.append(
            {
                "type": "reopen",
                "text": "Reopen if issue persists",
                "priority": "low",
            }
        )
    elif issue.status.value == "wont-do":
        actions.append(
            {
                "type": "reopen",
                "text": "Reopen if decision changes",
                "priority": "low",
            }
        )

    # Check comments
    comments = repo.get_comments(issue_id)
    if len(comments) == 0:
        actions.append(
            {
                "type": "comment",
                "text": "Add notes or context",
                "priority": "normal",
            }
        )

    # Check blockers
    blockers = repo.get_blockers(issue_id)
    open_blockers = [b for b in blockers if b.status.value not in ["closed", "wont-do"]]
    if open_blockers:
        actions.insert(
            0,
            {
                "type": "blocked",
                "text": f"Blocked by {len(open_blockers)} open issue(s)",
                "priority": "high",
            },
        )

    context["suggested_actions"] = actions

    # Get related issues (by keyword search)
    if issue.title:
        words = issue.title.split()
        if words:
            keyword = words[0]
            similar = repo.search_issues(keyword=keyword, limit=5)
            related = [
                {"id": i.id, "title": i.title, "status": i.status.value}
                for i in similar
                if i.id != issue_id
            ][:3]
            context["related_issues"] = related

    return jsonify(context)


@app.route("/api/memory", methods=["GET", "POST"])
def api_memory_list_create() -> Any:
    """API: List or create memory items."""
    repo = get_repo()

    if request.method == "POST":
        data = request.get_json()
        try:
            memory = repo.add_memory(
                key=data["key"],
                value=data["value"],
                category=data.get("category", "general"),
            )
            return jsonify(memory.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except KeyError as e:
            return jsonify({"error": f"Missing field: {str(e)}"}), 400
    else:
        category = request.args.get("category")
        search = request.args.get("search")
        memories = repo.list_memory(category=category, search=search)
        return jsonify([m.to_dict() for m in memories])


@app.route("/api/memory/<key>", methods=["PUT", "DELETE"])
def api_memory_update_delete(key: str) -> Any:
    """API: Update or delete memory item."""
    repo = get_repo()

    if request.method == "DELETE":
        if repo.delete_memory(key):
            return jsonify({"message": "Memory deleted"})
        return jsonify({"error": "Memory not found"}), 404
    else:
        data = request.get_json()
        memory = repo.update_memory(
            key=key,
            value=data.get("value"),
            category=data.get("category"),
        )
        if memory:
            return jsonify(memory.to_dict())
        return jsonify({"error": "Memory not found"}), 404


@app.route("/api/lessons", methods=["GET", "POST"])
def api_lessons_list_create() -> Any:
    """API: List or create lessons learned."""
    repo = get_repo()

    if request.method == "POST":
        data = request.get_json()
        try:
            ll = repo.add_lesson(
                lesson=data["lesson"],
                issue_id=data.get("issue_id"),
                category=data.get("category", "general"),
            )
            return jsonify(ll.to_dict()), 201
        except KeyError as e:
            return jsonify({"error": f"Missing field: {str(e)}"}), 400
    else:
        issue_id = request.args.get("issue_id", type=int)
        category = request.args.get("category")
        lessons = repo.list_lessons(issue_id=issue_id, category=category)
        return jsonify([lesson.to_dict() for lesson in lessons])


@app.route("/api/tags", methods=["GET"])
def api_tags_list() -> Any:
    """API: List all tags."""
    repo = get_repo()
    tags = repo.list_tags()
    return jsonify([t.to_dict() for t in tags])


@app.route("/api/issues/<int:issue_id>/tags", methods=["GET", "POST", "DELETE"])
def api_issue_tags(issue_id: int) -> Any:
    """API: Manage issue tags."""
    repo = get_repo()

    if request.method == "GET":
        tags = repo.get_issue_tags(issue_id)
        return jsonify([t.to_dict() for t in tags])

    elif request.method == "POST":
        data = request.get_json()
        tag_name = data.get("tag")
        if not tag_name:
            return jsonify({"error": "Tag name required"}), 400

        if repo.add_issue_tag(issue_id, tag_name):
            return jsonify({"message": "Tag added"}), 201
        return jsonify({"message": "Tag already exists"}), 200

    elif request.method == "DELETE":
        tag_name = request.args.get("tag")
        if not tag_name:
            return jsonify({"error": "Tag name required"}), 400

        if repo.remove_issue_tag(issue_id, tag_name):
            return jsonify({"message": "Tag removed"})
        return jsonify({"error": "Tag not found on issue"}), 404


@app.route("/api/links", methods=["POST", "DELETE"])
def api_links() -> Any:
    """API: Manage issue links."""
    repo = get_repo()

    data = request.get_json()
    source = data.get("source")
    target = data.get("target")
    type = data.get("type")

    if not source or not target:
        return jsonify({"error": "Source and target required"}), 400

    if request.method == "POST":
        if not type:
            return jsonify({"error": "Type required"}), 400
        try:
            rel = repo.link_issues(source, target, type)
            return jsonify(rel.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    elif request.method == "DELETE":
        if repo.unlink_issues(source, target, type):
            return jsonify({"message": "Unlinked"})
        return jsonify({"error": "Link not found"}), 404


def run_server(
    host: str = "0.0.0.0",
    port: int = 7760,
    debug: bool = False,
) -> None:
    """Run the web server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Enable debug mode (uses Flask dev server).
    """
    if debug:
        print(f"Starting .issue.db Web UI on http://{host}:{port} (DEBUG mode with Flask)")
        app.run(host=host, port=port, debug=True)
    else:
        try:
            from waitress import serve  # type: ignore

            print(
                f"Starting .issue.db Web UI on http://{host}:{port} (Production mode with Waitress, 3 threads)"
            )
            serve(app, host=host, port=port, threads=2)
        except ImportError:
            print("Warning: 'waitress' not found. Falling back to Flask development server.")
            print("Install with: pip install issuedb[web]")
            print(f"Starting .issue.db Web UI on http://{host}:{port} (Development mode with Flask)")
            app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server(debug=True)
