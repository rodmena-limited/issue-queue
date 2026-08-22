# 27 — Release readiness: does publishing fix the frozen bug or reship it?

Not a ticket. A recorded measurement for an operator decision.

## Why this needed checking at all

`tests/test_version_consistency.py` asserts that `pyproject.toml` and
`issuedb.__version__` agree. It passes. **That is a statement about the source
tree, and the wheel is what ships** — a different artefact, produced by a build
step the test never runs. The published 2.12.0 is the proof that the two can
diverge: it carries `metadata 2.12.0` beside `__version__ 2.11.0`.

So "the test passes, therefore a release would be consistent" is exactly the
source-versus-served inference this repo's rules forbid. Measured instead.

## Measured on the built artefact, in a clean venv

```
python3 -m build            -> issuedb-2.31.1-py3-none-any.whl, issuedb-2.31.1.tar.gz
pip install <the wheel>     into a fresh venv, nothing else present

  metadata     2.31.1
  __version__  2.31.1
  CONSISTENT   True
  subcommands  sync · signin · whoami   present
  update -s    wont-do                  present
```

### The control — the same checks must be able to say NO

Same venv, force-reinstalled from PyPI:

```
issuedb==2.12.0
  metadata 2.12.0 / __version__ 2.11.0   consistent: False
  sync/signin/whoami subcommands: 0
```

Both checks report the defect on the published build and its absence on the new
one, so neither is a check that can only say yes.

## What this establishes, and what it does not

**Establishes:** a release built from `2.31.1` would ship consistent version
records, `sync`, and the full documented lifecycle. Publishing would *fix* the
frozen 2.12.0 defect rather than ship a second instance of it.

**Does not establish:** that publishing is the right call, that the changelog or
docs are release-ready, or anything about upload credentials. **Publishing is an
outward-facing, effectively irreversible action** — a version number, once taken
on PyPI, cannot be reused — and it is the operator's decision. Nothing here was
uploaded.

## Context: the cost of the current hold

PyPI's newest issuedb is **2.12.0**; source is **2.31.1**. Nineteen minor
versions are unpublished, found by `financial-freedom-projec-195737` while
diagnosing their own install. Every `pip install issuedb` on any machine gets a
build with inconsistent version records, no sync, and none of the work since.

A defect that is fixed only in an unreachable release presents to a user exactly
as an unfixed one — and worse, because anyone investigating finds a passing test
and concludes the fault is theirs. That is very nearly what happened here: this
session diagnosed its own PATH install as broken when it was byte-for-byte the
newest artefact that exists.
