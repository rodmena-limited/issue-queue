#!/usr/bin/env bash
# One gate, one answer.
#
# Written after committing "ruff and mypy clean" in a message where ruff had
# printed "Found 1 error". The check WAS run. The output WAS on screen. The
# failure was in the gap between reading and acting, under time pressure, on a
# fix judged urgent — the same gap `tracker-fbe1b4` fell into with a credential
# path an hour earlier, for the same reason. Neither of us lacked information.
#
# Their remedy, and it is structural rather than a resolution to try harder:
# make the check refuse to be ambiguous. Every tool below is silenced unless it
# fails, so there is no partial-success output to skim past. The only success
# this prints is one line, and nothing else prints it.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
report() {  # name, output, status
    if [ "$3" -ne 0 ]; then
        printf '\n=== %s FAILED ===\n%s\n' "$1" "$2"
        fail=1
    fi
}

out=$(python3 -m pytest -q 2>&1); report "tests" "$out" $?
out=$(.venv/bin/ruff check issuedb tests audit 2>&1); report "ruff" "$out" $?
out=$(python3 -m mypy issuedb 2>&1); report "mypy" "$out" $?

if [ "$fail" -ne 0 ]; then
    printf '\nGATE FAILED\n'
    exit 1
fi
printf 'GATE PASSED\n'
