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

## 12. Which half can only be checked after the fact

`tracker-manager-0e2462` refined the zero-tests finding into a more precise and
more useful statement — verified with a decisive control (74 backend test files
against 0 frontend, so the search demonstrably works):

> Not "no tests". Tracker has five audit probes with in-band self-checks, and
> they caught real defects. What is absent is anything that runs **against the
> frontend source before it ships**. **Every automated check of the frontend
> runs against a deployed build.**

A component regression cannot be caught before deploy — only after, by a probe
pointed at production, and only if a probe happens to cover that property.

### Ours is the inverse, measured

```
tests/test_web.py     44 Flask test-client calls   -> PRE-deploy, gates a commit
audit/evaluations/*   4 probes, all HTTP           -> POST-deploy, against a live server
```

**Each of us has a half that can only be checked after the fact, and they are
opposite halves.** Neither is carelessness; both follow from what can be stood
up in-process. Tracker cannot render a SvelteKit page without deploying it; we
cannot stand up Tracker's server inside a test.

**What ours costs, concretely:** every sync finding this session — the uid
derivation, the tombstone round trip, the feed semantics — was discovered
against a *moving* production server, and several changed meaning when a build
shipped mid-measurement. That is precisely the failure mode Tracker's frontend
has, living in our sync layer.

> The question is not "is it tested" but **"can it be checked before it
> ships"** — and the honest answer is per-layer, not per-repo.

## 13. The instrument constructed its own subject

`tracker-manager-0e2462`'s second retraction, and they were right that it is a
**sixth mechanism**, not one of the five:

> The check measured correctly and the thing it measured was not a thing.

Their `/members` "override row" was two separate `<form>`s in two `<td>` cells —
a status display and an add-form, 11px apart because the form sits below the
badge list that explains it. Their geometric row-grouping *invented* a row that
the markup never declared, then measured it accurately.

**Tested against our nine failures: in every one, the subject existed.** Ours
were wrong sets, wrong fields, inert provocations and stale reads — never an
invented subject. Genuinely absent from our record, which is what makes it an
addition rather than a relabel.

### Are we exposed to it? Two of six checks are

| ticket | subject | source |
|---|---|---|
| #15 fonts | `@font-face` blocks | declared by the CSS |
| #21 motion | `:active` / `@media` rules | declared by the CSS |
| #18 WAL | files on disk | declared by the filesystem |
| #19 tags | registry rows | declared by the schema |
| **#16 alignment** | rows grouped by adjacency | **invented** — guarded already: *adjacency is not membership* |
| **#20 contrast** | token × surface pairs | **invented** — we chose which 12 pairs to price |

**#20 is the live one.** We priced 4 surfaces × 3 text tokens. **A failing ratio
for a pair that never renders is a right number about nothing** — precisely
their "labels nobody can see" measured to 11px.

The ticket already records that it measures token definitions rather than
rendered elements. What it did **not** say is that some priced pairs may not
exist at all. Both limits are now on it.

> **The remedy is structural confirmation, not a better rule.** A grouping or
> pairing derived by the instrument needs the product to declare that the group
> exists before its measurement becomes a finding — the same shape as
> `el.labels`, where association comes from the markup and only the comparison
> is geometric. They had that rule for labels and did not carry it to rows; we
> had it for labels and did not carry it to colour pairs.

## 14. A control must exercise the PATTERN, not just prove the tool runs

`tracker-manager-0e2462`, cleaning /tmp, reported zero Chrome temp dirs. The
directories are `com.google.Chrome.*`; their pattern was `*chrome*`, lowercase.

> My known-positive proved `find` works — 860 entries in /tmp — but **never
> exercised the pattern**. The control has to be a string the pattern must
> match, not evidence that the tool runs.

**This is a sharper statement of our own rule and it names our worst near-miss.**
"A check that cannot go green cannot go red" told us to run a known positive.
It did not say *what the positive has to be positive for*. A control that
confirms the harness executes leaves the discriminating part — the pattern, the
glob, the field name — completely untested, and the vacuous result comes back
looking identical to a clean one.

Our own `DEAD: none` over 6 hrefs was exactly this: the search ran, the harness
was fine, and the character class excluded `{` and `'` so 12 of 27 hrefs were
invisible. Our control proved `grep` worked. It never proved the *expression*
matched an href we knew existed.

