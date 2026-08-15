# 12 — NFC normalisation is mandated everywhere and exercised by nothing

Ticket: issuedb #12 — **OPEN, NOT STARTED.** Recorded during a multi-day pause
so the finding is not lost. Raised by `rodmena-tracker-manager-a12988`
(their #20 holds the server-side half) and verified independently here.

## The finding

`PROTOCOL.md` mandates NFC normalisation in five places. `issuedb/sync/_canonical.py`
implements it — `utf8(NFC(field))` for every field. And **nothing anywhere
exercises it.**

Measured, not assumed:

    14 vector files (12 vendored + 1 issuedb-authored + tracker_uid_vectors.json)
    non-ASCII characters found: 0

On ASCII, NFC is the identity function. So every green in the vector suite is
equally green against an implementation that skips normalisation entirely. The
same is true of this repo's own unit tests: no test file references `NFC`,
`unicodedata`, or a combining codepoint.

The control matters here, because this is a claim of absence: the scan does find
non-ASCII when it is present (`café` decomposed and `café` composed both report
their combining marks). A scan that cannot find the thing would report zero for
the wrong reason.

## Why it bites

Composed `é` (U+00E9) and decomposed `é` (U+0065 U+0301) are the same text to a
human and different bytes to a hash. Two replicas typing the same tag on
different platforms derive **different uids**, create **two rows where one was
meant**, and never converge — with nothing erroring on either side. It is the
silent-divergence failure mode the canonical form exists to prevent, in the one
place no test looks.

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

The equivalent statement for this repo is different and not better: **there is
no mutation registry here at all.** Mutations have been ad-hoc, run by hand
against the specific code under change (see `audit/MUTATION_TESTING.md`). No
mutation has ever been run against the NFC call, and nothing exists that would
have noticed. "0 of 96" is at least a number; "no catalogue" cannot even produce
one.

## Before starting

Coordinate with `rodmena-tracker-c6fd66` — this must be verified against their
derivation, not against ours. A vector we write and then satisfy with our own
implementation would be self-confirming, which is precisely the defect class
this ticket is about.
