"""ISSUE_DETAIL_TEMPLATE scripts chunk (auto-split, byte-preserved)."""

SCRIPTS_PART_2 = """            section.innerHTML = html;
            var delBtns = section.querySelectorAll('.del-link-btn');
            for (var di = 0; di < delBtns.length; di++) {
                delBtns[di].addEventListener('click', function() {
                    deleteLink(
                        parseInt(this.getAttribute('data-issue-id'), 10),
                        parseInt(this.getAttribute('data-link-id'), 10),
                        this.getAttribute('data-link-type')
                    );
                });
            }
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
{% endblock %}"""
