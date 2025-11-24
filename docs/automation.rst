Automation
==========

IssueDB is designed for automation. This guide covers scripting, CI/CD integration, and common automation patterns.

Shell Scripting
---------------

Basic Script Structure
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   #!/bin/bash
   set -e  # Exit on error

   # Create an issue
   issuedb-cli create -t "Automated issue" --priority medium

   # Get JSON output
   ISSUES=$(issuedb-cli --json list -s open)

   # Process with jq
   COUNT=$(echo "$ISSUES" | jq 'length')
   echo "Found $COUNT open issues"

Error Handling
~~~~~~~~~~~~~~

.. code-block:: bash

   #!/bin/bash

   # Function to safely run issuedb commands
   run_issuedb() {
       local output
       local exit_code

       output=$(issuedb-cli "$@" 2>&1)
       exit_code=$?

       if [ $exit_code -ne 0 ]; then
           echo "Error: $output" >&2
           return $exit_code
       fi

       echo "$output"
   }

   # Usage
   if ISSUE=$(run_issuedb --json get 1); then
       TITLE=$(echo "$ISSUE" | jq -r '.title')
       echo "Issue title: $TITLE"
   else
       echo "Failed to get issue"
       exit 1
   fi

Common Automation Tasks
-----------------------

Daily Report
~~~~~~~~~~~~

Generate a daily summary:

.. code-block:: bash

   #!/bin/bash
   # daily-report.sh

   DATE=$(date +%Y-%m-%d)
   REPORT_FILE="issue-report-$DATE.json"

   # Get summary
   issuedb-cli --json summary > "$REPORT_FILE"

   # Extract key metrics
   TOTAL=$(jq '.total_issues' "$REPORT_FILE")
   OPEN=$(jq '.by_status.open.count' "$REPORT_FILE")
   CRITICAL=$(jq '.by_priority.critical.count' "$REPORT_FILE")

   echo "=== Issue Report for $DATE ==="
   echo "Total issues: $TOTAL"
   echo "Open issues: $OPEN"
   echo "Critical issues: $CRITICAL"

   # Alert if too many critical issues
   if [ "$CRITICAL" -gt 0 ]; then
       echo "WARNING: $CRITICAL critical issues require attention!"
   fi

Stale Issue Finder
~~~~~~~~~~~~~~~~~~

Find issues that haven't been updated recently:

.. code-block:: bash

   #!/bin/bash
   # find-stale-issues.sh

   DAYS_THRESHOLD=7
   CUTOFF_DATE=$(date -d "$DAYS_THRESHOLD days ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null || \
                 date -v-${DAYS_THRESHOLD}d +%Y-%m-%dT%H:%M:%S)

   echo "Finding issues not updated since $CUTOFF_DATE"

   issuedb-cli --json list -s open | jq --arg cutoff "$CUTOFF_DATE" '
     [.[] | select(.updated_at < $cutoff)] |
     sort_by(.updated_at) |
     .[] |
     "Issue #\(.id): \(.title) (last updated: \(.updated_at))"
   ' -r

Issue Migration
~~~~~~~~~~~~~~~

Export and import issues:

.. code-block:: bash

   #!/bin/bash
   # export-issues.sh

   # Export all issues
   issuedb-cli --json list > issues-export.json
   issuedb-cli --json audit > audit-export.json

   echo "Exported $(jq 'length' issues-export.json) issues"
   echo "Exported $(jq 'length' audit-export.json) audit logs"

.. code-block:: bash

   #!/bin/bash
   # import-issues.sh

   # Transform exported issues for bulk create (remove id, timestamps)
   jq '[.[] | {title, description, priority, status}]' issues-export.json > import-ready.json

   # Import
   issuedb-cli --json bulk-create -f import-ready.json

CI/CD Integration
-----------------

GitHub Actions
~~~~~~~~~~~~~~

Create issues for failed tests:

.. code-block:: yaml

   # .github/workflows/test.yml
   name: Tests

   on: [push, pull_request]

   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - name: Set up Python
           uses: actions/setup-python@v4
           with:
             python-version: '3.11'

         - name: Install dependencies
           run: |
             pip install -e .
             pip install pytest issuedb

         - name: Run tests
           id: tests
           continue-on-error: true
           run: pytest --tb=short 2>&1 | tee test-output.txt

         - name: Create issue for failures
           if: steps.tests.outcome == 'failure'
           run: |
             FAILURES=$(grep -c "FAILED" test-output.txt || echo "0")
             if [ "$FAILURES" -gt 0 ]; then
               issuedb-cli create \
                 -t "CI: $FAILURES test(s) failed on $(date +%Y-%m-%d)" \
                 -d "$(cat test-output.txt | tail -50)" \
                 --priority high
             fi

Release checklist:

.. code-block:: yaml

   # .github/workflows/release.yml
   name: Release

   on:
     release:
       types: [published]

   jobs:
     create-release-issues:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - name: Install IssueDB
           run: pip install issuedb

         - name: Create release tracking issues
           run: |
             VERSION=${{ github.event.release.tag_name }}
             echo '[
               {"title": "Update documentation for '$VERSION'", "priority": "high"},
               {"title": "Announce release '$VERSION'", "priority": "medium"},
               {"title": "Monitor for issues after '$VERSION' release", "priority": "medium"}
             ]' | issuedb-cli --json bulk-create

