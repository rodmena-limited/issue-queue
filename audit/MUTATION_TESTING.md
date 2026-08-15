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

## Confirmed genuine survivors

- `os.fchmod` in `issuedb/sync/_credentials.py`: re-verified with bytecode
  disabled and a disk postcondition. It is genuinely a no-op — `tempfile.mkstemp`
  creates 0600 regardless of umask and `os.replace` preserves the source mode.
  The *property* is still guarded: swapping `mkstemp` for a naive `open()` takes
  four tests red.
