# 25 — The NFC round trip, run live, and why its green is forced

Ticket: issuedb #12 (the standing NFC gap) — **round trip RUN. The gap it was
meant to close is NOT closed, and this records why.**

## What was asked

`tracker-manager-0e2462` specified the decisive protocol:

1. push a tag whose name is the **decomposed** form, note the uid we derived
2. pull it back, record the uid the **server** stored
3. push the **composed** form as a separate request
4. the server must answer `existing`, version unchanged — **not** `created`

## What was run

`audit/evaluations/nfc_round_trip.py`, live against
`https://tracker.rodmena.co.uk`. Every control they asked for fired:

```
CONTROL  novel uid every run                     yes (uuid4 per run)
CONTROL  the two normal forms differ as bytes    b'cafe\xcc\x81-…' vs b'caf\xc3\xa9-…'
CONTROL  ASCII pair, pushed identically          created -> existing   <- replay detection works THIS run
```

Result, exactly as their protocol predicts:

```
STEP 1  push decomposed          -> created, version 1
STEP 2  uid WE derived            s256t128:a64bc03039058cf8b921e3c85dcea265
        uid SERVER stored         s256t128:a64bc03039058cf8b921e3c85dcea265
STEP 3  push composed            -> existing, version 1
STEP 4  'existing', version unchanged
```

## Why that green proves less than it looks like

The probe establishes the premise **before** the test rather than recalling it,
because the whole verdict hangs on it:

```
PREMISE  we sent    s256t128:9d4c92e0f40044b7bfd9e22e38408f0b   (novel, random)
         feed holds s256t128:9d4c92e0f40044b7bfd9e22e38408f0b
         server derives its own uid: FALSE
```

**The server stores the uid the client sends.** Measured this run, with a novel
value, read back from the feed rather than from the push response. So both
pushes in steps 1–3 key off *our* derivation, and step 4's `existing` was
decided before step 1 ran. **A server that does not normalise at all returns the
same green.**

- **PROVED**: issuedb derives one uid for both normal forms, and no duplicate is
  created through the push path.
- **NOT PROVED**: that Tracker's own derivation normalises.

Settling it needs a surface where the **server** derives the uid — the web UI
creating a tag — and its uid compared against ours. That is unchanged from
`SPECS/12`, and this run is evidence for it rather than a substitute.

## Three things the run turned up on the way

**1. `outcome: "gone"` is a real response value.** The first premise attempt used
an all-`f` constant, which an earlier probe had already consumed:

```
{'outcome': 'gone', 'deleted': True, 'restorable': True, 'tombstone': {...}}
```

Not in any vector. The probe reported PROBE BROKEN and refused to continue,
which is the correct behaviour, but the constant also violated the manager's own
"novel uid each run" control — a fixed value passes on history. Now uuid4.

**2. `outcome: "updated"` when the content hashes differ.** With `rt-nfd` and
`rt-nfc` as the two content hashes, step 3 returned `updated` and version 2, not
`existing`. Same row, no duplicate — but a different statement about what the
second push did. Their protocol assumes identical hashes; the probe now matches
that and reports `updated` distinctly rather than folding it into the pass.

**3. Deleting an issue over sync does not cascade to its tag rows.** Measured
across the whole feed:

```
live issue_tag rows            216
  attached to a LIVE issue     213   <- control, non-zero
  attached to a TOMBSTONED one   3
  issue_uid not in the feed      0
```

All three were ours — tags our sweep left behind when it deleted 16 probe issues
without their attachments. **Our own cleanup was incomplete**, and no genuine row
is affected. Stated narrowly: a replica applying this feed would create a tag
pointing at a deleted issue. Whether the cascade belongs to the server or the
client is Tracker's call, not ours to assert. Swept: 216 -> 213 live tag rows,
0 orphaned, 209 live issues unchanged.
