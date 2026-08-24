# 28 — A uid served twice in one walk created two rows and two ledger entries

Ticket: issuedb #26 — **FIXED in v2.32.0.**

## How it was found, which matters more than the bug

`tracker-manager-0e2462`, reviewing *their* pagination fix, recommended asserting
**distinct count and no duplicates** rather than a page count, because *"a client
that reads every page and applies only the first still gets the count right."*

Our pagination tests asserted that rows from page 1, 2 and 3 **arrive**. None
asserted that a row arrives **once**. Writing that test found a real defect here.

### The first version of the test was vacuous, and its control said so — wrongly

It duplicated a row at the **same seq**. `pull` filters `seq > cursor`, so the
duplicate was **never served twice**, and the test passed while proving nothing.

The control was there and it checked the wrong object: it counted occurrences in
the **fixture list** rather than in **what pull delivered**. Fixed to assert on
`served_pages`, so the control fails if the stimulus never happens.

A mutation confirmed the confusion: disabling `already_applied` did **not** break
the test, which should have been the signal that nothing was being exercised.

## The defect

The feed is one row per uid carrying current state, and **seq advances on
change** — so a row touched between page 1 being served and page 3 being served
appears on both, under two seqs. That is the documented semantics, not a server
fault.

The plan is computed for the **whole feed before anything is applied**, so both
occurrences read as "not present locally":

```
451 changes -> 451 CREATE actions
'issue 200' rows in issues : 2
sync_row rows for one uid  : 2      <- identity is no longer one-to-one
```

The ledger exists to map one uid to one local row. Two entries for one uid means
a later pull can resolve that uid to either row, and a push would send the same
logical row under two identities.

## EARS SPEC

- When one pull walk delivers the same uid more than once, the sync plan shall
  produce at most one action for that uid, so that a row touched mid-walk does
  not become two local rows.
- Where a uid appears more than once in a walk, the plan shall act on the
  occurrence with the highest seq, because the feed carries current state and
  the later occurrence is the newer one.
- The ledger shall hold at most one live row per uid, so that identity remains
  one-to-one.

## The fix

`issuedb/sync/_feed.py` — `collapse_duplicate_uids()`, applied before the plan
sees the walk. Highest seq wins; first-appearance order is preserved so
endpoints are still planned before the rows referencing them. **Changes with a
missing or non-string uid are deliberately not collapsed** — each must reach the
plan and be reported, since those are malformed-row reports the operator needs.

Proven red by removing the collapse: `test_a_uid_repeated_across_pages_lands_exactly_once`
fails with `a uid served on two pages landed 2 times`.

## The cap guard caught its own author

The fix pushed `_apply.py` from 598 to 602 lines and
`test_grandfathered_files_do_not_grow` failed — the ratchet from #24 biting the
change that had just been written. The rule says extract rather than append, so
`_feed.py` (61) and `_endpoints.py` (37) were split out and `_apply.py` came down
to **577**.

The baseline was then **re-tightened to 577**. Leaving 598 would hand back the
slack just recovered; a ratchet only ratchets if it is re-tightened, and that is
now stated in the file.
