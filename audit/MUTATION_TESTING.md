# Mutation testing in this repo — a hazard that fakes a survivor

A mutation that **appears to survive** may be a stale `.pyc`, not a gap in the
tests. This has produced two false survivors in this repo already.

## The mechanism

CPython's default bytecode invalidation is **timestamp-based with one-second
granularity**. It compares the source's mtime against the mtime recorded in the
cached `.pyc`. A mutation script that writes a file **within the same second**
as the existing cache entry therefore looks *unchanged*, and Python runs the
**old bytecode** — so the test suite passes and the mutation is reported as
having survived.

Mutation testing is exactly the workload that hits this: a tight
write → run → restore → write loop, many times per second.

It is the same defect class the tests themselves exist to catch — **a check
that cannot go red** — sitting in the harness rather than in the code.

## The rule

Run every mutation with bytecode writing disabled:

```bash
export PYTHONDONTWRITEBYTECODE=1
find . -name '__pycache__' -type d -not -path './venv/*' -exec rm -rf {} +
```

And assert the mutation landed **on disk**, not just that the script exited 0:

```python
intended = s.replace(old, new)
p.write_text(intended)
assert p.read_text() == intended, "POSTCONDITION FAIL: file does not match the intended text"
```

**Equality, not substring.** The weaker form —
`assert new in after and old not in after` — breaks whenever the replacement
legitimately contains part of the find string, which is common when a mutation
narrows a condition rather than deleting it. Reading the file back and
requiring it to *equal* the intended text has neither failure mode. Adopted
from Tracker's `falsify.py`, where two of their mutations hit exactly that case.

**Refuse a mutation whose find == replace.** A no-op scores as a survivor, and
it is the purest form of the whole problem: a check that changed nothing,
reporting that nothing broke.

The postcondition catches a mutation that never applied. `PYTHONDONTWRITEBYTECODE`
catches one that applied and was ignored. **Both are needed** — they fail in
different places and neither implies the other.

## The asymmetry worth remembering

| Result | Trustworthy? |
|---|---|
| Mutation went **RED** | **Yes, self-proving.** Neither a stale cache nor an unapplied edit can turn a suite red. |
| Mutation **SURVIVED** | **No.** Indistinguishable from one that never applied, or applied and was ignored. |

So only survivors need re-verification — which is what makes the audit cheap.

## The same failure one layer down: a stand-in with more power than the real thing

The stale `.pyc` is one instance of a wider rule, and the wider rule is the one
worth carrying:

> **A stand-in that cannot fail the way the real thing fails cannot test it.**

Tracker hit this in a form this repo's rules did not cover. Their `issue_tag`
push returned HTTP 500 in production —
`InsufficientPrivilegeError: permission denied for table issue_tags`. The
application role held `SELECT, INSERT, DELETE` and needed `UPDATE`: the grant
was correct for a pure membership row, and the sync work then added
`row_version`/`deleted_at`/`sync_content_hash`, which made the row updatable.
**No test in their suite could have seen it** — the suite connects as the
database OWNER, because its fixtures seed orgs and projects and seeding is an
operator action. An owner has every privilege, so every privilege bug was
invisible in test and immediate in production.

This repo's standing rule was:

> FakeTracker may be smaller than the server, never more permissive.

That covers **permissiveness** and does not cover **privilege**, **freshness**,
or **reach** — a stand-in can be exactly as permissive as the real thing and
still be unable to fail, because it runs with capabilities the real caller does
not have. The widened rule:

> **A stand-in must be no more capable than what it replaces — in permission,
> in privilege, in freshness, and in access.**

Where this bites in *this* repo, and what is done about each:

| Stand-in | Extra capability it could have | State |
|---|---|---|
| `FakeTracker` vs the real server | accepting a payload the server rejects | guarded by replaying the same vendored vectors against **both** |
| The vendored contract | drifting behind the deployed one | guarded by `schema_drift.py`, which prints `VENDORED_AT` and diffs against the served build |
| A test that opens `.issue.db` directly | bypasses the CLI's validation, migrations and lifecycle | **partly open** — sync/apply tests still assert on rows; the CLI path is exercised separately rather than in the same test |
| A probe reading a fixture | is not evidence about the server at all | guarded by printing `SERVED COMMIT` on every real-server run |

Tracker closed theirs the right way and it is the pattern to copy: open a
connection **as the constrained principal**, with only what the migrations
grant, and run the **real** functions through it — not a privilege matrix
restated by hand, which is a second source of truth that drifts. Then prove it
goes RED (revoke the grant, watch the probe fail) before trusting it green.

## Confirmed genuine survivors

- `os.fchmod` in `issuedb/sync/_credentials.py`: re-verified with bytecode
  disabled and a disk postcondition. It is genuinely a no-op — `tempfile.mkstemp`
  creates 0600 regardless of umask and `os.replace` preserves the source mode.
  The *property* is still guarded: swapping `mkstemp` for a naive `open()` takes
  four tests red.
