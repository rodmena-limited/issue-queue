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

## The mechanism under all of these

`tracker-fbe1b4`, 2026-08-22, on why six instrument failures happened to people
actively hunting instrument failures:

> **The instrument and the subject shared an assumption.** The instrument cannot
> see an assumption it is standing on, and no amount of care fixes that; only a
> second, differently-founded observation does. Which is why the known-positive
> works and re-reading the code does not.

**Tested against our own failures rather than accepted — five for five:**

| failure | the shared assumption |
|---|---|
| NFC probe reported "the implementations agree" | probe supplied the uid, server stored what it was given — **both sides used our derivation** |
| amplified `/projects` as the worst defect | our check and the report both assumed the tenth item was measured like the nine |
| href check: "DEAD: none" over 6 hrefs | matcher and mental model both assumed **hrefs are literal** |
| boundary check spared `909999` | listing and decision both assumed **a row in the feed is live** |
| #20 contrast over three `--bg-*` tokens | enumeration and palette model both assumed **the naming convention is the population** |

This is why "be more careful" is not a mitigation and a second observation is.
It also explains why the four detection heuristics all work by *contradiction*
— every one of them surfaces a fact the instrument's own assumption cannot
absorb.

## An acceptance criterion that rejects a correct fix

From the same exchange, and worse than a missing criterion:

> A `for=` check would **reject a perfectly good wrapping-label fix** — so
> #16's own verification would have failed a correct implementation of #16.

It looks like diligence while forcing the implementer toward a worse answer.
Same family as a vacuous red, one level up: it does not merely waste work, it
**actively selects against the right solution**. Worth catching before writing
the fix rather than after.

## 6. One wrong selector, two different failures

`tracker-fbe1b4`'s re-audit, 2026-08-22. Their broken `for=` label selector did
**two** things, not one:

- a **false positive** on `/keys` — six phantom failures on a correct page;
- a **vacuous pass** in their *alignment* check, which paired labels the same
  broken way, found 0 labels, **skipped the label assertion entirely**, and
  still printed `0 failing`.

> One wrong selector produced a false positive on one dimension and a vacuous
> pass on another.

The second is the emptied-population failure arriving by a new route: not "the
rows were destroyed" but "the labels were invisible, so there was nothing to
compare and nothing to report".

**Audited our own four UI checks for that shape.** Two have it structurally —
#16 would report `0/0` as clean if it found no controls, and #20's token×surface
pairs would vanish silently if a token were undefined. Verified neither
occurred:

```
#16  visible controls found : 7    <- non-empty, so the ratio is real
#20  colour tokens defined  : 18   <- and every token priced is defined
     --text-muted / --bg-primary / --bg-secondary / --bg-tertiary / --bg-hover : all True
```

**The shape existed; the failure did not.** Worth recording as checked rather
than as absent — the distinction between "we do not have that bug" and "we
looked".

### The prediction that held

Their three surviving instruments all read the platform's computed answer
(`getBoundingClientRect`, `getComputedStyle`, `scrollWidth`). The one that
re-derived — a selector standing in for `el.labels` — is the one that was wrong.

> Not proof the other three are right, but it is the distinction that predicted
> which would fail, and it predicted correctly.

## The taxonomy, tested rather than accepted

`tracker-manager-0e2462` proposed that roughly fifteen instrument failures
across three agents reduce to five mechanisms. Checked against our own nine:

| our failure | mechanism |
|---|---|
| NFC probe reported "the implementations agree" | check cannot go red |
| "server trusts the client uid", from a response field | wrong reference — measured the response, not stored state |
| stale-uid probe returned `updated` | stimulus cannot provoke — the uid was not fresh |
| href check: "DEAD: none" over 6 | population excludes the subject |
| boundary check spared `909999` | wrong reference — read a tombstone as a live row |
| #20 over three `--bg-*` tokens | population excludes the subject |
| two bad round-trip splits | stimulus cannot provoke |

**Seven of nine fit.** The taxonomy holds for instruments.

### The two that do not fit are a different category

- **`--json` reported broken** — a zsh word-split meant the CLI never ran the
  command; a *harness crash* read as a finding.
- **Misattributed a detector to the wrong peer** — an unaddressed pronoun in a
  message with two recipients.

Neither is an instrument failure. One is a **harness** failure, one is a
**communication** failure. Both produced a false claim about someone else's
work, which is what made them feel like the same family — but the remedy is
different: the instrument mechanisms are fixed by a second observation, these
two by reading the output instead of the exit code, and by naming the addressee.

> A taxonomy that is complete for its domain is not thereby complete for
> everything that looks like its domain.

## 7. Under-claiming is also misinformation

`tracker-fbe1b4`, 2026-08-22, after the manager found a shipped fix by
re-running a check rather than being told:

> A fix I **under-claimed** is as misleading as one I over-claim; it just fails
> the other way.

They had shipped the `/members` overflow fix inside a commit whose subject named
only the contrast changes, and described it on the bus as *"hardening, not a
verified fix"*. So the manager had every reason to treat it as still open, and
spent a turn re-verifying something already done.

**Every honesty rule collected tonight points at over-claiming.** This is the
opposite error, and it has a real cost: wasted work, and a record that says a
defect is open when it is closed.

**Audited our own tickets for it — none found.** #16 is honestly UNMEASURED (no
browser), #20 names its undercount direction, #21 claims exactly what was
checked and was checked twice, #15 is measured, #12 was corrected twice into
accuracy. But the *category* is new to this record: we had been auditing for
overclaim only.

## 8. A subject that cannot exhibit the defect

Same message. Tracker could not reproduce the `/members` overflow across four
synthetic combinations, and the manager's measurement explained why:

```
the real labels   left 580.586px   deep inside a 640px table
their constructed left   2.000px
```

**They built a subject that could not exhibit the defect, then concluded the
defect was not exhibited.** The shared assumption this time was that the
element's *position* did not matter to whether it escapes its containing block.

This is the sibling of *"a stimulus that could not provoke"* — there, the input
could not produce the condition; here, the **subject** could not host it. Both
produce a true measurement of the wrong thing, and both look like a clean
negative result.

> An inability to reproduce is not evidence against a report until you have
> shown your reproduction *can* exhibit the defect.
