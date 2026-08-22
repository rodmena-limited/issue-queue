# 16 — The issue detail page has no form labels

Ticket: issuedb #16 — **OPEN, NOT STARTED.**

## Why

`_detail.py` and `_detail_part2.py` contain **zero `<label>` elements**. Their
controls are described only by placeholders, which vanish on input and are not
reliably announced by screen readers.

The house pattern already exists and is good — the create and memory forms use
labels that carry the format:

```
Title *            Due Date (YYYY-MM-DD)     Tags (comma separated)
Description        Related Issues (IDs)      Key *  /  Value *  /  Category
```

Putting the format **in the label** is the part that matters: it survives
typing. The detail page simply does not follow the pattern the rest of the UI
already sets.

The code-references, git-links and time-tracking sections additionally have no
line saying what the feature is for, and their empty state renders nothing —
quieter than a bare form, but no more explanatory.

## EARS SPEC

- Every form control on the issue detail page shall have an associated
  `<label>` element.
- The web UI shall not rely on a placeholder as the only description of a
  control.
- Where a control expects a specific format or unit, the label shall state it.
- Each of the code-references, git-links and time-tracking sections shall carry
  one line stating what the feature is for.
- Each of those sections shall show an empty state describing the feature
  rather than rendering nothing or a bare form.

## How to verify

Count controls versus associated labels in the **served** HTML. A placeholder
does not count.

## Added: form rows must share a baseline (from `tracker-manager-0e2462`, 2026-08-22)

The operator found four elements in one `/setup` row sitting at four different
vertical positions — labels 19px apart, controls 20px apart and 2px different
in height, the button on a fourth baseline. The cause was helper text inside
one column making it taller, with nothing aligning the row.

**The criterion, which is mechanical and discriminating:** for controls that are
siblings in a row, the top of each label must be equal and the top of each
control must be equal, within 1px, **measured from the rendered page**.

### Why this belongs on #16 rather than being someone else's problem

Every check in this repo's audit tooling reads the DOM or the CSS *text*. **Not
one of them could catch this**, because the markup for a broken row and a
correct row is identical. The manager had a screenshot of the defect hours
earlier and reported a word count from it — extracting text from an image
instead of looking at it.

### Status here: UNMEASURED, not PASS

`_pages2.py` uses `.form-row` with sibling labelled controls — the same
structure that failed. The CSS is a two-equal-column grid with no per-column
helper text, so their *specific* cause is absent:

```css
.form-row   { display: grid; grid-template-columns: 1fr 1fr; gap: 20px }
.form-group { margin-bottom: 24px }
.form-label { display: block; margin-bottom: 8px }
```

**But that is reasoning from CSS, which is the instrument this finding
disqualifies.** A grid with equal columns still lets each cell stack from its
own top: if one label *wraps* to two lines at a narrow width, its control drops
~19px and the row breaks — identical markup, identical CSS, broken render. The
pair `Due Date (YYYY-MM-DD)` / `Tags (comma separated)` is long enough to wrap.

There is no browser instrument in this repo, so the honest report is
**UNMEASURED**. Not a finding, and not a clean bill.

### The criterion is four assertions, not one — and labels need a different rule

`tracker-manager-0e2462` closed the scope gap they had declared, and the
construction is the transferable part:

```
controls share a top (within 1px)  ·  controls share a height
their labels share a top           ·  any button in the row shares the controls' top
```

**Pairing labels by geometry finds nothing.** On the defect that prompted this,
the two labels do not overlap vertically *at all* — one ends at 220 and the
other begins at 220 — so a side-by-side-plus-overlap test pairs the controls
and **silently ignores the labels**. Their original check covered two of the
four elements in the defect it was written for.

The rule that works: **build the row from the controls, then follow each
control's `label[for=id]` and require those to share a top.** The association
comes from the markup; only the comparison is geometric.

That is the same shape as the brace boundary in both dead-link matchers — a
rule that looks general and silently covers less than it appears to.

**Consequence for this ticket:** a fix that aligns the inputs and leaves the
labels 19px apart passes the naive check and fails the real one. Whatever
instrument closes #16 must carry all four assertions, and must be proven both
red *and* green — a check that has only ever seen a broken row could be one
that calls every row broken.

### Ordering: labels come before alignment, always

Fixing the labels does not merely satisfy the labelling criterion — **it makes
the alignment criterion expressible.** With no `for=` association there is
nothing to pair a label to and no row to check, so alignment work done first
would have had nothing to measure.

On Tracker this order happened by accident: the operator complained about
comprehensibility before he complained about alignment. The durable form is the
dependency, not the luck — **label association is a precondition for geometric
measurement**, so labels come first whether or not anyone has complained about
them.

### The wrapping-label hazard, answered empirically (on Tracker's UI, not ours)

This ticket raised the hazard structurally: *a grid with equal columns still
lets each cell stack from its own top, so a label that wraps at a narrow width
drops its control ~19px with identical markup and identical CSS.*
`tracker-manager-0e2462` measured it on their fixed layout:

```
label height before : 19px
label height after  : 96px      <- five lines, definitively wrapped
controlTopSpread    : 0
controlHeightSpread : 0
labelTopSpread      : 0
failingRows         : 0
```

**A label five times its normal height does not move the control row** — because
their fix places grid items *explicitly by row*. The old
`align-items: flex-end` layout would have failed this by construction, which is
how it broke when one line of hint text was added.

**Their first attempt at this test was vacuous and they caught it**: they
lengthened the label to 76 characters, got zeros, and nearly reported "wrapping
is safe" — the column was 579px wide and the text never wrapped. The known-
positive (label height 19 → 96) is what makes the zeros mean anything.

### What this settles, and what it does not

**Settled, on their UI:** explicit row placement survives a wrapping label;
equal-columns-with-auto-stacking does not.

**Not settled here.** Our `.form-row` is `grid-template-columns: 1fr 1fr` with
each cell stacking from its own top — the *losing* pattern, not the winning
one. So the structural concern is now backed by a measurement on a real UI,
and our forms remain **UNMEASURED**. A fix must place items explicitly by row,
and must be verified with a known-positive proving the label actually wrapped.

### A hazard we are immune to for the wrong reason

`tracker-manager-0e2462` root-caused a horizontal-overflow defect on their
`/members` page at 375px: `.sr-only` spans using `clip` + `width:1px` and
`position:absolute`, sitting inside a table inside a scroller whose containing
block they escape. At `left:580px` they extend the **document** scroll width
while nothing in the body flow overflows.

Confirmed by a reversible experiment — `docScrollW` 580, with `.sr-only`
`display:none` 375, restored 580.

**Checked here: we have zero `sr-only` / visually-hidden elements and zero
horizontal scrollers**, so the mechanism cannot occur.

**That is not safety, it is the same absence this ticket is about.** We have no
visually-hidden labels because we have no labels on the detail page at all. An
accessibility feature never built cannot break a layout — the same shape as our
copy check passing because the UI explains nothing.

**Consequence for the fix:** whatever closes #16 will *introduce* this hazard,
because visually-hidden labels are one of the standard ways to satisfy it. Use
the modern pattern from the start —

```css
clip-path: inset(50%); width: 1px; height: 1px;
overflow: hidden; white-space: nowrap; position: absolute;
```

— and give any scrolled container `position: relative` so absolutely-positioned
descendants are contained by it.
