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
