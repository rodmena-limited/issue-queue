"""Page templates built from BASE_TEMPLATE (byte-preserved)."""

from issuedb.web._base import BASE_TEMPLATE

DASHBOARD_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}",
    "{% block title %}[{{ project_name }}] - .issue.db{% endblock %}",
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
    "{% block title %}.issue.db{% endblock %}",
    "{% block title %}Memory [{{ project_name }}] - .issue.db{% endblock %}",
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