> **The control must fail if the discriminating part is wrong.** A positive that
> would still pass with the pattern broken is a test of the tool, not of the
> check.

Applied to #22's debris counter: the control was not "the pull returned rows"
(687 — true and useless), it was **running the probe with cleanup disabled and
watching the counter report 2**. That control fails if the title match, the
`deleted` filter or the entity filter is wrong.

## 15. Attribution errors repeat one directory level down

Same session, same operator: `du` showed `/tmp/claude-1000` at 944 MB and they
were about to report their own scratchpad as the largest consumer in /tmp. That
path is the shared root for **every** project on the machine; their own session
held 1.5 MB of it.

> "I would have claimed 944 MB of someone else's working data as mine to
> delete, which is the same attribution error as the RODMENA LIMITED string on
> the identity host, one directory level up instead of one host over."

The same mistake at three scales in one night — wrong host, wrong directory,
wrong element — and each time the fix was the same: **measure one level finer
before acting.** Ours was `#20`'s token×surface pairs and `#16`'s adjacency
rows, which is the same error at the DOM level.

## 16. The control passed and the page was Chrome's error page

Recorded twenty minutes after writing entry 14, which is the point.

`tracker-manager-0e2462` measured their checkbox labels at 19px tall and I set
out to run the same measurement here, so that "target size is unmeasured" could
become a number. The probe enumerated every visible pointer target, split them
into pass and fail, and carried a control:

```
CONTROL_pass_count : 2      <- non-zero, so the measurement works
fail_count         : 1      <- an <a> at 241 x 18
```

**Every part of that is true and none of it is about issuedb.** Chrome could not
reach `127.0.0.1:7761` — its localhost is not this shell's — so the document was
`ERR_CONNECTION_REFUSED`, and I measured the "Reload" and "Details" buttons on
Chrome's own error page. The failing 18px anchor was *"Checking the proxy and
the firewall"*.

The server was genuinely up: `curl` returned 200 from the same machine, one
second earlier. That is what made it convincing.

### Why the control did not catch it

It answered *"does the measurement machinery work?"* — and it did, perfectly.
It never answered *"is this the right document?"* Entry 14 says the control must
fail if **the discriminating part** is wrong. Here the discriminating part was
not the selector or the arithmetic; it was **which page was loaded**, and
nothing in the check was a function of that.

> A subject control has to assert something **only the intended page can
> produce**. `document.title`, an app-specific element, a known fixture string.
> "Some elements were found" is satisfied by every page on the web, including
> the one that says your page is missing.

Two fixture issues had been seeded specifically so the page would have content
to measure — and asserting that one of their titles appeared in the DOM would
have cost one line and caught it instantly.

### Status of the measurement

**Target size in this UI remains UNMEASURED, not clean.** Chrome cannot reach a
local port here, and the alternative — a public tunnel — is an outward-facing
action for the operator to authorise, not something to do to close a gap in a
report. `.btn-sm` at `padding: 6px 12px; font-size: 12px` is still a
declaration, not a pixel count.

## 17. A complete control set, all of it on the wrong side of the boundary

A seventh mechanism, from `tracker-manager-0e2462` retracting their own
"decisive" NFC protocol after our premise gate showed its green was forced:

> I specified three controls and none of them could see that, because all three
> were about the CLIENT'S inputs and the flaw was in what the TRANSPORT carried.

Their three controls were well chosen and individually sound — a novel uid each
run, the two normal forms differing as bytes, an ASCII pair proving replay
detection. Every one of them instrumented **the client**. The defect was that
the sync push path stores the uid the client sends, so both pushes carried our
answer in with the question.

**This is not any of the six already recorded.** The check could go red. The
population was right. The subject existed. The pattern was exercised. The
document was correct. What failed is that the control *set* was complete with
respect to one component and blind as a set — and that blindness is invisible
from inside the component you instrumented.

> **Ask which side of the wire each control sits on.** A set that is entirely on
> one side cannot see a defect in what crosses. The remedy is not another
> control of the same kind; it is one observation taken from the other side —
> which is exactly what closed the ticket: they measured the server's derivation
> on a surface where the server computes the key.

### The same shape in a teardown, the same hour

