# 24 — Ten files breach the 550-line hard cap

Ticket: issuedb #24 — **OPEN, NOT STARTED.** Filed, not fixed: nine refactors
is a scoped piece of work, not a drive-by.

## Why

The standing rule is **500 lines soft, 550 hard** for source files, excluding
generated artifacts, fixtures, lockfiles and data blobs. Measured across
`issuedb/`, `audit/` and `tests/`:

```
922  tests/data/faketracker.py            <- FIXTURE, exempt
746  audit/evaluations/first_contact_probe.py
676  tests/test_git_integration.py
615  tests/test_similarity.py
598  issuedb/sync/_apply.py                <- shipped package
593  issuedb/cli/_main.py                  <- shipped package
591  tests/test_sync_apply.py
575  tests/test_web.py
561  tests/test_time_tracking.py
554  tests/test_code_refs.py
```

Nine files over the hard cap once the fixture is excluded, **two of them inside
the shipped package**. All pre-date this session; `first_contact_probe.py` was
718 lines before the cleanup fix pushed it to 746.

## EARS SPEC

- The repository shall keep every source file at or below 550 lines, so that no
  file crosses the project's hard cap.
- Where a file exceeds 500 lines, the repository shall record it as due for
  refactoring before it is extended further.
- If a source file would cross 550 lines, then the change shall split or
  extract instead of appending.

## Note on splitting the probe

`first_contact_probe.py` has been split once before in this session and the
split was wrong twice — both attempts printed `ROUND TRIP FAILED` against a
working server because the extracted boundaries cut through shared state. Any
split of that file needs the round trip re-run against the live server
afterwards, not just an import check.

## Suggested enforcement, and the trap Tracker already fell into

A test asserting the cap would keep this from recurring, and unlike the audit
above it would run on every commit. It must be written with a known-positive:
a cap test that reports zero because its glob matched nothing looks exactly
like a clean repository (see `SPECS/verification-gaps.md`, entry 14).

**And the enumeration must include untracked files.** `tracker-fbe1b4` shipped
this exact guard tonight and it enumerated with `git ls-files`, so:

```
untracked 800-line file    -> "0 NEW hard breach(es)"  PASSED
git add -N, nothing else   -> "NEW BREACH 799 ..."     FAILED
```

Fixed with `--cached --others --exclude-standard`, which picks up untracked
files while still honouring `.gitignore`.

The failure is not the flag; it is that **all three of their controls padded a
file that was already tracked.** A padded file tests *growth* and can never test
*arrival* — it was in the population before the test began. `tracker-manager-0e2462`
put it exactly: *"a padded file never tests membership."*

And the timing makes it the default path rather than an edge case: the normal
order of work is write the file, run the gate, then `git add`. **The gate runs at
the precise moment a new file is invisible to it.**

So this repo's guard must:

1. enumerate the filesystem, or use `--cached --others --exclude-standard`;
2. carry a **membership control** — create an oversized file, assert it appears
   in the enumeration, remove it under a trap — not only a size control;
3. not have the fix pattern-matched across every other guard. Tracker swept
   theirs and found `probe_design_tokens` uses `git ls-files` **correctly**,
   because there tracked-ness is the property under test: `deploy.sh` ships
   `git archive`, so an untracked font ships as a 404.
