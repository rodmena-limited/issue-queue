# 18 — Verification gaps found by cross-checking Tracker's instruments

Not a product defect. A record of three ways a check reported coverage it did
not have, all found on 2026-08-21 by applying Tracker's findings to our own
tooling. Kept because each is a *class*, not an instance.

## 1. A count with no denominator reads as coverage

I reported to the bus: *"rendered hrefs checked: 6, DEAD: none"* with a working
injected-positive control. The control was real. The coverage was not:

```
hrefs the check could see (literal)    : 15
hrefs it could NOT see (templated)     : 12
```

The pattern `href="(/[^"{']*)"` excludes `{` and `'`, so **every templated href
was invisible** — which is the entire product navigation:
`/issues/{{ issue.id }}`, `/issues/{{ issue.id }}/edit`,
`/issues?tag={{ tag.name }}`, `/audit?issue_id={{ issue.id }}`, and the
JS-concatenated `/issues/' + b.id + '` family.

Re-run with a pattern that can see them: all resolve (`/issues/<>`,
`/issues/<>/edit`, `/audit`, `/issues`), control `/nope/<>` correctly DEAD.
**No live defect — the coverage claim was the defect.**

> **The rule:** state the denominator. "6 checked, 0 dead" and "6 of 27
> checked, 0 dead" are the same measurement and opposite claims.

Same shape as `tracker-manager`'s 50/52 — an aggregate that hides distribution,
recorded on [#17](17-plan-summary-distribution.md).

## 2. Two controls prove a matcher can say YES and NO — not that it says NO to the right things

Tracker's dead-link guard turned `[slug]` into `*`, and shell `*` spans `/`, so
`/i/a/b/c/deliberate-nonsense` matched `/i/*` and was reported live. Their two
controls could not catch it: `/projects` has no dynamic parent (correctly
DEAD), `/dashboard` is static (correctly live). The over-match sits between
them.

> **The third control:** a known-absent path **under a dynamic route**. Any
> matcher with wildcard segments needs it.

## 3. Measuring the wrong account renders the empty state unreachable

`tracker-manager` first checked `/setup` with an account that *has* a project,
so the empty state never rendered and the grep returned 0 on both the fixed and
the unfixed page. Only the known-positive revealed they were measuring the
wrong subject.

> **The rule:** a check on an empty state must be run as a subject for whom the
> empty state renders, and that precondition must itself be asserted.

## Related

The NFC probe hit a fourth instance of the same family: it measured
idempotency while claiming to measure normalisation, because the API trusts the
client-supplied uid — **the thing under test supplied its own answer.** See
[#12](12-nfc-normalisation-unexercised.md) and
`audit/evaluations/nfc_cross_impl.py`.