GitLab CI
~~~~~~~~~

.. code-block:: yaml

   # .gitlab-ci.yml
   stages:
     - test
     - report

   test:
     stage: test
     script:
       - pip install -e . pytest
       - pytest --junitxml=report.xml
     artifacts:
       reports:
         junit: report.xml
       when: always

   issue-report:
     stage: report
     when: on_failure
     script:
       - pip install issuedb
       - |
         issuedb-cli create \
           -t "Pipeline failed: $CI_PIPELINE_ID" \
           -d "Job $CI_JOB_NAME failed. See $CI_JOB_URL" \
           --priority high

Pre-commit Hooks
----------------

Validate issues before commit:

.. code-block:: bash

   #!/bin/bash
   # .git/hooks/pre-commit

   # Check for TODO comments that should be issues
   TODOS=$(grep -r "TODO:" --include="*.py" . | wc -l)

   if [ "$TODOS" -gt 0 ]; then
       echo "Warning: Found $TODOS TODO comments"
       echo "Consider creating issues for these:"
       grep -r "TODO:" --include="*.py" . | head -5

       read -p "Create issues for TODOs? (y/n) " -n 1 -r
       echo
       if [[ $REPLY =~ ^[Yy]$ ]]; then
           grep -r "TODO:" --include="*.py" . | head -5 | while read -r line; do
               TITLE=$(echo "$line" | sed 's/.*TODO: //')
               issuedb-cli create -t "$TITLE" --priority low
           done
       fi
   fi

Cron Jobs
---------

Scheduled maintenance:

.. code-block:: bash

   # /etc/cron.d/issuedb-maintenance

   # Daily summary at 9 AM
   0 9 * * * user cd /path/to/project && /path/to/daily-report.sh

   # Weekly cleanup of old closed issues (archive)
   0 0 * * 0 user cd /path/to/project && /path/to/weekly-archive.sh

   # Check for stale issues every day
   0 10 * * * user cd /path/to/project && /path/to/find-stale-issues.sh

Weekly archive script:

.. code-block:: bash

   #!/bin/bash
   # weekly-archive.sh

   ARCHIVE_DIR="./issue-archives"
   mkdir -p "$ARCHIVE_DIR"

   DATE=$(date +%Y-%m-%d)

   # Export closed issues older than 30 days
   issuedb-cli --json list -s closed | jq --arg cutoff "$(date -d '30 days ago' +%Y-%m-%dT%H:%M:%S)" '
     [.[] | select(.updated_at < $cutoff)]
   ' > "$ARCHIVE_DIR/closed-$DATE.json"

   COUNT=$(jq 'length' "$ARCHIVE_DIR/closed-$DATE.json")
   echo "Archived $COUNT closed issues to $ARCHIVE_DIR/closed-$DATE.json"

Monitoring Integration
----------------------

Prometheus metrics export:

.. code-block:: bash

   #!/bin/bash
   # prometheus-metrics.sh

   # Generate Prometheus-compatible metrics
   SUMMARY=$(issuedb-cli --json summary)

   echo "# HELP issuedb_issues_total Total number of issues"
   echo "# TYPE issuedb_issues_total gauge"
   echo "issuedb_issues_total $(echo $SUMMARY | jq '.total_issues')"

   echo "# HELP issuedb_issues_by_status Issues by status"
   echo "# TYPE issuedb_issues_by_status gauge"
   echo "issuedb_issues_by_status{status=\"open\"} $(echo $SUMMARY | jq '.by_status.open.count')"
   echo "issuedb_issues_by_status{status=\"in_progress\"} $(echo $SUMMARY | jq '.by_status.in_progress.count')"
   echo "issuedb_issues_by_status{status=\"closed\"} $(echo $SUMMARY | jq '.by_status.closed.count')"

   echo "# HELP issuedb_issues_by_priority Issues by priority"
   echo "# TYPE issuedb_issues_by_priority gauge"
   echo "issuedb_issues_by_priority{priority=\"critical\"} $(echo $SUMMARY | jq '.by_priority.critical.count')"
   echo "issuedb_issues_by_priority{priority=\"high\"} $(echo $SUMMARY | jq '.by_priority.high.count')"
   echo "issuedb_issues_by_priority{priority=\"medium\"} $(echo $SUMMARY | jq '.by_priority.medium.count')"
   echo "issuedb_issues_by_priority{priority=\"low\"} $(echo $SUMMARY | jq '.by_priority.low.count')"

Best Practices
--------------

1. **Use JSON output**: Always use ``--json`` for automation
2. **Check exit codes**: Handle failures gracefully
3. **Log operations**: Keep records of automated changes
4. **Use bulk operations**: More efficient than loops
5. **Test scripts**: Verify automation on test databases first
6. **Rate limit**: Don't overwhelm the database with rapid operations
7. **Backup first**: Before bulk operations, backup the database
