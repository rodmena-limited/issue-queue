"""BASE_TEMPLATE chunk (auto-split, byte-preserved)."""

PART_3 = """            color: var(--accent-yellow);
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