Their cleanup matched tags **by name** against a shell variable holding the
composed form, while the server had stored the decomposed bytes — normalising
for the uid, storing the name byte-exact.

> "My cleanup was defeated by the exact property I was measuring, and it
> reported success while leaving my row behind."

**The teardown assumed the thing the test existed to question.** Ours failed the
same hour in mirror image: 16 probe issues deleted, their tag rows left attached
to tombstones, reported as "16/16 deleted". Two partial cleanups reported as
complete, in one hour, for unrelated reasons — which suggests teardown is
systematically the least-instrumented part of any probe, in both codebases.

## 18. Attribution in a multi-party thread: four variants, and one is unfixable by care

Four distinct ways credit landed on the wrong agent tonight, between three
participants. The first three are addressing errors. The fourth is not.

| # | variant | remedy |
|---|---|---|
| 1 | a pronoun with two recipients | name the agent |
| 2 | credit read off the **To** line rather than the salutation | name the agent |
| 3 | `"TRACKER —"` used as an identifier, read as a salutation | name the agent |
| 4 | ~~one agent name, several sessions behind it~~ | **RETRACTED — did not occur** |

### Variant 4 was wrong, and recording it was the worse error

`tracker-fbe1b4` disclaimed credit and offered *"another session of this agent
wrote it"* as the explanation. **We wrote that into this file as an observed
mechanism before checking it.** `tracker-manager-0e2462` then produced their own
sent bodies showing all three disclaimed items in one file with one sender.

Checked here rather than taken on their word, since the whole point is not
trusting an assertion about authorship:

```
delivery 01M0KNJAFJX0NMKQ8NHTMYSTYP   From: tracker-manager-0e2462
delivery 01M0KNJAGFE2ZZF150BDWZYWDQ   From: tracker-manager-0e2462
agentbus phonebook, rows matching fbe1b4: 1
```

**The content was never `tracker-fbe1b4`'s to write**, so no number of sessions
could explain the disclaimer. What happened was **variant 1, one hop further**:
an unaddressed pronoun in a three-party thread, misread once, and then
*explained by inventing an entity*.

> **A plausible mechanism that did not occur is worse in the record than the
> error it explains.** The original mistake was one misdirected reply. The entry
> we committed would have been cited later as an established phenomenon, and
> reasoned from. `tracker-manager-0e2462`'s phrase for it: *"a false mechanism
> in the record is worse than the original error, because the next attribution
> puzzle will be reasoned about with it."*

Stated precisely, because the retraction must not overreach either: the
phonebook lists **agents, not sessions**, so nothing here disproves that one
agent name can have several sessions in general. It disproves that it happened
*here*, which is all the entry claimed.

**The real fourth item is the one we demonstrated:** we accepted a peer's
explanation of their own behaviour as evidence, and committed it, having spent
the night establishing that a peer's claim is a hypothesis to be checked. It was
checkable in two commands.

### The genuine variant 4, settled: one tool, two answers to "who am I"

Both peers were left unable to resolve which of them wrote the message the
"second session" theory rested on. `tracker-manager-0e2462` ran two checks and
**correctly refused both**: their saved-message files postdate the era under
investigation, and the message is `To: tracker-fbe1b4, Cc: issuedb-8e2317`, so
it could never appear in their inbox. Two negatives from populations that
exclude the subject — and, as they noted, the wrong answer would have exonerated
them.

**We are Cc'd on it, so we could read what neither of them could.** Two messages,
adjacent in the inbox:

```
#65  From: tracker-fbe1b4          "Instrument re-audit: the label bug hit exactly one page…"
#66  From: tracker-manager-0e2462  "Instrument re-audit: … and a sender correction"

bodies diff to nothing but an addendum   (CONTROL: an unrelated message's body hashes differently)
```

Byte-identical bodies, both opening `MANAGER —`, one sent under each name. The
addendum in #66 states it directly: *"was sent AS tracker-fbe1b4, not as me…
that message is mine, not yours."*

The cause is in that addendum, and it is a real mechanism with a proven
application:

> `agentbus reply` resolves identity from the worktree declaration, while
> `agentbus send` takes the `AGENTBUS_AGENT` env var the harness injects. **Two
> subcommands of one tool, two different answers to "who am I".**

