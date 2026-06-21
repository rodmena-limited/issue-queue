"""BASE_TEMPLATE chunk (auto-split, byte-preserved)."""

PART_2 = """        }

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
"""
