# Tracker sync feed semantics (established 2026-08-22, on the wire)

Not a ticket — a property of the counterparty, derived by measurement across
two implementations, recorded here because a client that assumes otherwise
breaks silently.

## The statement

> **A replica cannot reconstruct history from this feed, but it always
> converges to current truth, and it learns each change once.**

`tracker-fbe1b4` is adding this wording to `contracts/sync/PROTOCOL.md` as the
stated feed semantics.

## How it was established, including the wrong turn

**First measurement, correct:**

```
total changes in feed         : 663
distinct uids                 : 663
uids appearing MORE THAN ONCE : 0
```

One row per uid — current state, not a change log. **The inference drawn from
it was wrong**: that a replica therefore could not learn a deletion
incrementally, because there is no create-then-tombstone pair to replay.

**Second measurement, which settled it:**

```
before delete : seq 1075, live
after delete  : ONE row for that uid at seq 1076, deleted=true; the 1075 row is GONE
whole feed    : 664 changes, 664 distinct uids, 0 appearing twice
```

**The row's seq advances on change.** One-row-per-uid *and* the row re-enters
above the watermark when it changes. The cursor is a **watermark over seq**,
not an index into a log — which is exactly what makes an incremental pull
deliver a deletion without replaying anything.

## Three assertions, not one

Tracker pinned this in their suite, and the structure is the point — the
obvious assertion alone passes against a broken feed:

| assertion | what it rules out |
|---|---|
| nothing arrives above the cursor while nothing has changed | a feed that **replays everything** on every pull |
| after a change, **exactly one** copy arrives above the held cursor | duplicate or missing delivery |
| the uid still appears **once** in the whole feed | the feed quietly becoming a change log |

Shown red by making an upsert keep its old `sync_seq`: *"a replica holding a
cursor from before the change received 0 copies of it; incremental delivery is
broken."*

**Our own confirmation was incomplete.** We verified that a *change arrives*
(`c:1075` → seq 1076, one change) and never verified that **nothing** arrives
when nothing has changed. Checked afterwards:

```
walked to head of feed          : cursor c:1068
immediate re-pull from the head : 0 changes, has_more=False
```

It holds — but "the change arrived" is satisfied by a feed that replays
everything, so that assertion was doing less work than it appeared to.

## Why it matters to this client

A future change that forgets to bump `sync_seq` stops delivery to every replica
and **nothing errors**: the row is correct locally, the feed simply never
mentions it again. That is the write-only failure class this collaboration hit
four times in one session.
