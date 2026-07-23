"""ISSUE_DETAIL_TEMPLATE assembled from byte-preserved chunks."""

from issuedb.web._base import BASE_TEMPLATE
from issuedb.web._detail_part2 import SCRIPTS_PART_2

SCRIPTS_PART_1 = """{% block scripts %}
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

    function escapeAttr(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
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
                    html += '<div class="audit-entry"><span class="audit-action">' + escapeHtml(log.action) + '</span>';
                    if (log.field_name) {
                        html += '<span class="audit-field">' + escapeHtml(log.field_name) + '</span>: ';
                        if (log.old_value) html += '<span class="audit-value">' + escapeHtml(truncate(log.old_value, 30)) + '</span> &rarr; ';
                        html += '<span class="audit-value">' + (log.new_value ? escapeHtml(truncate(log.new_value, 30)) : 'null') + '</span>';
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
                        '<a href="/issues/' + b.id + '">#' + b.id + ' ' + escapeHtml(truncate(b.title, 25)) + '</a>';
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
                        '<a href="/issues/' + b.id + '">#' + b.id + ' ' + escapeHtml(truncate(b.title, 25)) + '</a></div>';
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
                    html += '<a href="/issues/' + link.id + '" style="flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">#' + link.id + ' ' + escapeHtml(truncate(link.title, 20)) + '</a>';

                    // Delete button (link.type is user-controlled: carry it in a safely
                    // escaped data-attribute and bind the handler instead of inlining it).
                    html += '<button class="del-link-btn" data-issue-id="' + issueId + '" data-link-id="' + link.id + '" data-direction="' + link.direction + '" data-link-type="' + escapeAttr(link.type) + '" style="background: none; border: none; color: var(--text-muted); cursor: pointer; margin-left: 4px; font-size: 14px;">&times;</button>';

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

"""

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
        <a href="/issues?tag={{ tag.name }}" class="badge" style="{% if tag.color %}background-color: {{ tag.color | safe_color }}20; color: {{ tag.color | safe_color }}; border: 1px solid {{ tag.color | safe_color }}40;{% else %}background-color: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-color);{% endif %}">{{ tag.name }}</a>
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
        SCRIPTS_PART_1 + SCRIPTS_PART_2,
    )
)
