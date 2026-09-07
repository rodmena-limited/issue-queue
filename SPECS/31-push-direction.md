# 31 — The push direction: local changes reach the server

Ticket: issuedb #14 — **BUILT in v2.33.0.**

## Why it mattered

`tracker-fbe1b4`, from the outside: *"`SyncClient.push` is fully written.
Nothing in `issuedb/` calls it — a working push client with no caller. So no
issue created in any developer's `.issue.db` can ever reach Tracker."*

Confirmed here: `_sync_command.py` had `push` 0 / `pull` 8, no `push`
subcommand, and zero call sites in the package. Tracker could only be populated
by typing into its web UI, so every product claim about sharing issues was
false in the outbound direction.

## How it is driven

`sync` is **bidirectional**, and a dry run reports **both** directions. That is
deliberate: sync reporting only the inbound half is how "no issue can ever leave
a laptop" survived unnoticed. Pull runs first under `--apply`, so a local row
the server already knows is reconciled before it is offered back.

## What travels

| local table | wire entity | uid |
|---|---|---|
| `issues` | `issue` | **minted** once, remembered in the ledger |
| `issue_dependencies` | `issue_dependency` | **derived**, `(project, blocker, blocked)` |
| `issue_relations` | `issue_relation` | **derived**, endpoints sorted for symmetric types |
| `issue_tags` | — | **refused** |

`issue_tags` is refused rather than sent: the outbox trigger records
`NEW.issue_id` as `local_id` and the ledger is keyed `(entity, local_id)`, so
two tags on one issue collide on one key and one would be sent under the other's
identity. That is issuedb #13 and it needs a schema change. **Reported as a skip
with its reason on every sync** — a silent omission here would be a lost tag
nobody could see.

## Three decisions worth keeping

**The outbox is an event log; the server wants current state.** Editing an issue
three times writes three outbox rows. Entries collapse to the last event per
`(entity, local_id)` — the same reasoning as `collapse_duplicate_uids` on the
way in. A delete after an insert collapses to the delete: the server never knew
the row, so sending both would be an insert it must immediately undo.

**A per-uid rejection inside a 200 is not success.** The outbox mark does not
advance past a rejected entry, so the change is offered again next sync rather
than lost with nothing erroring.

**A test double must not define the wire contract.** `SyncClient.rejected` is
reached through the client *module*, not through the module-level `SyncClient`
name a test may have substituted. Calling it on the stand-in would have proved
only that the double agrees with itself.

## Verification

Six tests in `tests/test_sync_push.py`, proven red by disabling the send (2 of 6
fail). They cover: a locally created issue reaching the client; a dry run
reporting without sending; a rejection not advancing the mark **and the change
being retried**; one uid surviving an edit; tags refused; three edits collapsing
to one entry.

**End to end against production Tracker**, not a fake:

```
issuedb-cli sync            WOULD PUSH 1 local change(s): 1 issue   (nothing sent)
issuedb-cli sync --apply    Pushed 1 change(s)
pull it back                number=910033  title='push probe … issuedb #14 end-to-end'
second sync --apply         "Nothing local to push."   (the mark advanced)
```

Probe row swept afterwards: live probe rows 0.
