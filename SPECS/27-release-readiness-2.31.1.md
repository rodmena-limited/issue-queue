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

## REQUIRED after publishing — this record is one step short without it

`financial-freedom-projec-195737` pointed out the gap, and it is the same
distinction one level further out. The check above installed **the locally built
wheel**. That is the builder's experience, not the user's.

So if a release is made, the release is not done until:

```
python3 -m venv /tmp/verify && /tmp/verify/bin/pip install issuedb    # from PyPI, not a local file
/tmp/verify/bin/python -c "import importlib.metadata as m, issuedb; \
    print(m.version('issuedb'), issuedb.__version__)"                # both records must agree
/tmp/verify/bin/issuedb-cli --help | grep -E '^\s+(sync|signin|whoami)'
```

**That is the check that found the 2.12.0 bug in the first place** — a peer
installing from PyPI on a different machine — and it is the one that reproduces
what a user gets rather than what the builder produced. A green here means fixed
*for everyone*; a green on a local wheel only means fixed in a place users cannot
reach, which is the exact failure this whole file is about.

Merging is not deploying, and building is not publishing.

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

---

## UPDATE 2026-08-24 — the cost is no longer theoretical, and there is a second risk

### A real user is blocked

`todo-app-maker-5c0942` reported a user unable to sync a local `.issue.db` to
Tracker. Their diagnosis was correct and their install was fine:

```
PyPI latest (re-queried)     2.12.0
sync landed in source        2026-08-15
source version now           2.32.0
```

`signin` and `sync` are absent from every published build on every machine.
Tracker's `/setup` page tells users the commands ship in **2.16.0** — a release
that does not exist.

### The git workaround does not exist either, and would have failed silently

The obvious answer is "install from git instead of PyPI". Checked before
recommending it:

```
git ls-remote https://github.com/rodmena-limited/issue-queue
  refs/heads/main   4152819        <- 112 commits behind local
  newest tag        v2.12.0        <- exactly matches PyPI
  contains issuedb/sync/ ?         NO
```

`pip install git+https://...` would have installed cleanly, looked like it
worked, and had no sync command — **worse than the error it replaced**, because
the error at least tells the truth. Not offered.

### THE SECOND RISK, WHICH IS LARGER THAN THE PUBLISHING QUESTION

```
main...origin/main [ahead 112]
remote newest   4152819   2026-07-25
local newest    961cf11   2026-08-24
```

**112 commits exist only on this machine.** Not merely unpublished — *unpushed*.
That is the whole sync implementation, the apply paths, the derived-identity
work, the duplicate-uid fix, the file-size ratchet, and every SPECS record from
the Tracker collaboration, in one copy on one disk.

This is independent of the release decision and cheaper to resolve: `git push`
releases nothing (the repo has no CI workflows to trigger) and removes the
single-copy risk. Both remain operator decisions and neither has been taken here.

