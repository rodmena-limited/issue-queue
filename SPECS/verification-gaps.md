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

## 4. A stale reference to a versioned artefact

`tracker-manager-0e2462`, 2026-08-22. Mid-sweep they measured a stylesheet and
got **0 animations, 0 infinite animations, no reduced-motion guard** — about a
product they had confirmed thirty minutes earlier had a thorough global guard.
They nearly reported that Tracker had lost its motion handling.

```
0.DiHGqobo.css   12,969 bytes at 01:05     9 bytes at 01:20
```

Their asset list was **pinned to a build that no longer existed**. A deploy
changed the content-hashed filenames, and every URL in the list became a stub.
**The fetch "succeeded" fourteen times and returned almost nothing.**

> Content-hashed asset URLs are designed to change, so any list of them has a
> shelf life measured in deploys.

**The tell was arithmetic:** fourteen assets summing to 34,027 bytes in the
table, and 21,067 in the concatenation. *A total that does not match its own
parts.*

### How this differs from the other three

| heuristic | catches |
|---|---|
| every subject fails | a wrong **population** |
| the number contradicts what I know | a wrong **subject** |
| two of my own numbers disagree | a wrong **parse** |
| **a total disagreeing with its parts** | **a stale reference to a versioned artefact** |

### Our exposure is the opposite one

Checked: **zero** pinned content-hashed asset references in
`audit/evaluations/` (control: the pattern matches such a string when present).
We measure **source files in our own repo**, so nothing can go stale mid-run.

That is not safety — it is the other failure. Source cannot go stale, and
**source is also not what a user gets**. Every UI finding recorded here
(#15, #16, #20, #21) is a statement about the stylesheet, not about the served
page.

## 5. Re-deriving what the platform already answers

`tracker-manager-0e2462` retracted "/keys: 6 of 6 controls unlabelled" after
issuedb's `el.labels` correction. Their check was
`document.querySelector("label[for=" + id + "]")`; the page uses **wrapping
labels**, which need no `for=` and no `id`, so a correct page read as entirely
unlabelled. Measured both ways on the same build:

```
/keys       unlabelled by for= grep : 6      <- what was reported
            unlabelled by el.labels : 0      <- the truth
/knowledge  unlabelled by el.labels : 6      <- the finding STANDS here
```

The same reported defect was **false on one page and true on the other**, and
the instrument could not tell them apart.

> **When the platform exposes the answer, use the platform.** `el.labels`,
> `getComputedStyle`, `getBoundingClientRect`, `matchMedia` are the browser
> telling you what is *actually* true. The platform does not have a stale copy,
> a wrong pattern, or a missing case.

### Audit of our own UI findings against that rule

**All four re-derive something a browser would answer authoritatively** — we
have no platform to ask, so we reimplemented it:

| ticket | ours | the platform's answer |
|---|---|---|
| #15 fonts | parsed `@font-face` from CSS text | `getComputedStyle(body).fontFamily` |
| #16 labels | counted `<label>` in source | `el.labels.length` |
| #20 contrast | ratios from token literals | `getComputedStyle` colour + background |
| #21 motion | grepped `:active` / `@media` | CSSOM + `matchMedia` |

**The test that matters is whether a valid alternative form exists** that the
check cannot see — that is what made `/keys` a phantom.

- **#16 — safe.** Already re-checked for wrapping labels: **0 of either form**
  against 15 visible controls. No alternative form exists.
- **#21 — safe, checked not assumed.** No `:active`, and no JS alternative
  either: `matchMedia` 0, `prefers-reduced-motion` 0, active/press class 0,
  `mousedown` 0 (control: `addEventListener` matches 1, so the search works).
- **#15, #20 — risk is UNDERCOUNT, not phantom.** A colour or family set inline
  or by JS would be missed, but a failing token pair still fails wherever it is
  used. Incomplete rather than false.
