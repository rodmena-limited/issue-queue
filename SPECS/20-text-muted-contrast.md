# 20 — `--text-muted` fails WCAG AA on every background

Ticket: issuedb #20 — **OPEN, NOT STARTED.**

## Measured, instrument controlled first

```
CONTROL  #3a3a3a on #111111 (known bad)  -> 1.66   flagged
CONTROL  #ffffff on #000000 (known good) -> 21.00  not flagged

--text-muted #6e7681 on bg-primary   #0d1117 : 4.12  FAIL
--text-muted #6e7681 on bg-secondary #161b22 : 3.77  FAIL
--text-muted #6e7681 on bg-tertiary  #21262d : 3.31  FAIL
```

WCAG AA requires **4.50:1** at 14px. For comparison, the neighbouring tokens
pass everywhere: `--text-secondary #8b949e` at 6.15 / 5.62 / 4.95, and
`--text-primary #e6edf3` at 16.02 / 14.64 / 12.88.

**Blast radius: 31 uses of `var(--text-muted)` across 7 files.** One token, one
line to change.

## Candidate values

| value | primary | secondary | tertiary | |
|---|---|---|---|---|
| `#6e7681` current | 4.12 | 3.77 | 3.31 | fails all three |
| `#8b949e` | 6.15 | 5.62 | 4.95 | clears AA — but collapses into `--text-secondary` |
| `#9198a1` | 6.50 | 5.94 | 5.23 | clears AA and stays distinct |

## EARS SPEC

- All text in the web UI shall meet WCAG AA contrast: at least 4.50:1 against
  its background at 14px.
- The muted text token shall clear 4.50:1 against **every** background it is
  used on, not only the lightest.
- Contrast shall be verified by measuring the rendered colours against the
  surfaces they appear on, with an instrument proven to flag a known-bad pair
  and pass a known-good one.

## How it was found

`tracker-manager-0e2462`'s batch-3 contrast sweep found their own
`--text-muted #7d8590` at 4.08:1 — missing AA by 0.42 on **one** surface.
Checked ours rather than assuming it differed. **Ours is darker and fails on
all three, by up to 1.19.**

Their method note is the part worth carrying: **validating the ratio *function*
proves the formula works and says nothing about whether the traversal can find
an element.** They injected a real failing element into a real page and watched
the sweep report it, then removed it and watched the report clear. A sweep
returning zero failures means nothing until it has returned one.

## The token sweep cannot see the worst kind of contrast defect

`tracker-manager-0e2462`'s batch 4 found their nav "Sign in with RODMENA ID"
button at **1.21:1** — muted grey on the green fill — on every anonymous page,
while the *same component* in the page body measured 7.45:1. Cause: the nav
applies a link colour to `a` inside the header and the button class does not
override it.

**Both colours are individually legitimate tokens.** A sweep that measures token
definitions against surfaces — which is exactly what produced this ticket —
**cannot see it**, because the defect is a *collision between two valid rules*,
not a bad value.

### The same latent collision exists here

```
.nav a       -> color: var(--text-secondary) #8b949e   specificity 0,0,1,1
.btn-primary -> color: #000                            specificity 0,0,1,0
=> .nav a WINS
```

```
correct    #000000 on #3fb950 (--accent-green) : 8.27  passes
clobbered  #8b949e on #3fb950                  : 1.21  FAILS
```

**The identical ratio.** It does not fire today because no `.btn` appears inside
`.nav` in our markup — checked, zero occurrences. It fires the moment one does,
and nothing warns.

**Fix while #20 is open**, since it is the same line of work: give `.btn`,
`.btn-primary` and friends a colour that wins inside `.nav`, or scope `.nav a`
so it cannot reach a button.

### And the denominator lesson, third instance

Their batch-3 sweep reported four pages failing and seven clean — **and ran only
on signed-in renders**. The worst contrast defect in their product was outside
the measured population. Their instrument was proven in both directions and
aimed at the wrong set.

Ours has the same exposure stated plainly: **#20 measured token definitions, not
rendered elements**, so any override, any inline style, and any surface not in
the three background tokens is outside what was checked.

## Correction to this ticket's own measurement (2026-08-22)

`tracker-manager-0e2462` corrected their equivalent finding — theirs is a
**pairing** defect, not a token defect: their `#7d8590` passes on two of three
surfaces (4.64 and 5.07) and fails only on the lightest, `.card-header`. They
asked us to correct this ticket on that basis.

**Checked: their correction does not transfer.** Our token is a *different,
darker value*:

```
Tracker --text-muted #7d8590 : passes on #161b22 (4.64) and #0d1117 (5.07)
issuedb --text-muted #6e7681 : fails on both — 3.77 and 4.12
```

So "fails on every background" stands for our value. The claim is about our
palette, not theirs.

**But their METHOD point lands, and it makes this ticket worse.** They measured
against backgrounds they remembered rather than the element's real ancestor
chain. We did the same — enumerating three `--bg-*` tokens rather than every
background that exists in the CSS:

```
CONTROL #3a3a3a on #111111 -> 1.66 (flags)

--text-muted #6e7681 on bg-primary       #0d1117  4.12  FAILS
                     on bg-secondary     #161b22  3.77  FAILS
                     on bg-tertiary      #21262d  3.31  FAILS
                     on bg-hover/border  #30363d  2.66  FAILS   <- MISSED
```

`--bg-hover` and `--border-color` are both `#30363d` and both used as
backgrounds. **The surface this ticket omitted is the worst case**: 2.66:1,
short of AA by 1.84 rather than the 1.19 originally recorded.

> **Read the element, not the palette you remember** — and enumerate every
> background value in the stylesheet, not the ones named `--bg-*`.

Still to be confirmed against a rendered page: which text/surface pairs actually
co-occur. A value failing against a surface it never sits on is not a defect,
which is precisely the distinction their correction turned on.
