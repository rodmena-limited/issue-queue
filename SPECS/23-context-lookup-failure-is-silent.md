# 23 — A failed commit lookup was indistinguishable from no commits

Ticket: issuedb #23 — **FIXED, tests proven red, both surfaces covered.**

## Why

`tracker-manager-0e2462` named the shape while narrowing one of their own
confirmations:

> The removal partially failed, the catch swallowed it, and ~156 MB stayed
> behind **while the code read as if it had cleaned up**.

They counted three instances in three subsystems. Checked this repo for the
same thing and found it in a **read** path rather than a teardown.

An AST walk over the package (76 files, **97 except handlers** — both controls
non-zero) found 3 silent `except …: pass` handlers. One is a benign format
fallback that re-raises at the end. The other two are the git enrichment in
`/api/issues/<id>/context`.

Measured through the endpoint, not the code:

```
KNOWN POSITIVE      branch='main'  commits=3
git log TIMES OUT   branch='main'  commits=0
```

The branch field is still populated, so **the response looks entirely
successful** while the commit list is empty. A caller cannot tell *"no commit
mentions this issue"* from *"the search did not run"* — and the consumer is an
agent deciding whether work has been committed.

## EARS SPEC

- When the commit lookup for an issue fails or times out, the context API shall
  report that the lookup did not complete, so that an empty commit list is not
  read as a definite absence.
- While the commit lookup has failed, the context API shall still return the
  rest of the git context it did obtain.
- The context API shall state, for each git sub-lookup it reports, whether that
  lookup completed.

## The fix, and the bug inside the first version of it

`commits_lookup_ok` on the API block; `related_commits_lookup_ok` on the CLI's
`git_info`.

**The first version keyed only off the exception handlers, and therefore lied.**
`git log` exits **128** on an unborn branch, which is not an exception — so a
freshly initialised repository reported:

```
{"branch": "main", "commits_mentioning_issue": [], "commits_lookup_ok": true}
```

A flag asserting, falsely, that the search had run. That is the same defect the
ticket is about, reproduced one branch over inside its own fix, and it was found
only by testing the ordinary case rather than the exotic one.

Corrected to treat a non-zero exit as a failed lookup:

```
COMMITLESS   commits_lookup_ok false   commits []
WITH COMMIT  commits_lookup_ok true    commits [{"hash": "6e6f55e", …}]
```

## A deliberate divergence between the two surfaces

The CLI reports `true` in a commitless repo and the API reports `false`. **This
is correct, not a second bug.** The CLI searches with `git log --all`, which
exits 0 on an unborn branch — it really did search every ref and find nothing.
The API omits `--all` and gets 128. `test_cli_context_reports_the_same_signal`
pins the difference so it cannot drift silently.

## Verification

Five tests in `tests/test_context_api_degradation.py`, each shown to fail
against the unfixed code:

```
flag removed entirely      3 failed  (KeyError: 'commits_lookup_ok')
returncode branch reverted 1 failed  (assert True is False)
```

### The first version of these tests could never have run

They guarded on `if git is None: pytest.skip("not run inside a git work tree")`
and skipped **on every machine** — `tests/conftest.py:22` chdirs each test into
`tmp_path`, which is not a work tree. Three tests that can never run report
exactly like three tests that pass.

They now build their own one-commit repository in the temp cwd, with
`GIT_CONFIG_GLOBAL=/dev/null` so a developer's `~/.gitconfig` cannot decide the
outcome, and assert rather than skip.
