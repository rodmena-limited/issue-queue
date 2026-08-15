# Ambiguous issue references: present every candidate, select none

- **Ticket:** issuedb #6
- **Versions:** 2.17.0 (resolver), 2.18.0 (git-scan + CLI wiring)
- **Modules:** `issuedb/sync/_references.py`, `issuedb/sync/_ledger.py`, `issuedb/git_repository.py`, `issuedb/git_cli.py`
- **Tests:** `tests/test_sync_references.py`, `tests/test_git_scan_ambiguity.py`

## EARS spec

- When a local issue number resolves to exactly one issue, issuedb shall resolve the reference to that issue.
- If a local issue number resolves to two or more distinct issues, then issuedb shall present every candidate and shall select none.
- If a local issue number resolves to no issue, then issuedb shall report the reference as unknown and shall not silently omit it.
- When issuedb scans git commits, issuedb shall check a reference for ambiguity **before** taking any action on it.
- If a scanned reference is ambiguous, then issuedb shall create no link, shall close no issue, and shall report the reference with every candidate.
- When a scan encounters an ambiguous reference, issuedb shall continue processing the remaining commits.
- The issuedb reference resolver shall never choose a candidate on the user's behalf, including when one candidate is newer or more recently updated.
- The issuedb reference resolver shall depend on the Python standard library only.

## Why this is not a display concern

`git-scan --auto-close` **closes issues** based on `#N` parsed out of a commit
message. Two clones of a repo that commits `.issue.db` allocate that number
independently — reproduced, both minted a different issue `#3`.

So acting on an ambiguous reference does not mislabel something. It **closes
somebody else's issue**, and nothing errors when it does. For an automated
action, "select none" has to mean *do nothing and report*: a scanner that picks
the local candidate because it is the one it can see is choosing, and the choice
is invisible in the output.

Ambiguity is checked **before** the issue lookup. The local candidate is always
findable, so a lookup-first scanner would act on it and never reach the check.

## Verification

`ambiguous_refs` is a first-class count on the scan result and gets its own
summary line. Buried in `details`, "Closed 0 issue(s)" reads as *nothing to do*
rather than *I refused to guess*.

Rendered through the real CLI:

```
Scanned 1 commit(s)
Created 0 link(s)
Closed 0 issue(s)
SKIPPED 1 ambiguous reference(s) - issuedb did not choose

Details:
  - Commit abc123de, Issue #1: ambiguous (#1 matches 2 issues; issuedb will not choose)
      candidate [aaaaaaaaaaaa] #1: fix login timeout
      candidate [bbbbbbbbbbbb] #118: (not present locally — pull to see it)
```

### Mutations

| Mutation | Result |
|---|---|
| Ambiguity check removed | 6 failed |
| **Reports the ambiguity but acts anyway** (`continue` dropped) | 4 failed |
| `ambiguous_refs` never incremented | 2 failed |
| `resolved()` returns the first candidate | 3 failed |
| Aliases ignored entirely | 8 failed |
| uid de-duplication dropped | 1 failed |

The second is the subtle one: warning the user *and doing it anyway* is the
version a hurried implementation produces, and it looks correct in the output.

A **positive control** (`test_an_unambiguous_reference_is_still_linked_and_closed`)
guards the opposite failure — a scanner that refused *everything* would pass every
test above while making `git-scan` useless.

Gates: 795 tests pass, mypy clean over 72 source files, ruff clean, stdlib only.

## Agent guidance

`PROMPT.txt` instructs agents that an `ambiguous` result is **correct behaviour,
not a failure**: do not retry, do not pick a candidate, do not suggest a flag to
force it. Without that, an LLM agent hitting the refusal would work around the
guard, which is exactly what it exists to prevent.
