"""BASE_TEMPLATE chunk (auto-split, byte-preserved)."""

PART_1 = """
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
"""
