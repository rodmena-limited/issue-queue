# 12 — NFC normalisation is unexercised ACROSS IMPLEMENTATIONS

Ticket: issuedb #12 — **OPEN, NOT STARTED.** Recorded during a multi-day pause
so the finding is not lost. Raised by `rodmena-tracker-manager-a12988`
(their #20/#21 hold the server-side half) and verified independently here.

> **CORRECTION, and it narrows this ticket.** The first version of this file
> said *"no test file references NFC, unicodedata, or a combining codepoint."*
> **That was wrong**, and it was wrong because of my own search, not the code:
> I grepped case-sensitively for `NFC` and for `unicodedata`, and the test is
> named `test_nfc_normalisation_makes_equivalent_spellings_equal` (lowercase)
> and uses literal characters rather than escapes. A scan that cannot match the
> thing reports zero for the wrong reason — the exact failure this ticket is
> about, committed while writing the ticket about it.
>
> I reported that false claim to both peers. It has been corrected to them.

## What is actually true

`PROTOCOL.md` mandates NFC normalisation in five places, and
`issuedb/sync/_canonical.py` implements it — `utf8(NFC(field))` for every field.

**Covered here, at the unit level.** `tests/test_sync_canonical.py:137` derives
a uid from composed `café` (U+00E9) and decomposed `café` (U+0065 U+0301) and
requires them equal. It asserts `composed != decomposed` first, which is the
control proving the two inputs really differ. **Proven able to go red:** deleting
`unicodedata.normalize("NFC", …)` from `_canonical.py` takes exactly that test
red and no other.

**Not covered: agreement with Tracker.** Measured, not assumed —

    14 vector files (12 vendored + 1 issuedb-authored + tracker_uid_vectors.json)
    non-ASCII characters found: 0

On ASCII, NFC is the identity function, so every green in the *vector* suite is
equally green against a server that skips normalisation. The unit test proves
this client normalises; **nothing proves the two implementations normalise the
same way**, and that is the only property that keeps rows converging.

The control on that scan holds: it does find combining marks when they are
present.

## Why it bites

Composed `é` (U+00E9) and decomposed `é` (U+0065 U+0301) are the same text to a
human and different bytes to a hash. Two replicas typing the same tag on
different platforms derive **different uids**, create **two rows where one was
meant**, and never converge — with nothing erroring on either side. It is the
silent-divergence failure mode the canonical form exists to prevent.

Both implementations normalising *correctly but differently* is the case no
single-repo test can see, and it is not hypothetical: the `symmetric_types`
episode had two vector sets, each internally consistent and each individually
right, disagreeing with one another.

## EARS SPEC

- The uid derivation shall apply NFC normalisation to every field before
  hashing, so that composed and decomposed spellings of the same text derive the
  same uid.
- The vector set shall include at least one case whose fields differ between
  their composed and decomposed forms, so that NFC is exercised rather than
  assumed.
- When a tag name is pushed in decomposed form and the same tag is pushed in
  composed form, the server and the client shall derive the SAME uid and the
  rows shall converge.
- If a vector suite contains only ASCII, then it shall not be treated as
  evidence that normalisation works, because NFC is the identity function on
  ASCII.

## The mutation angle, checked after Tracker raised it

Tracker found that **0 of their 96 registered mutations** touch the
`unicodedata.normalize("NFC", …)` call — so the falsification harness they use
to answer "how do you know that check can fail" is itself blind here, and would
report all 96 behaving against a canonical form that skips normalisation.

**There is no mutation registry here at all** — mutations are ad-hoc, run by
hand against the code under change (see `audit/MUTATION_TESTING.md`). So this
repo cannot produce a denominator: "0 of 96" is at least a number, and "no
catalogue" is not.

But the specific claim that follows from that is one I ALSO got wrong the first
time, and the correction runs the other way: the NFC call **is** killed by a
mutation. Removing it takes `test_nfc_normalisation_makes_equivalent_spellings_equal`
red and nothing else. Run by hand today rather than by a registry — which is the
real gap, since nothing here would have told me that guard was unproven if it
had been.

## Length-prefixing, checked when Tracker raised it as their second finding

Tracker reports length-prefixing as protected-by-accident on their side and
undemonstrated as a rule. **Here it is demonstrated directly:**
`tests/test_sync_canonical.py:121` asserts that `("i", "ab")` and `("ia", "b")`
derive different uids — fields that concatenate to the same string — and
`:159` pins `canonical_bytes(["ab","c"]) == b"2:ab1:c"`. The collision the rule
exists to prevent is the thing asserted, not a side effect of a frozen
expectation moving.

Confirmed against this implementation with the control:

    ["ab","c"] vs ["a","bc"]   with prefixes    -> differ   (True)
                               naive concat     -> collide  (True, so the
                                                   check discriminates)

So Tracker's second finding does not carry over. Recorded because "it applies to
them, therefore to us" is an inference, and this one is false.

## Before starting

Coordinate with `rodmena-tracker-c6fd66` — this must be verified against their
derivation, not against ours. A vector we write and then satisfy with our own
implementation would be self-confirming, which is precisely the defect class
this ticket is about.

## Why the push/pull round trip CANNOT settle this (measured 2026-08-21)

`audit/evaluations/nfc_cross_impl.py` pushes the NFC form, then the NFD form,
and the second returns `existing`. **That green does not mean the
implementations agree.**

The sync API **stores the client-supplied uid**. Verified against stored state,
not a response field:

```
push tag under a fresh bogus uid  -> s256t128:ac69dea1...  created
correct derivation would be       -> s256t128:932326d7...
CONTROL: full walk from c:0 finds the tag by NAME  -> True
STORED uid, read back from pull   -> s256t128:ac69dea1...
```

The row carries a uid no correct derivation of those fields produces. So both
directions of the round trip key off **issuedb's** bytes, and `existing` proves
uid-idempotency — never normalisation. The thing under test supplied its own
answer.

**The first attempt at this was itself broken**, and the failures are worth
keeping: the bogus uid was not fresh (so the push returned `updated`, not
`created` — the tell), and pulling from a cursor taken before the write found
nothing. Both would have produced a confident wrong answer. The second attempt
used a fresh uid and a **known-positive proving the pull walk finds the row by
tag name** before asking it about uids.

**An earlier version of this claim was asserted from a response field alone** —
the server echoing our uid looks identical to the server storing it. Caught by
`tracker-manager-0e2462`, who noted it was the same error issuedb had corrected
*them* on in August. The claim survived; the evidence for it did not.

## What would settle it

A surface where **Tracker** derives the uid — creating a tag through the web UI
with a decomposed name, then reading back the uid Tracker minted and comparing
it to ours. Pull cannot substitute, for the reason above.

## SETTLED for the ASCII case: the implementations agree (2026-08-21)

`tracker-manager-0e2462` found the surface: `GET /v1/issues/{key}/tags` returns
`sync_uid` for tags **created through the web UI**, where no client supplies a
uid — so Tracker derived it.

```
project_uid : 01M03Z127ZEQXSY40Y8XHED3D7
issue_uid   : s256t128:b16f16f6a1221a385a52cccdf9ae9186   (AGENTBUS-188)
tag name    : "feature"

Tracker derived : s256t128:3f2f63049adcaaf1c281bc344955b7fc
issuedb derives : s256t128:3f2f63049adcaaf1c281bc344955b7fc      MATCH
CONTROL, one character different -> af1cd014..., NOT equal
```

**The first cross-implementation evidence either project has ever had.** The
ASCII case is the sharper test to run first: NFC is the identity function
there, so it isolates the canonical *encoding* — length-prefixing, field order,
entity tag, `project_uid` as field 1 — from normalisation entirely.

The issue uid needed no API change: the sync feed already carries it in the
`issue_tag` payload as `issue_uid`.

## Two write paths, two keying rules

Reconciling a contradiction between two measurements that were both correct:

| path | behaviour | verified |
|---|---|---|
| sync push | client supplies a uid; Tracker **stores it verbatim**, never re-derives | a tag pushed under a bogus uid comes back from pull carrying it |
| web / API | no uid supplied; Tracker **derives its own** | `feature` on AGENTBUS-188 matches our derivation exactly |

Both confirmed in one pass over the same feed with the same function.

**The consequence is larger than any single defect.** One logical tag can enter
Tracker by two doors and be keyed two different ways. If the derivations agree
byte for byte, one row; if they differ by one byte, **two rows for one logical
tag, both valid, both replicating, nothing erroring anywhere.** So "the sync API
trusts the client-supplied uid" is safe *only because* the implementations
agree — a load-bearing assumption that went unverified for the entire life of
the protocol until this measurement.

## RESOLVED: the accented case is a REAL DIVERGENCE

Deriving against Tracker's NFC-form probe uid gave a **mismatch**, but it is
**unusable**: the probe tags were deleted before they could be pulled, so their
`issue_uid` cannot be read and it is not confirmable which issue they were on.
A mismatch against a different issue is arithmetically expected and means
nothing.

The method is sound — it reproduces Tracker's ASCII uid exactly — so the
mismatch is either a real divergence or an unobservable input, and those are
indistinguishable from here. **One accented tag left in place long enough to
pull settles it.**

## CORRECTED: NOT a cross-implementation divergence — a Tracker deploy/API defect

> **This section's original heading claimed the implementations diverge. That
> attribution was WRONG.** `tracker-manager-0e2462` ran Tracker's own
> `canonical.py` on the exact fields below and it produces **issuedb's** uid,
> not the served one:
>
> ```
> KNOWN-POSITIVE (ASCII):  source == served == issuedb   3f2f6304...  MATCH
> accented case:           source == issuedb             d24599c3...
>                          served                        698998f0...  DIFFERENT
> ```
>
> Tracker's `_canonical` is `unicodedata.normalize("NFC", field).encode("utf-8")`
> with `len(encoded)` — **bytes, not characters**, NFC applied before encoding,
> in the same place we apply it. So my leading hypothesis (character-vs-byte
> length prefix) was **ruled out**, and so was NFC ordering.
>
> **The two implementations agree. The RUNNING BUILD does not reproduce its own
> source for non-ASCII input.** The measurement below stands exactly as recorded;
> only the attribution changes, and it changes away from issuedb. Kept in full
> because the isolation is what made the real defect findable.

## The measurement (2026-08-21)

`tracker-manager-0e2462` recreated the accented tag and left it in place. Bytes
read **from the sync feed, not retyped** — which excludes local normalisation
as an artefact:

```
tag_name bytes : b'nfc-probe-caf\xc3\xa9'    is NFC: True   is NFD: False
issue_uid      : s256t128:b16f16f6a1221a385a52cccdf9ae9186   (AGENTBUS-188)

Tracker derived : s256t128:698998f045245913e5bbe791afcb2b87
issuedb derives : s256t128:d24599c3bcd749e35d14eadf5448c048
MATCH           : False
```

### The isolation

Same issue, same `project_uid`, **only the tag name differs**:

| input | ours == Tracker's |
|---|---|
| ASCII `"feature"` | **TRUE** |
| accented name | **FALSE** |

So `project_uid`, `issue_uid`, field order, the entity tag and length-prefixing
**all agree** — proven by the ASCII match on the same row. The divergence is in
how a **non-ASCII name** is encoded.

"issuedb used the wrong field" was ruled out by searching the input space —
NFD name, no `project_uid`, project-as-key, issue-key-not-uid, issue-number:
none produces `698998f0`.

### Leading hypothesis (Tracker's to confirm, not ours)

**The length prefix may count CHARACTERS rather than BYTES.** For this name
that is 14 vs 15, and the two agree on *every* ASCII input ever tested — which
matches the signature exactly: latent for the entire life of the protocol,
diverging on the first non-ASCII input.

### Severity

**Worse than Tracker's live 500.** The 500 refuses a write — loud, nothing
stored wrong. This is silent: one logical tag entering by the sync door and the
web door gets **two uids, two rows, both valid, both replicating, nothing
erroring anywhere.** Narrow — it needs a non-ASCII name, which is why nobody
has hit it — but it is precisely the failure the canonical form exists to
prevent.

### Where the defect actually is (Tracker's, not ours)

The ASCII case proves the deployed path *does* reach a derivation equivalent to
`canonical.py` — so it is not "a different function entirely", it is something
that bites only when the name is not ASCII. Surviving candidates, Tracker's to
resolve:

1. **Something upstream of `attach_tag` mutating `name` before it is hashed** —
   a validator, a pydantic coercion, an encode/decode round trip in the API
   layer. Currently the leading candidate.
2. **Deploy drift** — the served `1ddf730` not carrying the `canonical.py` that
   is in the tree at `1ddf730`. Boring, and worth eliminating first for exactly
   that reason.

The endpoint-identity hypothesis is ruled out by our own ASCII match: if the
field were wrong, ASCII would have diverged too.

### The lesson for our own record

My isolation was right and my **attribution** was wrong. Narrowing to "the name
encoding" was correct and load-bearing — it is what let the comparison of
source against served happen at all. But "the two implementations disagree" was
an inference from *our* two data points, and a third data point (Tracker's
source, run independently) moved the blame without changing any measurement.

**A confirmed difference between two systems does not tell you which one is
wrong, or even that either implementation is.** Here neither was: both sources
agree and a deployment sits between them.
