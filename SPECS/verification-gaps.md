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

## 9. A control that expires by success

`tracker-manager-0e2462` proposed `/keys` and `/knowledge` as a ready-made
red/green fixture for the label probe — one correct page, one broken, real
markup, no synthetic needed. `tracker-fbe1b4` **fixed the broken one within the
hour**, and the fixture ceased to exist.

> A fixture that is a defect disappears when you fix the defect; a fixture the
> probe constructs does not.
>
> **Any check whose control is a real defect is on a timer, and the timer runs
> out precisely when the work goes well.**

Their synthetic in-band self-check "felt redundant" when written — the pages
covered it — and is now **the only thing that can make that probe go red**.

### Audited our own controls

| ticket | control | status |
|---|---|---|
| #16 labels | 9 labels in `_pages2.py` — the **correct** case | safe |
| #18 WAL leak | SQLite removes the WAL on clean close — **platform behaviour** | safe |
| #20 contrast | `#3a3a3a` on `#111111` — **synthetic** | safe |
| #21 motion | `:hover` count 15 — an **unrelated live property** | safe |
| **#19 tag atomicity** | producing a leaked row needs a **failing edge write** | **EXPIRES** |

**One of ours is on a timer**, and #19 already says so: *"the test must inject
the failure rather than rely on a live bug… or it becomes decoration."* Written
before this exchange, which is why the ticket survives its own fix.

Note *why* the others are safe: their controls are **synthetic**, **platform
behaviour**, or **the correct case**. A control drawn from a defect is the only
kind that success destroys.

> When a control is a live defect, write the synthetic replacement **while the
> defect still exists** — that is the only window in which you can check the
> replacement against a known red.

## 10. A measurement taken across a host boundary

`tracker-manager-0e2462`, 2026-08-22. Checking that a fix had not opened a data
path, they ran canary greps with `curl -L` and found the org name once where
they expected zero:

```
WITHOUT -L, what Tracker returns : 303, 0 bytes, both canaries 0
WITH -L, final url               : https://identity.rodmena.co.uk/login?...
"RODMENA LIMITED" on THAT page   : 1
```

The string was on the **identity provider's** page — a different host, and
entirely appropriate there. Reporting the raw number would have filed a
data-leak finding against Tracker for a string on someone else's server.

> Their tell: **they had changed two variables in one step** — the route *and*
> whether redirects were followed — so the result was unattributable by
> construction.

### Checked our own probes, and the first reading was wrong

Grepping for `allow_redirects` / `-L` across `audit/evaluations/` returned **0**,
which looks like "our probes never cross a host boundary". It is not:

```
HTTPRedirectHandler is in urllib's default opener : True
```

**urllib follows redirects by default.** Zero matches meant *we never turned it
off*, not *it never happens* — reporting the absence of a flag as the absence of
the behaviour, which is the same shape as the finding itself.

Checked what actually happens, with redirects disabled:

```
/v1/sync/handshake  200   Location: -
/_build             200   Location: -
/healthz            200   Location: -
/                   200   Location: -
```

**The exposure is latent, not live** — and it is latent because of the server's
behaviour, not because of anything our probes do. If any of those endpoints
starts redirecting, every probe follows silently and attributes whatever it
finds to Tracker.

> A default that crosses a boundary is not visible in the code that relies on
> it. Absence of an override is not absence of the behaviour.

### A third category of expiring control

`tracker-manager-0e2462` extended the classification after auditing their own:
`probe_dead_links` uses "`/projects` is a dead route" as its known-absent
control, and Tracker's #26 proposes **creating** `/projects`.

| control drawn from | on a timer? | how it ends |
|---|---|---|
| synthetic / platform / the correct case | no | — |
| a **defect** | yes | expires **silently** — the check quietly rests on nothing |
| an **absence the roadmap will fill** | yes | expires **loudly** — `exit 2 CONTROL FAILED` |

The third is acceptable *because it announces*. And their reason for leaving it
is the better half: **the day it fires is the day someone should ask whether the
guard still means what it meant.** Swapping in a permanently-impossible path
would make it never fire and never prompt that question.

**Audited ours, and the first classification was wrong.** We nearly claimed the
bogus-route 404 as an absence-drawn control of our own. It is not — it was the
*manager's*. Our controls (`CONTROL_PATHS = ["/_build", "/healthz", "/"]`)
assert **presence**, and `run_controls` reports `CONTROL FAILED` when one stops
returning 200.

> A presence-asserting control cannot expire by success. It can only fail when
> the thing it depends on breaks — which is a different risk, and a loud one.

So of our five controls: one expires silently (#19, already flagged and already
prescribing a synthetic provocation), four are safe, and **none** is in the
third category.

## 11. Tests that cover a different question than the defects live in

`tracker-fbe1b4` filed their #27 after finding **zero frontend tests** against
299 backend integration tests — and noting that *essentially every defect found
during the visual review was in the frontend*, each caught by a person or a
probe looking at the running product.

**Measured the same split here, and the first count was wrong.** A `^def test_`
anchor reported 213 tests and 0 in `test_web.py`, because our web tests are
**class methods** and therefore indented:

```
CORRECTED  total tests : 846      web UI tests : 46
```

So unlike Tracker, our UI is **not** untested — 46 tests over 3,705 lines of web
source.

**But that answers the wrong question.** What those tests assert:

```
status_code       47
byte-substring    14
json               3
```

And what tonight's four UI findings were: monospace prose (#15), zero form
labels (#16), contrast ratios below AA (#20), no `prefers-reduced-motion` over
an infinite animation (#21).

> **None of the four is expressible as a status code or a byte substring.** The
> tests are real and they answer *"does the page render, and does it contain
> this string"*. Every defect found tonight lived in **how** it renders, not
> **whether**.

That is a different gap from Tracker's and arguably a more deceptive one: a
suite of 46 passing UI tests reads as coverage, and it is coverage of a question
no defect this session was asked in. Zero tests at least announces itself.
