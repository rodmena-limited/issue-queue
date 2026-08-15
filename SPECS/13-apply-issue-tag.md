# 13 — Apply `issue_tag` changes (needs a ledger redesign)

Ticket: issuedb #13 — **OPEN, NOT STARTED.**

## Why

The apply path now consumes issues, relations and dependencies. `issue_tag` is
the last entity the server advertises that it does not. A sync reports tag
changes as `SKIP — issuedb does not apply entity 'issue_tag' yet`.

## The blocker

`sync_row` is keyed by `(entity, local_id)`. `issue_tags` has **no `id`
column** — its primary key is `(issue_id, tag_id)`, and the outbox trigger uses
`issue_id` as `local_id`. Two tags on one issue would therefore collide on
`(issue_tags, issue_id)` in the ledger: two uids, one key.

The clean fix is an `id` column on `issue_tags` (a migration), so the ledger
keys tag uids the way it keys relations and dependencies. That also touches the
trigger and the push side.

## EARS SPEC

- The apply path shall consume `issue_tag` changes, so that a sync applies tags
  as well as issues, relations and dependencies.
- When a tag change references an issue, the apply shall resolve the issue uid
  to a local issue id.
- When a tag name is not present locally, the apply shall create the tag before
  attaching it.
- The ledger shall be able to hold more than one tag uid for the same issue, so
  that two tags on one issue do not collide.
