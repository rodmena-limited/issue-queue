# 19 — Attaching a tag is not atomic; a failed attach orphans an unremovable tag

Ticket: issuedb #19 — **OPEN, NOT STARTED.**

## Reproduced, with a control

```
registry before      : []
after normal attach  : ['normal-tag']       <- CONTROL: a good attach registers the tag

provoke a failure on the SECOND write (drop issue_tags), attach again:
attach raised        : OperationalError
registry after fail  : ['normal-tag', 'should-not-survive']    <- ORPHAN
```

## Mechanism

`_tags.py:76` `add_issue_tag` performs **two separate writes**:

1. `create_tag()` commits the registry row in its own connection context.
2. `INSERT INTO issue_tags` — the edge — happens later, in a different context.

A failure on the second leaves the first committed.

## And the orphan cannot be removed through the product

`remove_issue_tag` (`_tags.py:131`) deletes only from `issue_tags`. The CLI
exposes `tag list` / `add` / `remove` and **no command deletes a tag from the
registry**. So a failed attach permanently adds a tag that nothing uses and
nobody can remove — the same shape as Tracker's, where the NFC-collision 500
orphaned a row every time it fired.

## EARS SPEC

- When a tag is attached to an issue, the repository shall write the tag
  registry row and the issue-tag edge in a single transaction.
- If the edge write fails, then the tag registry row shall not persist.
- The product shall provide a way to remove a tag from the registry, so that an
  orphan is recoverable if one is ever created.

## How it was found, and the trap in testing it

Reported by `tracker-fbe1b4` as a defect in **their** code; checked here rather
than assumed to differ. It did not differ.

Their warning is worth carrying into the fix: **their first test for it was
vacuous.** They sent a 300-character name, which Pydantic rejected *before any
write*, so the test passed with **and** without the transaction. They found out
only by reverting the fix to check it went red. The provocation has to fail the
**second** write specifically — validation rejecting the input never exercises
the path.

## A SECOND, larger defect in the same area: a normal detach also leaves the tag

`tracker-manager-0e2462` measured this on Tracker after we predicted it from
our own seven tombstoned-but-still-registered tags:

```
1. create + attach "orphan-semantics-5d1c"   issue_count 1
2. detach — a normal, successful 204
3. registry row still present : TRUE   issue_count 0   orphans 7 -> 8
4. removed it again           : orphans back to 7
```

**A plain attach-then-detach leaves a registry row.** No 500, no failed write,
no bug — just ordinary use. So two different things wear one label:

| | |
|---|---|
| **LEAKED** | a registry row whose edge write *failed* — the defect this ticket is about |
| **UNUSED** | a tag legitimately on no issue right now — normal, and possibly *wanted*, since tags are project-scoped and reusable |

Of their ten orphans, exactly **one** came from a failed attach. The other nine
were residue of successful create-then-detach cycles.

### What this means for issuedb

We have the same shape: `remove_issue_tag` deletes the edge and leaves the
`tags` row, and there is no CLI command that removes a tag from the registry.
So issuedb also accumulates unused tags through ordinary use, and `tag list`
will show them forever.

**That is arguably correct** — a reusable project-scoped tag should survive
losing its last issue — but it must be a *decision*, not an accident, and there
must be a way to remove one. Both halves of this ticket's third EARS clause
still apply.

**Do not conflate the two counts.** A number that mixes "rows a bug leaked"
with "tags nobody is using today" alarms without informing, and grows with
normal use while never shrinking on its own.

### We cannot adopt the leaked/unused taxonomy without a tombstone first

Tracker can distinguish the two because their detach writes a **tombstone**, so
a registry row with no *live* edge still has a *deleted* edge behind it.
Verified in our schema:

```
issue_tags columns : ['issue_id', 'tag_id', 'created_at']
rows after detach  : 0
```

**No `deleted_at`, and the row is gone — our detach is a hard delete.** So in
issuedb "a tag with no edge" cannot distinguish:

| | |
|---|---|
| **LEAKED** | the edge write failed and never existed |
| **UNUSED** | the edge existed and was deleted |

That is a real dependency: adopting the taxonomy here requires adopting the
tombstone first. Their `331d3a1` was written to fix *replication* and turned out
to be what makes the distinction representable at all.

### A `leaked` count is only meaningful if the condition can be manufactured

Tracker reports `leaked: 0` and correctly flagged it as **unfalsifiable from
outside** — their attach is now atomic, so no leaked row can be produced through
the product to prove the bucket can ever be non-zero.

We can still produce one, because this ticket is unfixed:

```
normal attach          -> tag with 1 edge          (in_use)
normal detach          -> tag with 0 edges         (unused, on their schema)
attach with the edge write forced to fail -> tag with 0 edges   (leaked)
```

**The test must inject the failure** — drop or deny the edge write — rather than
rely on a live bug, because the fix removes the only natural way to reach the
state. A bucket whose condition disappears when the bug is fixed needs a
synthetic provocation or it becomes decoration.
