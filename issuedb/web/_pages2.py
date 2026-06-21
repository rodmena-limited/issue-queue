"""Page templates built from BASE_TEMPLATE (byte-preserved)."""

from issuedb.web._base import BASE_TEMPLATE

ISSUES_LIST_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}.issue.db{% endblock %}",
    "{% block title %}Issues [{{ project_name }}] - .issue.db{% endblock %}",
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
                        <a href="/issues?tag={{ tag.name }}" class="badge" style="font-size: 10px; padding: 2px 6px; {% if tag.color %}background-color: {{ tag.color | safe_color }}20; color: {{ tag.color | safe_color }}; border: 1px solid {{ tag.color | safe_color }}40;{% else %}background-color: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-color);{% endif %}">{{ tag.name }}</a>
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
    "{% block title %}.issue.db{% endblock %}",
    "{% block title %}Audit Log - .issue.db{% endblock %}",
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
