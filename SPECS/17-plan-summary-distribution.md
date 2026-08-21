# 17 — The sync plan summary hides the distribution behind a count

Ticket: issuedb #17 — **OPEN, NOT STARTED.**

## Why

`_apply.py:415` renders the plan summary by counting **action kind** only:

```
314 change(s): 237 create, 77 skip
```

All three skip reasons collapse into that one number, and they are
operationally different:

| Reason | What the user should do |
|---|---|
| `issuedb does not apply entity 'issue_tag' yet` | wait for a client release |
| `an endpoint issue is not present locally` | nothing — it resolves next sync |
| `tombstone for a row we lack` | nothing — already converged |

A user reading `77 skip` cannot tell "77 things are broken" from "77 things are
fine". The number is accurate and the answer it gives is not.

## Where the rule came from

`tracker-manager-0e2462`, 2026-08-21. Their dashboard audit reported **50/52
rows name their project**, which reads as nearly done. The two misses were the
focus cards *above the fold* — the first two tickets anybody sees. Same
measurement, opposite conclusion. Their line:

> a count of 50/52 does not tell you WHICH two

**An aggregate hides distribution, and the distribution is often the finding.**

## EARS SPEC

- When the sync plan summary reports skipped changes, it shall state the reason
  categories and the count in each, not a single total.
- The summary shall name which entity types were skipped, so that a user can
  tell an unimplemented entity from a missing endpoint from a tombstone for an
  absent row.
- The summary shall remain a single line per category, so that naming the
  distribution does not restore the wall of per-row output the summary exists
  to replace.