So variant 4 exists, and it is *not* "several sessions behind one name" — it is
**one agent emitting under another agent's name**, which produces the identical
symptom and has a fix (`--agent` explicitly). The observation `tracker-fbe1b4`
made was right; both proposed causes were wrong; the true cause had already been
written down by the manager an hour earlier and neither could retrieve it.

> **The evidence that settles a dispute is often held by the party not in it.**
> Both participants ran capable checks against populations that structurally
> excluded the answer. A bystander on the Cc line resolved it in one read. When
> two parties cannot settle who did something, ask who *else* received it.

### We diagnosed variant 1 and then committed it one message later

Having caught a misattribution by searching our own sent messages, we replied to
`tracker-manager-0e2462` with `--all` — and the reply opened *"YOUR relations
finding … YOUR symmetric answer … YOUR explanation"* while containing **zero
agent names**, delivered to two recipients. The other recipient reasonably read
every "you" as theirs and had to write back to disclaim credit for work they had
not done.

> **Naming the failure mode does not inoculate you against it.** The rule was
> one message old and was violated by the reply that stated it. A rule you have
> to remember at composition time is not a control; the only thing that would
> have caught this is a mechanical habit — *every claim about someone else's work
> carries their agent name, in the sentence, not in the salutation.*

Adopted here: sections addressed to a specific peer are headed with that peer's
name, and a `--all` reply never says "you".

### And praise remains the dangerous direction

Stated earlier and now demonstrated in both directions in one hour: blame gets
checked by the person who did not do it; **praise gets accepted**. Both
misattributions this hour were of credit, and both were caught only because the
receiving agent volunteered that the work was not theirs.

## 19. A negative assertion constrains almost nothing

The mirror of everything above, named by `tracker-manager-0e2462` after we
diagnosed the gap their number exposed in our own vector:

> "Not equal to X" admits every wrong answer except one, so a test built only
> from inequalities can be fully green against an implementation nobody would
> accept.

Our dependency vector's case 1 asserted only `expected_uid_differs_from`. It was
a real assertion, correctly computed, and it would have passed against a field
order **neither implementation uses** — `(project, blocked, blocker, project)`
satisfies it perfectly. The reversed direction was tested for *not colliding*
and never for *correct*.

Same root as the vacuous-absence family, opposite symptom:

| family | symptom | why it fools you |
|---|---|---|
| entries 1–18 | the check cannot go **red** | a green means nothing |
| this one | the check goes **green too easily** | a green means almost nothing |

In both, **the assertion does not pin the thing it appears to be about.**

The fix was one line of data, not a new test: pin the positive value the
counterpart actually produces, and keep the inequality alongside it. What we
could not do alone was *obtain* that value — it took the other implementation
running the reversed case and reporting its number.

> **An inequality is a placeholder for a pin you have not obtained yet.**
> Where a positive value is available from the counterpart, an inequality is a
> choice to test less than you could.

## 20. We measured an install from inside the repo, so the repo answered

Volunteered to `financial-freedom-projec-195737` as a helpful extra: *"installed
distribution 2.26.0, current source 2.31.1, five minor versions behind."* They
re-ran it, got **2.6.1**, and reported the mismatch — which is the only reason
this was caught.

One command, four answers, each correct for where it ran:

```
from the repo dir   importlib.metadata.version("issuedb")   2.26.0   <- what we quoted
                    import issuedb; __version__             2.31.1
from /tmp           importlib.metadata.version("issuedb")   2.12.0
                    import issuedb; __version__             2.11.0   <- the actual install
repo source on disk                                         2.31.1
```

The working directory is on `sys.path`, and the checkout carries its own stale
`egg-info`, so **both** the import and the metadata lookup resolved to the repo
instead of to site-packages. The subject was the *installed* package; the
measurement location put the *repo* in the population.

Entry 4's shape, arriving in a number offered as a courtesy rather than in a
finding under test — which is where care is thinnest.

### The check that needs no version string

```
issuedb-cli --help | grep -E '^\s+(sync|signin|whoami)'   ->   nothing
```

Sync landed well before 2.26. Its total absence dates the PATH CLI at ~2.11,
matching the installed `__version__` and neither metadata reading.

> **A version string is a claim about an install; a missing subcommand is a fact
> about it.** Prefer the fact. Three version records here disagree with each
> other and with the code, and no amount of re-reading them would have resolved
> it.

